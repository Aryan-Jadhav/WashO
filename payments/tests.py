import datetime
from decimal import Decimal
from unittest import mock

from django.contrib.auth.models import Group
from django.core import mail
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import Address, User
from accounts.roles import Role
from catalog.models import ServicePrice
from delivery.services import (DeliveryError, assign_delivery_agent, assign_pickup_agent, confirm_delivery,
                               confirm_pickup, start_delivery)
from orders.models import Coupon, Order, TimeSlot
from orders.services import change_status, create_order
from stores.models import ServiceArea, Store
from tagging.services import add_garment, finish_tagging

from .invoice import build_invoice_pdf, invoice_lines, invoice_number
from .models import Payment
from .services import PaymentError, record_collection

S = Order.Status
TODAY = timezone.localdate()
TOMORROW = TODAY + datetime.timedelta(days=1)


def user_with_role(phone, role, store=None, **kw):
    u = User.objects.create_user(phone, "Laundry@2026", store=store, **kw)
    u.groups.add(Group.objects.get(name=role))
    return u


class PaymentTestBase(TestCase):
    def setUp(self):
        self.store = Store.objects.get(slug="washo-kothrud")
        self.customer = user_with_role("9876500001", Role.CUSTOMER, first_name="Asha & Co",  # '&' must not break PDF
                                       email="asha@example.com")
        self.staff = user_with_role("9876500002", Role.STAFF, store=self.store)
        self.agent = user_with_role("9876500003", Role.AGENT, store=self.store, first_name="Ravi")
        self.address = Address.objects.create(user=self.customer, line1="Flat <5>, Sai & Sons", is_default=True,
                                              area=ServiceArea.objects.get(name="Kothrud"))
        self.shirt = ServicePrice.objects.get(category__slug="wash-iron", item__name="Shirt")   # ₹35
        self.silk = ServicePrice.objects.get(category__slug="dry-clean", item__name="Saree (Silk)")  # ₹299

    def make_order(self, items=None, **kw):
        return create_order(customer=kw.pop("customer", self.customer), address=kw.pop("address", self.address),
                            pickup_date=TOMORROW, time_slot=TimeSlot.objects.first(),
                            selected_items=items or [(self.shirt, 2), (self.silk, 1)], **kw)

    def to_out_for_delivery(self, order, garments=None):
        order = assign_pickup_agent(order, self.agent, self.staff)
        order = confirm_pickup(order, self.agent, 3)
        order = change_status(order, S.AT_STORE, self.staff)
        for sp in garments or [self.shirt, self.shirt, self.silk]:
            add_garment(order, sp, self.staff)
        order = finish_tagging(order, self.staff, confirm_mismatch=True)
        order = change_status(order, S.IN_CLEANING, self.staff)
        order = change_status(order, S.READY, self.staff)
        order = assign_delivery_agent(order, self.agent, TODAY, self.staff)
        return start_delivery(order, self.agent)


class CashOnDeliveryTests(PaymentTestBase):
    def test_delivery_needs_payment(self):
        order = self.to_out_for_delivery(self.make_order())
        with self.assertRaisesMessage(DeliveryError, "Collect ₹369.00"):
            confirm_delivery(order, self.agent, 3)
        order.refresh_from_db()
        self.assertEqual(order.status, S.OUT_FOR_DELIVERY)
        self.assertFalse(Payment.objects.exists())

    def test_payment_recorded_with_delivery(self):
        order = self.to_out_for_delivery(self.make_order())
        confirm_delivery(order, self.agent, 3, payment_method="upi", reference="UPI123")
        p = Payment.objects.get(order=order)
        self.assertEqual((p.amount, p.method, p.collected_by, p.reference),
                         (Decimal("369.00"), "upi", self.agent, "UPI123"))
        order.refresh_from_db()
        self.assertEqual(order.status, S.DELIVERED)

    def test_cannot_pay_twice_or_before_final_bill(self):
        order = self.make_order()
        with self.assertRaisesMessage(PaymentError, "final bill isn't ready"):
            record_collection(order, self.agent, "cash")
        order = self.to_out_for_delivery(order)
        record_collection(order, self.agent, "cash")
        with self.assertRaisesMessage(PaymentError, "already recorded"):
            record_collection(order, self.agent, "cash")

    def test_nothing_to_collect_when_coupon_covers_bill(self):
        Coupon.objects.create(code="FREEWASH", description="Free", discount_type="flat", value=Decimal("5000"),
                              valid_from=TODAY, valid_until=TOMORROW)
        order = self.to_out_for_delivery(self.make_order(coupon_code="FREEWASH"))
        self.assertEqual(order.total, Decimal("0.00"))
        confirm_delivery(order, self.agent, 3)  # no payment needed
        self.assertFalse(Payment.objects.exists())

    def test_agent_form_requires_collected_tick(self):
        order = self.to_out_for_delivery(self.make_order())
        self.client.force_login(self.agent)
        resp = self.client.post(reverse("delivery:job_deliver", args=[order.code]),
                                {"count": 3, "payment_method": "cash"})
        self.assertTrue(resp.context["delivery_form"].errors.get("payment_collected"))
        self.client.post(reverse("delivery:job_deliver", args=[order.code]),
                         {"count": 3, "payment_method": "cash", "payment_collected": "on"})
        self.assertContains(self.client.get(reverse("delivery:my_jobs")), "Collected today")


class InvoiceTests(PaymentTestBase):
    def test_invoice_lines_group_same_items(self):
        order = self.to_out_for_delivery(self.make_order())
        lines = invoice_lines(order)
        self.assertEqual([(l["qty"], l["amount"]) for l in lines], [(1, Decimal("299.00")), (2, Decimal("70.00"))])

    def test_invoice_lines_add_up_to_subtotal_for_express(self):
        order = self.to_out_for_delivery(self.make_order(is_express=True))
        lines = invoice_lines(order)
        self.assertEqual(sum(l["amount"] for l in lines), order.subtotal)  # express is shown separately
        self.assertEqual(order.subtotal + order.express_charge - order.discount, order.total)

    def test_pdf_is_built_even_with_special_characters(self):
        order = self.to_out_for_delivery(self.make_order())
        pdf = build_invoice_pdf(order)
        self.assertTrue(pdf.startswith(b"%PDF"))
        self.assertGreater(len(pdf), 1500)

    def test_customer_downloads_own_invoice(self):
        order = self.to_out_for_delivery(self.make_order())
        self.client.force_login(self.customer)
        resp = self.client.get(reverse("payments:invoice", args=[order.code]), {"download": 1})
        self.assertEqual(resp["Content-Type"], "application/pdf")
        self.assertIn(f'attachment; filename="{invoice_number(order)}.pdf"', resp["Content-Disposition"])

    def test_invoice_access_rules(self):
        order = self.to_out_for_delivery(self.make_order())
        url = reverse("payments:invoice", args=[order.code])
        other = user_with_role("9876500009", Role.CUSTOMER)
        baner_staff = user_with_role("9876500008", Role.STAFF, store=Store.objects.get(slug="washo-baner"))
        for user, code in [(other, 404), (baner_staff, 404), (self.staff, 200)]:
            self.client.force_login(user)
            self.assertEqual(self.client.get(url).status_code, code, user.phone)
        self.client.logout()
        self.assertEqual(self.client.get(url).status_code, 302)  # login first

    def test_no_invoice_before_final_bill(self):
        order = self.make_order()
        self.client.force_login(self.customer)
        self.assertEqual(self.client.get(reverse("payments:invoice", args=[order.code])).status_code, 404)


class EmailNotificationTests(PaymentTestBase):
    def test_booking_email(self):
        with self.captureOnCommitCallbacks(execute=True):
            order = self.make_order()
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["asha@example.com"])
        self.assertIn(f"{order.code}: Pickup booked", mail.outbox[0].subject)
        self.assertIn(order.code, mail.outbox[0].alternatives[0][0])  # HTML version too

    def test_email_on_each_status_change(self):
        order = self.make_order()
        with self.captureOnCommitCallbacks(execute=True):
            assign_pickup_agent(order, self.agent, self.staff)
        self.assertIn("Agent assigned", mail.outbox[-1].subject)
        self.assertIn("Ravi will pick up", mail.outbox[-1].body)

    def test_delivered_email_has_invoice_attached(self):
        order = self.to_out_for_delivery(self.make_order())
        mail.outbox.clear()
        with self.captureOnCommitCallbacks(execute=True):
            confirm_delivery(order, self.agent, 3, payment_method="cash")
        msg = mail.outbox[-1]
        self.assertIn("Delivered", msg.subject)
        name, content, mimetype = msg.attachments[0]
        self.assertEqual((name, mimetype), (f"{invoice_number(order)}.pdf", "application/pdf"))
        self.assertTrue(content.startswith(b"%PDF"))

    def test_no_email_when_customer_has_none(self):
        nomail = user_with_role("9876500010", Role.CUSTOMER)
        addr = Address.objects.create(user=nomail, line1="X", area=ServiceArea.objects.get(name="Kothrud"))
        with self.captureOnCommitCallbacks(execute=True):
            self.make_order(customer=nomail, address=addr)
        self.assertEqual(len(mail.outbox), 0)

    def test_mail_failure_does_not_break_the_order(self):
        with mock.patch("django.core.mail.EmailMultiAlternatives.send", side_effect=OSError("SMTP down")):
            with self.captureOnCommitCallbacks(execute=True):
                order = self.make_order()
        self.assertTrue(Order.objects.filter(pk=order.pk).exists())
