import datetime
import shutil
import tempfile
from decimal import Decimal
from io import BytesIO

from django.contrib.auth.models import Group
from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from PIL import Image

from accounts.models import Address, User
from accounts.roles import Role
from catalog.models import ServicePrice
from orders.models import Order, TimeSlot
from orders.services import change_status, create_order
from stores.models import ServiceArea, Store

from .models import CountCheck, Garment, MismatchAlert
from .services import TaggingError, add_garment, finish_tagging, record_count, remove_garment
from .templatetags.qr import qr_svg

S = Order.Status
CP = CountCheck.Checkpoint
TOMORROW = timezone.localdate() + datetime.timedelta(days=1)
MEDIA = tempfile.mkdtemp()


def price(cat, item):
    return ServicePrice.objects.select_related("category", "item").get(category__slug=cat, item__name=item)


def user_with_role(phone, role, store=None, **kw):
    u = User.objects.create_user(phone, "Laundry@2026", store=store, **kw)
    u.groups.add(Group.objects.get(name=role))
    return u


class TaggingTestBase(TestCase):
    def setUp(self):
        self.store = Store.objects.get(slug="washo-kothrud")
        self.customer = user_with_role("9876500001", Role.CUSTOMER)
        self.staff = user_with_role("9876500002", Role.STAFF, store=self.store)
        self.admin = User.objects.create_superuser("9000000001", "x", email="admin@washo.local")
        address = Address.objects.create(user=self.customer, line1="Flat 1", is_default=True,
                                         area=ServiceArea.objects.get(name="Kothrud"))
        self.shirt = price("wash-iron", "Shirt")          # ₹35 booked
        self.silk = price("dry-clean", "Saree (Silk)")    # ₹299
        self.order = create_order(customer=self.customer, address=address, pickup_date=TOMORROW,
                                  time_slot=TimeSlot.objects.first(), selected_items=[(self.shirt, 3)])

    def move_to(self, *statuses):
        for s in statuses:
            self.order = change_status(self.order, s, by=self.admin)

    def to_store(self, pickup_count=None):
        self.move_to(S.PICKUP_ASSIGNED, S.PICKED_UP)
        if pickup_count is not None:
            record_count(self.order, CP.PICKUP, pickup_count, by=self.admin)
        self.move_to(S.AT_STORE)

    def tag(self, sp, n=1, **kw):
        return [add_garment(self.order, sp, self.staff, **kw) for _ in range(n)]


class GarmentTaggingTests(TaggingTestBase):
    def test_tag_codes_are_sequential_and_unique(self):
        self.to_store()
        g1, g2, g3 = self.tag(self.shirt, 3)
        self.assertEqual([g.tag_code for g in (g1, g2, g3)],
                         [f"{self.order.code}-01", f"{self.order.code}-02", f"{self.order.code}-03"])
        with self.assertRaises(IntegrityError), transaction.atomic():
            Garment.objects.create(order=self.order, seq=9, tag_code=g1.tag_code, category=g1.category,
                                   item=g1.item, unit_price=1)

    def test_cannot_tag_before_order_reaches_store(self):
        with self.assertRaisesMessage(TaggingError, "only be tagged while the order is At Store"):
            self.tag(self.shirt)

    def test_stain_needs_a_note(self):
        self.to_store()
        with self.assertRaisesMessage(TaggingError, "describe the stain"):
            self.tag(self.shirt, has_stain=True)
        with self.assertRaises(IntegrityError), transaction.atomic():  # DB check constraint too
            Garment.objects.create(order=self.order, seq=50, tag_code="X-50", category=self.shirt.category,
                                   item=self.shirt.item, unit_price=1, has_damage=True)
        g = self.tag(self.shirt, has_stain=True, condition_note="Ink on pocket")[0]
        self.assertTrue(g.has_issue)

    def test_booked_price_is_used_for_booked_items(self):
        self.to_store()
        self.shirt.price = Decimal("99")  # price list changed after booking
        self.shirt.save()
        g = self.tag(ServicePrice.objects.get(pk=self.shirt.pk))[0]
        self.assertEqual(g.unit_price, Decimal("35.00"))  # customer keeps the booked price

    def test_remove_only_before_finishing(self):
        self.to_store()
        g1, g2 = self.tag(self.shirt, 2)
        remove_garment(g2)
        finish_tagging(self.order, self.staff)
        with self.assertRaises(TaggingError):
            remove_garment(g1)

    def test_qr_svg_is_inline_svg(self):
        svg = qr_svg("https://example.com/staff/tag/WO-000001-01/")
        self.assertTrue(svg.startswith("<svg class=\"qr\""))
        self.assertNotIn("<?xml", svg)


class FinalBillTests(TaggingTestBase):
    def test_final_bill_from_tagged_garments(self):
        self.to_store()
        self.tag(self.shirt, 4)   # booked 3, actually 4 shirts
        self.tag(self.silk, 1)    # plus a saree not in the booking
        order = finish_tagging(self.order, self.staff)
        order.refresh_from_db()
        self.assertEqual(order.status, S.TAGGED)
        self.assertTrue(order.bill_finalised)
        self.assertEqual(order.estimated_total, Decimal("105.00"))  # 3 x 35
        self.assertEqual(order.subtotal, Decimal("439.00"))         # 4 x 35 + 299
        self.assertEqual(order.total, Decimal("439.00"))

    def test_express_and_coupon_recalculated(self):
        address = self.customer.addresses.first()
        order = create_order(customer=self.customer, address=address, pickup_date=TOMORROW,
                             time_slot=TimeSlot.objects.last(), selected_items=[(self.silk, 2)],
                             is_express=True, coupon_code="WELCOME50")  # 598 + 299 express - 50
        self.order = order
        self.to_store()
        self.tag(self.silk, 1)  # only one saree arrived
        finish_tagging(self.order, self.staff)
        self.order.refresh_from_db()
        self.assertEqual(self.order.subtotal, Decimal("299.00"))
        self.assertEqual(self.order.express_charge, Decimal("149.50"))
        self.assertEqual(self.order.discount, Decimal("50.00"))      # 448.50 is still above ₹299 minimum
        self.assertEqual(self.order.total, Decimal("398.50"))

    def test_coupon_dropped_if_final_amount_below_minimum(self):
        address = self.customer.addresses.first()
        self.order = create_order(customer=self.customer, address=address, pickup_date=TOMORROW,
                                  time_slot=TimeSlot.objects.last(), selected_items=[(self.shirt, 10)],
                                  coupon_code="WELCOME50")  # 350 >= 299
        self.to_store()
        self.tag(self.shirt, 5)  # 175 < 299
        finish_tagging(self.order, self.staff)
        self.order.refresh_from_db()
        self.assertEqual(self.order.discount, Decimal("0.00"))
        self.assertEqual(self.order.total, Decimal("175.00"))

    def test_finish_needs_at_least_one_garment(self):
        self.to_store()
        with self.assertRaisesMessage(TaggingError, "at least one garment"):
            finish_tagging(self.order, self.staff)


class GarmentCountMismatchTests(TaggingTestBase):
    """Counts at pickup, store and delivery must match; otherwise admin is alerted."""

    def test_matching_counts_raise_no_alert(self):
        self.to_store(pickup_count=3)
        self.tag(self.shirt, 3)
        finish_tagging(self.order, self.staff)
        self.assertFalse(MismatchAlert.objects.exists())
        self.assertEqual(CountCheck.objects.get(order=self.order, checkpoint=CP.STORE).count, 3)

    def test_store_count_lower_than_pickup_raises_alert_and_emails_admin(self):
        self.to_store(pickup_count=5)
        self.tag(self.shirt, 4)
        # Staff must confirm they re-checked the bag before finishing with a different count.
        with self.assertRaisesMessage(TaggingError, "counted 5 garments at pickup but 4 are tagged"):
            finish_tagging(self.order, self.staff)
        with self.captureOnCommitCallbacks(execute=True):
            finish_tagging(self.order, self.staff, confirm_mismatch=True)
        alert = MismatchAlert.objects.get(order=self.order)
        self.assertEqual((alert.checkpoint, alert.expected_count, alert.actual_count), (CP.STORE, 5, 4))
        self.assertEqual(alert.difference, -1)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("admin@washo.local", mail.outbox[0].to)
        self.assertIn("mismatch", mail.outbox[0].subject.lower())

    def test_delivery_count_compared_with_store_count(self):
        self.to_store(pickup_count=3)
        self.tag(self.shirt, 3)
        finish_tagging(self.order, self.staff)
        self.move_to(S.IN_CLEANING, S.READY, S.OUT_FOR_DELIVERY)
        _, alert = record_count(self.order, CP.DELIVERY, 2, by=self.admin)
        self.assertIsNotNone(alert)
        self.assertEqual((alert.checkpoint, alert.expected_count, alert.actual_count), (CP.DELIVERY, 3, 2))
        _, alert2 = record_count(self.order, CP.DELIVERY, 3, by=self.admin)  # recount is correct
        self.assertIsNone(alert2)

    def test_same_wrong_count_twice_gives_one_alert(self):
        record_count(self.order, CP.PICKUP, 4, by=self.admin)
        record_count(self.order, CP.STORE, 3, by=self.admin)
        record_count(self.order, CP.STORE, 3, by=self.admin)
        self.assertEqual(MismatchAlert.objects.count(), 1)

    def test_no_alert_without_previous_count(self):
        _, alert = record_count(self.order, CP.STORE, 3, by=self.admin)
        self.assertIsNone(alert)

    def test_alert_needs_different_counts_in_db(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            MismatchAlert.objects.create(order=self.order, checkpoint=CP.STORE, expected_count=3, actual_count=3)

    def test_admin_resolves_alert(self):
        record_count(self.order, CP.PICKUP, 4, by=self.admin)
        _, alert = record_count(self.order, CP.STORE, 3, by=self.admin)
        self.client.force_login(self.admin)
        self.client.post(reverse("tagging:alert_resolve", args=[alert.pk]),
                         {"resolution_note": "Agent miscounted at pickup"})
        alert.refresh_from_db()
        self.assertEqual(alert.status, MismatchAlert.Status.RESOLVED)
        self.assertEqual(alert.resolved_by, self.admin)


@override_settings(MEDIA_ROOT=MEDIA)
class StaffPanelViewTests(TaggingTestBase):
    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(MEDIA, ignore_errors=True)
        super().tearDownClass()

    def test_staff_sees_only_own_store(self):
        self.client.force_login(self.staff)
        self.assertEqual(self.client.get(reverse("tagging:order", args=[self.order.code])).status_code, 200)
        other = user_with_role("9876500003", Role.STAFF, store=Store.objects.get(slug="washo-baner"))
        self.client.force_login(other)
        self.assertEqual(self.client.get(reverse("tagging:order", args=[self.order.code])).status_code, 404)

    def test_customer_and_agent_cannot_open_panel(self):
        self.client.force_login(self.customer)
        self.assertEqual(self.client.get(reverse("tagging:panel")).status_code, 403)
        agent = user_with_role("9876500004", Role.AGENT, store=self.store)
        self.client.force_login(agent)
        self.assertEqual(self.client.get(reverse("tagging:panel")).status_code, 403)

    def test_only_admin_sees_alerts_page(self):
        self.client.force_login(self.staff)
        self.assertEqual(self.client.get(reverse("tagging:alerts")).status_code, 403)
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(reverse("tagging:alerts")).status_code, 200)

    def test_staff_flow_receive_tag_with_photo_finish(self):
        self.move_to(S.PICKUP_ASSIGNED, S.PICKED_UP)
        self.client.force_login(self.staff)
        self.client.post(reverse("tagging:order_step", args=[self.order.code]))  # received at store
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, S.AT_STORE)

        buf = BytesIO()
        Image.new("RGB", (10, 10), "red").save(buf, "JPEG")
        photo = SimpleUploadedFile("stain.jpg", buf.getvalue(), content_type="image/jpeg")
        resp = self.client.post(reverse("tagging:garment_add", args=[self.order.code]), {
            "service_price": self.shirt.pk, "description": "White", "has_stain": "on",
            "condition_note": "Tea stain on collar", "photo": photo,
        }, HTTP_HX_REQUEST="true")
        self.assertContains(resp, f"{self.order.code}-01")
        self.assertNotContains(resp, "<html")  # HTMX fragment only
        g = Garment.objects.get()
        self.assertTrue(g.photo.name.startswith("garments/"))

        self.client.post(reverse("tagging:finish_tagging", args=[self.order.code]))
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, S.TAGGED)
        self.assertEqual(self.client.get(reverse("tagging:tags_print", args=[self.order.code])).status_code, 200)
        resp = self.client.get(reverse("tagging:garment_lookup", args=[g.tag_code]))
        self.assertContains(resp, "Tea stain on collar")

    def test_customer_sees_their_garments(self):
        self.to_store()
        self.tag(self.shirt, has_damage=True, condition_note="Button missing")
        finish_tagging(self.order, self.staff)
        self.client.force_login(self.customer)
        resp = self.client.get(reverse("orders:detail", args=[self.order.code]))
        self.assertContains(resp, f"{self.order.code}-01")
        self.assertContains(resp, "Button missing")

    def test_staff_login_lands_on_panel(self):
        resp = self.client.post(reverse("login"), {"username": "9876500002", "password": "Laundry@2026"})
        self.assertRedirects(resp, reverse("accounts:after_login"), fetch_redirect_response=False)
        self.assertRedirects(self.client.get(reverse("accounts:after_login")), reverse("tagging:panel"))
