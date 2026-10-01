import datetime
from decimal import Decimal
from io import StringIO

from django.contrib.auth.models import Group
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from accounts.roles import Role
from orders.models import Order, OrderStatusHistory
from payments.models import Payment
from stores.models import Store
from tagging.models import CountCheck, MismatchAlert

from .models import DailyRevenue
from .services import dashboard_data

S = Order.Status


class SeedDemoTests(TestCase):
    """seed_demo builds 60 realistic orders through the real business rules."""

    @classmethod
    def setUpTestData(cls):
        call_command("seed_demo", stdout=StringIO())

    def demo_orders(self):
        return Order.objects.filter(customer__phone__startswith="901100")

    def test_counts_and_every_status_present(self):
        self.assertEqual(User.objects.filter(phone__startswith="901100", groups__name=Role.CUSTOMER).count(), 20)
        self.assertEqual(self.demo_orders().count(), 60)
        self.assertEqual(set(self.demo_orders().values_list("status", flat=True)), set(S.values))
        for store in Store.objects.all():  # every store has staff and agents
            self.assertTrue(store.team.filter(groups__name=Role.STAFF).exists())
            self.assertEqual(store.team.filter(groups__name=Role.AGENT).count(), 2)

    def test_delivered_orders_are_complete(self):
        delivered = self.demo_orders().filter(status=S.DELIVERED)
        self.assertEqual(delivered.count(), 30)
        for o in delivered:
            self.assertTrue(Payment.objects.filter(order=o, amount=o.total).exists())
            self.assertEqual(o.count_checks.count(), 3)
            self.assertTrue(o.bill_finalised)

    def test_timeline_is_in_the_past_and_in_order(self):
        now = timezone.now()
        self.assertFalse(OrderStatusHistory.objects.filter(changed_at__gt=now).exists())
        for o in self.demo_orders():
            times = list(o.history.order_by("id").values_list("changed_at", flat=True))
            self.assertEqual(times, sorted(times), o.code)

    def test_mismatch_alerts_for_demo(self):
        self.assertEqual(MismatchAlert.objects.filter(status=MismatchAlert.Status.OPEN).count(), 2)
        self.assertTrue(MismatchAlert.objects.filter(status=MismatchAlert.Status.RESOLVED).exists())

    def test_second_run_skips_and_reset_rebuilds(self):
        out = StringIO()
        call_command("seed_demo", stdout=out)
        self.assertIn("already loaded", out.getvalue())
        self.assertEqual(self.demo_orders().count(), 60)
        call_command("seed_demo", "--reset", stdout=StringIO())
        self.assertEqual(self.demo_orders().count(), 60)
        self.assertEqual(User.objects.filter(phone__startswith="901100").count(), 20)

    def test_revenue_view_matches_payments(self):
        """The PostgreSQL view adds up exactly the money in the payments table."""
        view_total = sum((r.revenue for r in DailyRevenue.objects.all()), Decimal("0"))
        self.assertEqual(view_total, sum((p.amount for p in Payment.objects.all()), Decimal("0")))
        self.assertEqual(sum(r.orders for r in DailyRevenue.objects.all()), Payment.objects.count())


class DashboardTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_demo", stdout=StringIO())

    def test_kpis_and_charts(self):
        data = dashboard_data()
        self.assertEqual(len(data["daily"]), 30)
        self.assertEqual(len(data["monthly"]), 12)
        self.assertEqual(sum(s["value"] for s in data["by_status"]), Order.objects.count())
        self.assertEqual(data["kpis"]["open_orders"], Order.objects.exclude(status__in=[S.DELIVERED, S.CANCELLED]).count())
        thirty_days = sum(d["value"] for d in data["daily"])
        start = timezone.localdate() - datetime.timedelta(days=29)
        expected = sum(float(p.amount) for p in Payment.objects.all()
                       if timezone.localdate(p.collected_at) >= start)
        self.assertAlmostEqual(thirty_days, expected, places=2)

    def test_store_filter(self):
        baner = Store.objects.get(slug="washo-baner")
        data = dashboard_data(store=baner)
        self.assertEqual(sum(s["value"] for s in data["by_status"]), Order.objects.filter(store=baner).count())

    def test_only_admin_can_open(self):
        url = reverse("dashboard:home")
        self.client.force_login(User.objects.get(phone="9044000001"))
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'id="chart-data"')
        staff = User.objects.filter(groups__name=Role.STAFF).first()
        self.client.force_login(staff)
        self.assertEqual(self.client.get(url).status_code, 403)

    def test_admin_lands_on_dashboard(self):
        self.client.post(reverse("login"), {"username": "9044000001", "password": "Demo@1234"})
        self.assertRedirects(self.client.get(reverse("accounts:after_login")), reverse("dashboard:home"))


class DashboardEmptyTests(TestCase):
    def test_works_with_no_orders(self):
        admin = User.objects.create_superuser("9000000001", "x")
        admin.groups.add(Group.objects.get(name=Role.ADMIN))
        self.client.force_login(admin)
        self.assertEqual(self.client.get(reverse("dashboard:home")).status_code, 200)
