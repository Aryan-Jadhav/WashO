import datetime
from decimal import Decimal

from django.contrib.auth.models import Group
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import Address, User
from accounts.roles import Role
from catalog.models import ServicePrice
from stores.models import ServiceArea

from .models import Coupon, CouponError, DailySlot, Order, OrderStatusHistory, TimeSlot
from .pricing import build_quote
from .services import (BookingError, InvalidTransition, cancel_order, change_status, check_slot_bookable,
                       create_order, reserve_slot)

S = Order.Status
TOMORROW = timezone.localdate() + datetime.timedelta(days=1)


def make_customer(phone="9876500001"):
    user = User.objects.create_user(phone, "Laundry@2026", first_name="Asha")
    user.groups.add(Group.objects.get(name=Role.CUSTOMER))
    return user


def make_address(user, area_name="Kothrud"):
    return Address.objects.create(user=user, line1="Flat 5, Sai Heights", area=ServiceArea.objects.get(name=area_name),
                                  is_default=True)


def give_agent(order):
    """Orders need an agent before Pickup Assigned / Out for Delivery (Phase 5 rule)."""
    agent = User.objects.create_user("9700000000", "x", store=order.store)
    agent.groups.add(Group.objects.get(name=Role.AGENT))
    Order.objects.filter(pk=order.pk).update(pickup_agent=agent, delivery_agent=agent)
    return agent


def price(category_slug, item_name):
    return ServicePrice.objects.select_related("category", "item").get(category__slug=category_slug,
                                                                       item__name=item_name)


class OrderTotalTests(TestCase):
    """Order total = items + express charge - coupon discount."""

    def setUp(self):
        self.shirt_wi = price("wash-iron", "Shirt")       # ₹35, express +50%
        self.silk = price("dry-clean", "Saree (Silk)")     # ₹299, express +50%
        self.shoes = price("shoe-cleaning", "Sports Shoes")  # ₹399, no express

    def test_simple_total(self):
        q = build_quote([(self.shirt_wi, 5), (self.silk, 1)])
        self.assertEqual(q.subtotal, Decimal("474.00"))  # 5*35 + 299
        self.assertEqual(q.express_charge, Decimal("0.00"))
        self.assertEqual(q.total, Decimal("474.00"))
        self.assertEqual(q.piece_count, 6)

    def test_express_charge_only_on_services_with_express(self):
        q = build_quote([(self.shirt_wi, 2), (self.shoes, 1)], is_express=True)
        self.assertEqual(q.subtotal, Decimal("469.00"))        # 70 + 399
        self.assertEqual(q.express_charge, Decimal("35.00"))   # 50% of 70; shoes get no surcharge
        self.assertEqual(q.total, Decimal("504.00"))

    def test_zero_quantities_ignored(self):
        q = build_quote([(self.shirt_wi, 0)])
        self.assertEqual(q.lines, [])
        self.assertEqual(q.total, Decimal("0"))


class CouponRuleTests(TestCase):
    def setUp(self):
        self.user = make_customer()
        self.today = timezone.localdate()
        self.flat = Coupon.objects.get(code="WELCOME50")      # ₹50 off, min ₹299, 1 per user
        self.percent = Coupon.objects.get(code="FRESH20")     # 20% up to ₹150, min ₹499

    def test_flat_discount(self):
        self.assertEqual(self.flat.discount_for(Decimal("400")), Decimal("50.00"))

    def test_percent_discount_with_cap(self):
        self.assertEqual(self.percent.discount_for(Decimal("500")), Decimal("100.00"))
        self.assertEqual(self.percent.discount_for(Decimal("2000")), Decimal("150.00"))  # capped

    def test_minimum_order_value(self):
        with self.assertRaisesMessage(CouponError, "Add items worth ₹49.00 more"):
            self.flat.check_usable(self.user, Decimal("250"), self.today)
        self.assertEqual(self.flat.discount_for(Decimal("250")), Decimal("0.00"))

    def test_expired_and_inactive(self):
        with self.assertRaisesMessage(CouponError, "expired"):
            Coupon.objects.get(code="MONSOON15").check_usable(self.user, Decimal("1000"), self.today)
        self.flat.is_active = False
        with self.assertRaisesMessage(CouponError, "no longer active"):
            self.flat.check_usable(self.user, Decimal("1000"), self.today)

    def test_discount_never_exceeds_amount(self):
        coupon = Coupon(code="BIG", discount_type="flat", value=Decimal("500"))
        self.assertEqual(coupon.discount_for(Decimal("120")), Decimal("120.00"))

    def test_per_user_and_total_limits(self):
        address = make_address(self.user)
        items = [(price("dry-clean", "Saree (Silk)"), 2)]  # ₹598
        slot = TimeSlot.objects.first()
        create_order(customer=self.user, address=address, pickup_date=TOMORROW, time_slot=slot,
                     selected_items=items, coupon_code="welcome50")  # lower case works too
        with self.assertRaisesMessage(CouponError, "already used"):
            self.flat.check_usable(self.user, Decimal("1000"), self.today)

        self.percent.usage_limit = 0
        self.percent.save()
        with self.assertRaisesMessage(CouponError, "fully used"):
            self.percent.check_usable(self.user, Decimal("1000"), self.today)

    def test_cancelled_order_gives_coupon_back(self):
        address = make_address(self.user)
        order = create_order(customer=self.user, address=address, pickup_date=TOMORROW,
                             time_slot=TimeSlot.objects.first(),
                             selected_items=[(price("dry-clean", "Saree (Silk)"), 2)], coupon_code="WELCOME50")
        cancel_order(order, by=self.user)
        self.flat.check_usable(self.user, Decimal("1000"), self.today)  # no error

    def test_invalid_coupon_in_quote(self):
        q = build_quote([(price("dry-clean", "Saree (Silk)"), 1)], coupon_code="NOPE", user=self.user)
        self.assertEqual(q.coupon_error, "This coupon code doesn't exist.")
        self.assertEqual(q.discount, Decimal("0"))

    def test_coupon_code_must_be_uppercase_in_db(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            Coupon.objects.filter(code="FRESH20").update(code="fresh20")


class SlotCapacityTests(TestCase):
    def setUp(self):
        self.slot = TimeSlot.objects.get(start_time=datetime.time(10))  # capacity 5
        self.area = ServiceArea.objects.get(name="Kothrud")

    def test_slot_cannot_be_overbooked(self):
        with transaction.atomic():
            for _ in range(self.slot.capacity):
                reserve_slot(TOMORROW, self.slot, self.area)
        with self.assertRaisesMessage(BookingError, "just got full"):
            with transaction.atomic():
                reserve_slot(TOMORROW, self.slot, self.area)
        self.assertEqual(DailySlot.objects.get(date=TOMORROW, time_slot=self.slot, area=self.area).booked_count, 5)

    def test_capacity_is_per_area(self):
        with transaction.atomic():
            for _ in range(self.slot.capacity):
                reserve_slot(TOMORROW, self.slot, self.area)
            # A different area has its own places.
            reserve_slot(TOMORROW, self.slot, ServiceArea.objects.get(name="Baner"))

    def test_cancel_releases_place(self):
        user = make_customer()
        address = make_address(user)
        self.slot.capacity = 1
        self.slot.save()
        items = [(price("wash-iron", "Shirt"), 3)]
        order = create_order(customer=user, address=address, pickup_date=TOMORROW, time_slot=self.slot,
                             selected_items=items)
        with self.assertRaises(BookingError):
            create_order(customer=user, address=address, pickup_date=TOMORROW, time_slot=self.slot,
                         selected_items=items)
        cancel_order(order, by=user)
        create_order(customer=user, address=address, pickup_date=TOMORROW, time_slot=self.slot,
                     selected_items=items)  # works again

    def test_past_and_too_far_slots_rejected(self):
        now = timezone.make_aware(datetime.datetime.combine(TOMORROW, datetime.time(10, 30)))
        with self.assertRaisesMessage(BookingError, "already started"):
            check_slot_bookable(TOMORROW, self.slot, now)  # 10:00 slot at 10:30
        with self.assertRaisesMessage(BookingError, "within the next"):
            check_slot_bookable(TOMORROW + datetime.timedelta(days=30), self.slot)

    def test_failed_booking_takes_no_place(self):
        """Everything is one transaction: an invalid coupon must not keep the slot place."""
        user = make_customer()
        address = make_address(user)
        with self.assertRaises(BookingError):
            create_order(customer=user, address=address, pickup_date=TOMORROW, time_slot=self.slot,
                         selected_items=[(price("wash-iron", "Shirt"), 1)], coupon_code="WELCOME50")  # below min
        self.assertFalse(DailySlot.objects.filter(booked_count__gt=0).exists())


class StatusTransitionTests(TestCase):
    def setUp(self):
        self.user = make_customer()
        self.admin = User.objects.create_superuser("9000000001", "x")
        self.order = create_order(customer=self.user, address=make_address(self.user), pickup_date=TOMORROW,
                                  time_slot=TimeSlot.objects.first(),
                                  selected_items=[(price("wash-iron", "Shirt"), 4)])
        give_agent(self.order)

    def test_full_happy_path(self):
        for status in [S.PICKUP_ASSIGNED, S.PICKED_UP, S.AT_STORE, S.TAGGED, S.IN_CLEANING,
                       S.READY, S.OUT_FOR_DELIVERY, S.DELIVERED]:
            self.order = change_status(self.order, status, by=self.admin)
        self.assertEqual(self.order.status, S.DELIVERED)

    def test_skipping_a_step_is_rejected(self):
        with self.assertRaises(InvalidTransition):
            change_status(self.order, S.READY, by=self.admin)

    def test_no_change_after_delivered_or_cancelled(self):
        cancel_order(self.order, by=self.user)
        with self.assertRaises(InvalidTransition):
            change_status(self.order, S.PICKUP_ASSIGNED, by=self.admin)

    def test_cannot_cancel_after_pickup(self):
        change_status(self.order, S.PICKUP_ASSIGNED, by=self.admin)
        change_status(self.order, S.PICKED_UP, by=self.admin)
        with self.assertRaisesMessage(InvalidTransition, "already been picked up"):
            cancel_order(self.order, by=self.user)


class StatusHistoryTriggerTests(TestCase):
    """The PL/pgSQL trigger writes the history (Python never inserts history rows)."""

    def setUp(self):
        self.user = make_customer()
        self.admin = User.objects.create_superuser("9000000001", "x")
        self.order = create_order(customer=self.user, address=make_address(self.user), pickup_date=TOMORROW,
                                  time_slot=TimeSlot.objects.first(),
                                  selected_items=[(price("wash-iron", "Shirt"), 4)])
        give_agent(self.order)

    def test_booking_and_changes_are_logged_with_user(self):
        change_status(self.order, S.PICKUP_ASSIGNED, by=self.admin, note="Agent Ravi")
        rows = list(OrderStatusHistory.objects.filter(order=self.order))
        self.assertEqual([(r.from_status, r.to_status) for r in rows],
                         [("", "booked"), ("booked", "pickup_assigned")])
        self.assertEqual(rows[0].changed_by, self.user)
        self.assertEqual(rows[1].changed_by, self.admin)
        self.assertEqual(rows[1].note, "Agent Ravi")

    def test_direct_database_update_is_still_logged(self):
        with transaction.atomic():
            # Bypass change_status completely, like someone running SQL by hand.
            from django.db import connection
            with connection.cursor() as cur:
                cur.execute("SELECT set_config('washo.changed_by', '', true)")
            Order.objects.filter(pk=self.order.pk).update(status=S.PICKUP_ASSIGNED)
        last = OrderStatusHistory.objects.filter(order=self.order).last()
        self.assertEqual(last.to_status, "pickup_assigned")
        self.assertIsNone(last.changed_by)

    def test_other_field_updates_not_logged(self):
        Order.objects.filter(pk=self.order.pk).update(customer_note="Ring the bell")
        self.assertEqual(OrderStatusHistory.objects.filter(order=self.order).count(), 1)

    def test_total_must_add_up_in_db(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            Order.objects.filter(pk=self.order.pk).update(total=Decimal("1"))


class BookingPageTests(TestCase):
    def setUp(self):
        self.user = make_customer()
        self.client.force_login(self.user)
        self.slot = TimeSlot.objects.get(start_time=datetime.time(16))
        self.shirt = price("wash-iron", "Shirt")

    def post_booking(self, **extra):
        address = self.user.addresses.first()
        data = {"address": address.pk, "pickup_date": TOMORROW.isoformat(), "time_slot": self.slot.pk,
                f"qty_{self.shirt.pk}": 10, "coupon_code": "", "note": ""}
        data.update(extra)
        return self.client.post(reverse("orders:book"), data)

    def test_no_address_redirects_to_add_address(self):
        resp = self.client.get(reverse("orders:book"))
        self.assertRedirects(resp, f"{reverse('accounts:address_create')}?next={reverse('orders:book')}")

    def test_book_order_end_to_end(self):
        make_address(self.user)
        resp = self.post_booking()
        order = Order.objects.get(customer=self.user)
        self.assertRedirects(resp, reverse("orders:detail", args=[order.code]))
        self.assertEqual(order.total, Decimal("350.00"))
        self.assertEqual(order.store.slug, "washo-kothrud")
        self.assertTrue(order.code.startswith("WO-"))
        self.assertEqual(order.history.count(), 1)

    def test_booking_without_items_shows_error(self):
        make_address(self.user)
        resp = self.post_booking(**{f"qty_{self.shirt.pk}": 0})
        self.assertContains(resp, "Please add at least one item")
        self.assertFalse(Order.objects.exists())

    def test_cannot_use_someone_elses_address(self):
        make_address(self.user)
        other = make_customer("9876500002")
        other_addr = make_address(other)
        resp = self.post_booking(address=other_addr.pk)
        self.assertIn("address", resp.context["form"].errors)

    def test_estimate_endpoint(self):
        resp = self.client.post(reverse("orders:book_estimate"),
                                {f"qty_{self.shirt.pk}": 10, "coupon_code": "WELCOME50"})
        self.assertEqual(resp.context["quote"].total, Decimal("300.00"))  # 350 - 50

    def test_customer_sees_only_own_orders(self):
        make_address(self.user)
        self.post_booking()
        order = Order.objects.get()
        other = make_customer("9876500002")
        self.client.force_login(other)
        self.assertEqual(self.client.get(reverse("orders:detail", args=[order.code])).status_code, 404)

    def test_staff_cannot_open_booking_page(self):
        staff = User.objects.create_user("9876500003", "x")
        staff.groups.add(Group.objects.get(name=Role.STAFF))
        self.client.force_login(staff)
        self.assertEqual(self.client.get(reverse("orders:book")).status_code, 403)

    def test_cancel_from_order_page(self):
        make_address(self.user)
        self.post_booking()
        order = Order.objects.get()
        self.client.post(reverse("orders:cancel", args=[order.code]), {"reason": "Not at home"})
        order.refresh_from_db()
        self.assertEqual(order.status, S.CANCELLED)
        self.assertEqual(order.history.last().note, "Not at home")


class AddressBookTests(TestCase):
    def setUp(self):
        self.user = make_customer()
        self.client.force_login(self.user)

    def test_only_one_default(self):
        a1 = make_address(self.user)
        self.client.post(reverse("accounts:address_create"), {
            "label": "work", "line1": "Office 3", "area": ServiceArea.objects.get(name="Baner").pk,
            "is_default": "on"})
        a1.refresh_from_db()
        self.assertFalse(a1.is_default)
        self.assertEqual(self.user.addresses.filter(is_default=True).count(), 1)

    def test_db_rejects_two_defaults(self):
        make_address(self.user)
        with self.assertRaises(IntegrityError), transaction.atomic():
            make_address(self.user)

    def test_delete_is_soft_and_promotes_new_default(self):
        a1 = make_address(self.user)
        a2 = Address.objects.create(user=self.user, line1="B", area=ServiceArea.objects.get(name="Aundh"))
        self.client.post(reverse("accounts:address_delete", args=[a1.pk]))
        a1.refresh_from_db()
        a2.refresh_from_db()
        self.assertFalse(a1.is_active)  # still in DB for old orders
        self.assertTrue(a2.is_default)
