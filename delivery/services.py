"""Delivery agent jobs: assigning agents, confirming pickups and deliveries with garment counts."""
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from accounts.roles import Role
from orders.models import Order
from orders.services import InvalidTransition, change_status
from payments.services import PaymentError, amount_due, record_collection
from tagging.models import CountCheck
from tagging.services import expected_count, record_count

S = Order.Status
CP = CountCheck.Checkpoint


class DeliveryError(Exception):
    """Shown to staff / agents as a message."""


def agents_for_store(store):
    """Active delivery agents who work at this store."""
    return get_user_model().objects.filter(groups__name=Role.AGENT, store=store, is_active=True) \
        .distinct().order_by("first_name", "phone")


def _locked(order):
    return Order.objects.select_for_update().get(pk=order.pk)


def _check_agent(order, agent):
    if agent is None or not agents_for_store(order.store).filter(pk=agent.pk).exists():
        raise DeliveryError("Choose a delivery agent who works at this order's store.")


# ------------------------------------------------------------- staff side ----


@transaction.atomic
def assign_pickup_agent(order, agent, by):
    """Booked -> Pickup Assigned (or change the agent before the pickup happens)."""
    order = _locked(order)
    if order.status not in (S.BOOKED, S.PICKUP_ASSIGNED):
        raise DeliveryError("The pickup agent can only be set before the clothes are picked up.")
    _check_agent(order, agent)
    order.pickup_agent = agent
    order.save(update_fields=["pickup_agent", "updated_at"])
    if order.status == S.BOOKED:
        order = change_status(order, S.PICKUP_ASSIGNED, by, note=f"Pickup agent: {agent.get_full_name() or agent.phone}")
    return order


@transaction.atomic
def assign_delivery_agent(order, agent, delivery_date, by):
    """Choose who delivers a Ready order, and on which day (status stays Ready)."""
    order = _locked(order)
    if order.status != S.READY:
        raise DeliveryError("A delivery agent can be assigned only when the order is Ready.")
    _check_agent(order, agent)
    if delivery_date < timezone.localdate():
        raise DeliveryError("The delivery date can't be in the past.")
    order.delivery_agent = agent
    order.delivery_date = delivery_date
    order.save(update_fields=["delivery_agent", "delivery_date", "updated_at"])
    return order


# ------------------------------------------------------------- agent side ----


def _check_own_job(order, agent, field):
    if getattr(order, f"{field}_id") != agent.pk:
        raise DeliveryError("This job is not assigned to you.")


@transaction.atomic
def confirm_pickup(order, agent, count, note=""):
    """At the customer's door: count the garments together, then take them."""
    order = _locked(order)
    _check_own_job(order, agent, "pickup_agent")
    if order.status != S.PICKUP_ASSIGNED:
        raise DeliveryError("This pickup is not waiting to be collected.")
    if count < 1:
        raise DeliveryError("Count at least 1 garment.")
    record_count(order, CP.PICKUP, count, agent, note)
    return change_status(order, S.PICKED_UP, agent, note=f"Picked up {count} garments" + (f" – {note}" if note else ""))


@transaction.atomic
def start_delivery(order, agent):
    """Agent has collected the packed order from the store."""
    order = _locked(order)
    _check_own_job(order, agent, "delivery_agent")
    if order.status != S.READY:
        raise DeliveryError("This order is not ready to leave the store.")
    return change_status(order, S.OUT_FOR_DELIVERY, agent, note="Collected from store for delivery")


@transaction.atomic
def confirm_delivery(order, agent, count, confirm_mismatch=False, note="", payment_method=None, reference=""):
    """At the customer's door: count the garments handed over and collect the bill (Cash on Delivery).

    A different count needs confirmation and raises a mismatch alert for admin. Count, payment and
    'Delivered' are saved in ONE transaction - all of them, or none.
    """
    order = _locked(order)
    _check_own_job(order, agent, "delivery_agent")
    if order.status != S.OUT_FOR_DELIVERY:
        raise DeliveryError("This order is not out for delivery.")
    expected = expected_count(order, CP.DELIVERY)
    if expected is not None and count != expected and not confirm_mismatch:
        raise DeliveryError(
            f"The store tagged {expected} garments but you counted {count}. Count again with the customer; "
            "if it is really different, tick the confirmation box (admin will be alerted)."
        )
    due = amount_due(order)
    if due > 0 and not payment_method:
        raise DeliveryError(f"Collect ₹{due} from the customer (cash or UPI) and tick 'Payment collected'.")
    record_count(order, CP.DELIVERY, count, agent, note)
    if due > 0:
        try:
            record_collection(order, agent, payment_method, reference)
        except PaymentError as e:
            raise DeliveryError(str(e))
    return change_status(order, S.DELIVERED, agent, note=f"Delivered {count} garments" + (f" – {note}" if note else ""))


def agent_jobs(agent, day=None):
    """The agent's work for a day: pickups (by slot date) and deliveries (by delivery date).

    Overdue jobs from earlier days are included so nothing is forgotten.
    """
    day = day or timezone.localdate()
    base = Order.objects.select_related("customer", "pickup_slot__time_slot", "store")
    pickups = base.filter(pickup_agent=agent, status=S.PICKUP_ASSIGNED, pickup_slot__date__lte=day) \
        .order_by("pickup_slot__date", "pickup_slot__time_slot__start_time")
    deliveries = base.filter(delivery_agent=agent, status__in=[S.READY, S.OUT_FOR_DELIVERY],
                             delivery_date__lte=day).order_by("delivery_date", "status", "code")
    to_store = base.filter(pickup_agent=agent, status=S.PICKED_UP).order_by("updated_at")
    return pickups, deliveries, to_store
