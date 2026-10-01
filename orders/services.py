"""Business rules for slots, booking and order status.

Views call these functions; they never change orders directly. Keeping the
rules in one place makes them testable and stops two screens from behaving
differently.
"""
import datetime

from django.db import connection, transaction
from django.db.models import F
from django.utils import timezone

from .models import Coupon, DailySlot, Order, OrderItem, TimeSlot
from .pricing import build_quote

S = Order.Status

MAX_DAYS_AHEAD = 7  # customers can book up to a week ahead
MIN_LEAD_MINUTES = 60  # a slot starting in less than an hour can't be booked

# Which status may follow which. Anything not listed here is rejected.
ALLOWED_TRANSITIONS = {
    S.BOOKED: {S.PICKUP_ASSIGNED, S.CANCELLED},
    S.PICKUP_ASSIGNED: {S.PICKED_UP, S.CANCELLED},
    S.PICKED_UP: {S.AT_STORE},
    S.AT_STORE: {S.TAGGED},
    S.TAGGED: {S.IN_CLEANING},
    S.IN_CLEANING: {S.READY},
    S.READY: {S.OUT_FOR_DELIVERY},
    S.OUT_FOR_DELIVERY: {S.DELIVERED},
    S.DELIVERED: set(),
    S.CANCELLED: set(),
}
# Cancelling is only possible before the clothes leave the customer's home.
CANCELLABLE_STATUSES = {S.BOOKED, S.PICKUP_ASSIGNED}
# The normal happy path, used for progress bars and the admin "next status" action.
STATUS_FLOW = [S.BOOKED, S.PICKUP_ASSIGNED, S.PICKED_UP, S.AT_STORE, S.TAGGED,
               S.IN_CLEANING, S.READY, S.OUT_FOR_DELIVERY, S.DELIVERED]


class BookingError(Exception):
    """A booking can't be made; the message is safe to show to the customer."""


class InvalidTransition(Exception):
    pass


# ---------------------------------------------------------------- slots ----


def bookable_dates(today=None):
    today = today or timezone.localdate()
    return [today + datetime.timedelta(days=i) for i in range(MAX_DAYS_AHEAD + 1)]


def slot_is_in_future(date, time_slot, now=None):
    now = timezone.localtime(now or timezone.now())
    start = timezone.make_aware(datetime.datetime.combine(date, time_slot.start_time))
    return start - now >= datetime.timedelta(minutes=MIN_LEAD_MINUTES)


def check_slot_bookable(date, time_slot, now=None):
    now = now or timezone.now()
    today = timezone.localdate(now)
    if not time_slot.is_active:
        raise BookingError("This time slot is not available.")
    if date < today or date > today + datetime.timedelta(days=MAX_DAYS_AHEAD):
        raise BookingError(f"Please choose a date within the next {MAX_DAYS_AHEAD} days.")
    if not slot_is_in_future(date, time_slot, now):
        raise BookingError("This time slot has already started or is too soon. Please pick a later slot.")


def slot_availability(date, area, now=None):
    """For the booking page: every active slot with places left, full / past flags."""
    booked = dict(
        DailySlot.objects.filter(date=date, area=area).values_list("time_slot_id", "booked_count")
    )
    result = []
    for slot in TimeSlot.objects.filter(is_active=True):
        remaining = max(slot.capacity - booked.get(slot.pk, 0), 0)
        result.append({
            "slot": slot,
            "remaining": remaining,
            "is_full": remaining == 0,
            "is_past": not slot_is_in_future(date, slot, now),
        })
    return result


def reserve_slot(date, time_slot, area):
    """Take one place in the slot or raise BookingError if it is full.

    Must run inside a transaction. select_for_update() locks the counter row,
    so concurrent bookings for the same slot queue up one after another.
    """
    daily, _ = DailySlot.objects.select_for_update().get_or_create(date=date, time_slot=time_slot, area=area)
    if daily.booked_count >= time_slot.capacity:
        raise BookingError("Sorry, this slot just got full. Please choose another time.")
    daily.booked_count = F("booked_count") + 1  # done by the DB: no lost updates
    daily.save(update_fields=["booked_count"])
    daily.refresh_from_db()
    return daily


def release_slot(daily_slot):
    DailySlot.objects.filter(pk=daily_slot.pk, booked_count__gt=0).update(booked_count=F("booked_count") - 1)


# --------------------------------------------------------------- status ----


def _set_audit_context(user, note=""):
    """Tell the PostgreSQL trigger WHO is making the change (see migration 0002).

    set_config(..., true) lasts only until the end of the current transaction.
    """
    with connection.cursor() as cur:
        cur.execute(
            "SELECT set_config('washo.changed_by', %s, true), set_config('washo.status_note', %s, true)",
            [str(user.pk) if user else "", note or ""],
        )


@transaction.atomic
def change_status(order, new_status, by, note=""):
    """The ONLY way order status changes. Validates the move; the DB trigger logs it."""
    order = Order.objects.select_for_update().get(pk=order.pk)  # stop two people changing it at once
    new_status = S(new_status)
    if new_status == S.CANCELLED and order.status not in CANCELLABLE_STATUSES:
        raise InvalidTransition("This order can't be cancelled because the clothes have already been picked up.")
    if new_status not in ALLOWED_TRANSITIONS[S(order.status)]:
        raise InvalidTransition(f"Can't change status from {order.get_status_display()} to {new_status.label}.")
    # Someone must be responsible for the trip before it starts.
    if new_status == S.PICKUP_ASSIGNED and not order.pickup_agent_id:
        raise InvalidTransition("Assign a pickup agent first (Staff panel → order → Assign pickup agent).")
    if new_status == S.OUT_FOR_DELIVERY and not order.delivery_agent_id:
        raise InvalidTransition("Assign a delivery agent first (Staff panel → order → Assign delivery agent).")

    _set_audit_context(by, note)
    order.status = new_status
    order.save(update_fields=["status", "updated_at"])

    if new_status == S.CANCELLED:
        release_slot(order.pickup_slot)  # give the pickup place back to other customers
    return order


def cancel_order(order, by, reason=""):
    # The "can it still be cancelled?" check happens inside change_status, on the locked row.
    return change_status(order, S.CANCELLED, by, reason or "Cancelled by customer")


def next_status(order):
    """Next status on the normal path (or None at the end)."""
    try:
        i = STATUS_FLOW.index(S(order.status))
    except ValueError:
        return None
    return STATUS_FLOW[i + 1] if i + 1 < len(STATUS_FLOW) else None


# -------------------------------------------------------------- booking ----


@transaction.atomic
def create_order(*, customer, address, pickup_date, time_slot, selected_items, is_express=False,
                 coupon_code="", note="", now=None):
    """Create an order: reserve the slot, check the coupon, copy prices, save everything.

    Everything is in ONE transaction: if any step fails (slot full, coupon used
    up), nothing is saved and the slot place is not taken.
    """
    if address.user_id != customer.pk or not address.is_active:
        raise BookingError("Please choose one of your saved addresses.")
    if not any(qty > 0 for _, qty in selected_items):
        raise BookingError("Please add at least one item.")

    check_slot_bookable(pickup_date, time_slot, now)
    daily_slot = reserve_slot(pickup_date, time_slot, address.area)

    coupon_code = (coupon_code or "").strip().upper()
    if coupon_code:
        # Lock the coupon so its usage limit can't be exceeded by simultaneous bookings.
        Coupon.objects.select_for_update().filter(code=coupon_code).first()
    quote = build_quote(selected_items, is_express, coupon_code, customer, timezone.localdate(now))
    if quote.coupon_error:
        raise BookingError(quote.coupon_error)

    _set_audit_context(customer, "Order placed")
    order = Order.objects.create(
        customer=customer, address=address, address_snapshot=address.one_line(),
        store=address.area.store, pickup_slot=daily_slot, is_express=is_express,
        coupon=quote.coupon, customer_note=note,
        estimated_total=quote.total, subtotal=quote.subtotal, express_charge=quote.express_charge,
        discount=quote.discount, total=quote.total,
    )
    OrderItem.objects.bulk_create([
        OrderItem(order=order, category=line.category, item=line.item, quantity=line.quantity,
                  unit_price=line.unit_price, express_surcharge=line.express_surcharge(is_express))
        for line in quote.lines
    ])
    order.code = f"WO-{order.pk:06d}"
    order.save(update_fields=["code"])
    return order

