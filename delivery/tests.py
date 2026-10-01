import datetime

from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import Address, User
from accounts.roles import Role
from catalog.models import ServicePrice
from orders.models import Order, TimeSlot
from orders.services import InvalidTransition, change_status, create_order
from stores.models import ServiceArea, Store
from tagging.models import CountCheck, MismatchAlert
from tagging.services import add_garment, finish_tagging

from .services import (DeliveryError, agent_jobs, assign_delivery_agent, assign_pickup_agent, confirm_delivery,
                       confirm_pickup, start_delivery)

S = Order.Status
CP = CountCheck.Checkpoint
TODAY = timezone.localdate()
TOMORROW = TODAY + datetime.timedelta(days=1)


def user_with_role(phone, role, store=None, **kw):
    u = User.objects.create_user(phone, "Laundry@2026", store=store, **kw)
    u.groups.add(Group.objects.get(name=role))
    return u


class DeliveryTestBase(TestCase):
    def setUp(self):
        self.store = Store.objects.get(slug="washo-kothrud")
        self.customer = user_with_role("9876500001", Role.CUSTOMER)
        self.staff = user_with_role("9876500002", Role.STAFF, store=self.store)
        self.agent = user_with_role("9876500003", Role.AGENT, store=self.store, first_name="Ravi")
        self.other_agent = user_with_role("9876500004", Role.AGENT, store=Store.objects.get(slug="washo-baner"))
        self.address = Address.objects.create(user=self.customer, line1="Flat 1", is_default=True,
                                              area=ServiceArea.objects.get(name="Kothrud"))
        self.shirt = ServicePrice.objects.get(category__slug="wash-iron", item__name="Shirt")
        self.order = create_order(customer=self.customer, address=self.address, pickup_date=TOMORROW,
                                  time_slot=TimeSlot.objects.first(), selected_items=[(self.shirt, 3)])

    def to_ready(self, garments=3, pickup_count=3):
        """Assign, pick up, tag at store, clean -> Ready."""
        self.order = assign_pickup_agent(self.order, self.agent, self.staff)
        self.order = confirm_pickup(self.order, self.agent, pickup_count)
        self.order = change_status(self.order, S.AT_STORE, self.staff)
        for _ in range(garments):
            add_garment(self.order, self.shirt, self.staff)
        self.order = finish_tagging(self.order, self.staff, confirm_mismatch=True)
        self.order = change_status(self.order, S.IN_CLEANING, self.staff)
        self.order = change_status(self.order, S.READY, self.staff)


class AssignmentTests(DeliveryTestBase):
    def test_pickup_assigned_needs_an_agent(self):
        with self.assertRaisesMessage(InvalidTransition, "Assign a pickup agent first"):
            change_status(self.order, S.PICKUP_ASSIGNED, self.staff)

    def test_assign_pickup_moves_status_and_logs(self):
        order = assign_pickup_agent(self.order, self.agent, self.staff)
        self.assertEqual(order.status, S.PICKUP_ASSIGNED)
        self.assertEqual(order.pickup_agent, self.agent)
        self.assertIn("Ravi", order.history.last().note)

    def test_agent_must_work_at_order_store(self):
        with self.assertRaisesMessage(DeliveryError, "works at this order's store"):
            assign_pickup_agent(self.order, self.other_agent, self.staff)
        with self.assertRaises(DeliveryError):
            assign_pickup_agent(self.order, self.staff, self.staff)  # staff are not agents

    def test_reassign_before_pickup_keeps_status(self):
        assign_pickup_agent(self.order, self.agent, self.staff)
        second = user_with_role("9876500005", Role.AGENT, store=self.store)
        order = assign_pickup_agent(self.order, second, self.staff)
        self.assertEqual((order.status, order.pickup_agent), (S.PICKUP_ASSIGNED, second))

    def test_delivery_assignment_only_when_ready(self):
        with self.assertRaisesMessage(DeliveryError, "only when the order is Ready"):
            assign_delivery_agent(self.order, self.agent, TODAY, self.staff)
        self.to_ready()
        with self.assertRaisesMessage(DeliveryError, "can't be in the past"):
            assign_delivery_agent(self.order, self.agent, TODAY - datetime.timedelta(days=1), self.staff)
        order = assign_delivery_agent(self.order, self.agent, TODAY, self.staff)
        self.assertEqual(order.status, S.READY)

    def test_out_for_delivery_needs_delivery_agent(self):
        self.to_ready()
        with self.assertRaisesMessage(InvalidTransition, "Assign a delivery agent first"):
            change_status(self.order, S.OUT_FOR_DELIVERY, self.staff)


class AgentJobTests(DeliveryTestBase):
    def test_confirm_pickup_records_count(self):
        assign_pickup_agent(self.order, self.agent, self.staff)
        order = confirm_pickup(self.order, self.agent, 4, note="Customer added a shirt")
        self.assertEqual(order.status, S.PICKED_UP)
        self.assertEqual(CountCheck.objects.get(order=order, checkpoint=CP.PICKUP).count, 4)

    def test_other_agent_cannot_confirm(self):
        assign_pickup_agent(self.order, self.agent, self.staff)
        with self.assertRaisesMessage(DeliveryError, "not assigned to you"):
            confirm_pickup(self.order, self.other_agent, 3)

    def test_delivery_with_matching_count(self):
        self.to_ready()
        assign_delivery_agent(self.order, self.agent, TODAY, self.staff)
        start_delivery(self.order, self.agent)
        order = confirm_delivery(self.order, self.agent, 3)
        self.assertEqual(order.status, S.DELIVERED)
        self.assertFalse(MismatchAlert.objects.filter(checkpoint=CP.DELIVERY).exists())

    def test_delivery_count_mismatch_needs_confirmation_and_alerts(self):
        self.to_ready()
        assign_delivery_agent(self.order, self.agent, TODAY, self.staff)
        start_delivery(self.order, self.agent)
        with self.assertRaisesMessage(DeliveryError, "store tagged 3 garments but you counted 2"):
            confirm_delivery(self.order, self.agent, 2)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, S.OUT_FOR_DELIVERY)  # nothing changed
        confirm_delivery(self.order, self.agent, 2, confirm_mismatch=True)
        alert = MismatchAlert.objects.get(checkpoint=CP.DELIVERY)
        self.assertEqual((alert.expected_count, alert.actual_count), (3, 2))

    def test_agent_jobs_for_the_day(self):
        assign_pickup_agent(self.order, self.agent, self.staff)
        pickups, deliveries, to_store = agent_jobs(self.agent, TODAY)
        self.assertEqual(list(pickups), [])  # pickup is tomorrow
        pickups, _, _ = agent_jobs(self.agent, TOMORROW)
        self.assertEqual(list(pickups), [self.order])
        pickups, _, _ = agent_jobs(self.agent, TOMORROW + datetime.timedelta(days=3))
        self.assertEqual(len(pickups), 1)  # still listed later as overdue
        self.assertEqual(list(agent_jobs(self.other_agent, TOMORROW)[0]), [])


class AgentPanelViewTests(DeliveryTestBase):
    def test_full_journey_through_all_panels(self):
        """Customer books -> staff assign -> agent picks up -> staff tag -> agent delivers."""
        # Staff assigns the pickup agent from the staff panel
        self.client.force_login(self.staff)
        self.client.post(reverse("delivery:assign_pickup", args=[self.order.code]), {"agent": self.agent.pk})
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, S.PICKUP_ASSIGNED)

        # Agent sees the job and confirms pickup with a count
        self.client.force_login(self.agent)
        resp = self.client.get(reverse("delivery:my_jobs"), {"day": TOMORROW.isoformat()})
        self.assertContains(resp, self.order.code)
        resp = self.client.post(reverse("delivery:job_pickup", args=[self.order.code]), {"count": 3})
        self.assertRedirects(resp, reverse("delivery:my_jobs"))
        self.assertContains(self.client.get(reverse("delivery:my_jobs")), "Hand over at store")

        # Store work
        self.order.refresh_from_db()
        self.order = change_status(self.order, S.AT_STORE, self.staff)
        for _ in range(3):
            add_garment(self.order, self.shirt, self.staff)
        finish_tagging(self.order, self.staff)
        change_status(self.order, S.IN_CLEANING, self.staff)
        change_status(self.order, S.READY, self.staff)

        # Staff assigns delivery
        self.client.force_login(self.staff)
        self.client.post(reverse("delivery:assign_delivery", args=[self.order.code]),
                         {"agent": self.agent.pk, "delivery_date": TODAY.isoformat()})

        # Agent delivers
        self.client.force_login(self.agent)
        self.assertContains(self.client.get(reverse("delivery:my_jobs")), self.order.code)
        self.client.post(reverse("delivery:job_start_delivery", args=[self.order.code]))
        self.client.post(reverse("delivery:job_deliver", args=[self.order.code]), {"count": 3})
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, S.DELIVERED)
        self.assertEqual(list(self.order.count_checks.values_list("checkpoint", "count")),
                         [("pickup", 3), ("store", 3), ("delivery", 3)])

    def test_agent_cannot_open_others_job(self):
        assign_pickup_agent(self.order, self.agent, self.staff)
        self.client.force_login(self.other_agent)
        self.assertEqual(self.client.get(reverse("delivery:job", args=[self.order.code])).status_code, 404)

    def test_only_agents_open_my_jobs(self):
        self.client.force_login(self.customer)
        self.assertEqual(self.client.get(reverse("delivery:my_jobs")).status_code, 403)
        self.client.force_login(self.agent)
        self.assertEqual(self.client.get(reverse("tagging:panel")).status_code, 403)  # not a staff panel user

    def test_agent_login_lands_on_my_jobs(self):
        self.client.post(reverse("login"), {"username": "9876500003", "password": "Laundry@2026"})
        self.assertRedirects(self.client.get(reverse("accounts:after_login")), reverse("delivery:my_jobs"))

    def test_staff_of_other_store_cannot_assign(self):
        baner_staff = user_with_role("9876500006", Role.STAFF, store=Store.objects.get(slug="washo-baner"))
        self.client.force_login(baner_staff)
        resp = self.client.post(reverse("delivery:assign_pickup", args=[self.order.code]), {"agent": self.agent.pk})
        self.assertEqual(resp.status_code, 404)

    def test_bad_pickup_count_rejected(self):
        assign_pickup_agent(self.order, self.agent, self.staff)
        self.client.force_login(self.agent)
        resp = self.client.post(reverse("delivery:job_pickup", args=[self.order.code]), {"count": 0})
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.context["pickup_form"].errors)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, S.PICKUP_ASSIGNED)
