"""Garment tagging, count checks, mismatch alerts and the final bill."""
from decimal import Decimal

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.db import transaction
from django.db.models import Max, Q, Sum
from django.urls import reverse
from django.utils import timezone

from accounts.roles import Role
from orders.models import Order, money
from orders.services import InvalidTransition, change_status

from .models import CountCheck, Garment, MismatchAlert

S = Order.Status
CP = CountCheck.Checkpoint
MAX_GARMENTS_PER_ORDER = 300

# Each count is compared with the count at the step before it.
PREVIOUS_CHECKPOINT = {CP.STORE: CP.PICKUP, CP.DELIVERY: CP.STORE}

# Garment details (stain, photo...) can be corrected until the order is ready.
EDITABLE_STATUSES = {S.AT_STORE, S.TAGGED, S.IN_CLEANING}


class TaggingError(Exception):
    """Shown to staff as a message."""


# ---------------------------------------------------------------- garments ----


def _locked(order):
    return Order.objects.select_for_update().get(pk=order.pk)


def price_for(order, service_price):
    """Unit price + express surcharge for a garment.

    If the customer booked this exact service + item, use the booking price (what they
    were shown). Otherwise use today's price list.
    """
    booked = order.items.filter(category=service_price.category, item=service_price.item).first()
    if booked:
        return booked.unit_price, booked.express_surcharge
    base = service_price.unit_price()
    extra = service_price.unit_price(express=True) - base if order.is_express else Decimal("0.00")
    return base, extra


@transaction.atomic
def add_garment(order, service_price, by, description="", has_stain=False, has_damage=False,
                condition_note="", photo=None):
    order = _locked(order)  # lock: two staff tagging the same order can't get the same number
    if order.status != S.AT_STORE:
        raise TaggingError("Garments can only be tagged while the order is At Store.")
    if (has_stain or has_damage) and not condition_note.strip():
        raise TaggingError("Please describe the stain or damage.")
    seq = (order.garments.aggregate(m=Max("seq"))["m"] or 0) + 1
    if seq > MAX_GARMENTS_PER_ORDER:
        raise TaggingError(f"An order can have at most {MAX_GARMENTS_PER_ORDER} garments.")
    unit_price, surcharge = price_for(order, service_price)
    return Garment.objects.create(
        order=order, seq=seq, tag_code=f"{order.code}-{seq:02d}",
        category=service_price.category, item=service_price.item,
        unit_price=unit_price, express_surcharge=surcharge, description=description.strip(),
        has_stain=has_stain, has_damage=has_damage, condition_note=condition_note.strip(),
        photo=photo or "", tagged_by=by,
    )


@transaction.atomic
def remove_garment(garment):
    order = _locked(garment.order)
    if order.status != S.AT_STORE:
        raise TaggingError("Garments can only be removed before tagging is finished.")
    garment.delete()


# ------------------------------------------------------------ count checks ----


def _admin_emails():
    User = get_user_model()
    emails = User.objects.filter(Q(is_superuser=True) | Q(groups__name=Role.ADMIN), is_active=True) \
        .exclude(email="").values_list("email", flat=True).distinct()
    return list(emails) or [settings.SUPPORT_EMAIL]


def _notify_admin(alert):
    order = alert.order
    diff = alert.difference
    send_mail(
        subject=f"[WashO] Garment count mismatch on {order.code}",
        message=(
            f"Order {order.code} ({order.store.name}) - {alert.get_checkpoint_display()}\n"
            f"Expected {alert.expected_count} garments, counted {alert.actual_count} "
            f"({'+' if diff > 0 else ''}{diff}).\n\n"
            f"Please check: {reverse('tagging:alerts')}"
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=_admin_emails(),
        fail_silently=True,
    )


@transaction.atomic
def record_count(order, checkpoint, count, by, note=""):
    """Save the count for a checkpoint and raise an alert if it differs from the previous one.

    Returns (CountCheck, MismatchAlert or None).
    """
    checkpoint = CP(checkpoint)
    if count < 0:
        raise TaggingError("Count can't be negative.")
    check, _ = CountCheck.objects.update_or_create(
        order=order, checkpoint=checkpoint,
        defaults={"count": count, "recorded_by": by, "note": note},
    )

    alert = None
    prev_cp = PREVIOUS_CHECKPOINT.get(checkpoint)
    prev = CountCheck.objects.filter(order=order, checkpoint=prev_cp).first() if prev_cp else None
    if prev and prev.count != count:
        # Don't raise the same alert twice if the same wrong count is entered again.
        alert = MismatchAlert.objects.filter(order=order, checkpoint=checkpoint, status=MismatchAlert.Status.OPEN,
                                             expected_count=prev.count, actual_count=count).first()
        if alert is None:
            alert = MismatchAlert.objects.create(order=order, checkpoint=checkpoint,
                                                 expected_count=prev.count, actual_count=count)
            transaction.on_commit(lambda a=alert: _notify_admin(a))  # email only if the save succeeds
    return check, alert


def expected_count(order, checkpoint):
    """Count at the previous checkpoint (what we expect now), or None if not recorded."""
    prev_cp = PREVIOUS_CHECKPOINT.get(CP(checkpoint))
    prev = CountCheck.objects.filter(order=order, checkpoint=prev_cp).first() if prev_cp else None
    return prev.count if prev else None


@transaction.atomic
def resolve_alert(alert, by, note):
    if not note.strip():
        raise TaggingError("Please write how the mismatch was resolved.")
    alert.status = MismatchAlert.Status.RESOLVED
    alert.resolved_by = by
    alert.resolved_at = timezone.now()
    alert.resolution_note = note.strip()
    alert.save()


# ------------------------------------------------------------- final bill ----


def finalise_bill(order):
    """Replace the booking estimate with the bill for the garments actually tagged.

    The coupon (if any) is applied again on the new amount; if the order is now
    below the coupon's minimum value the discount becomes 0.
    """
    sums = order.garments.aggregate(sub=Sum("unit_price"), extra=Sum("express_surcharge"))
    order.subtotal = money(sums["sub"] or 0)
    order.express_charge = money(sums["extra"] or 0)
    gross = order.subtotal + order.express_charge
    order.discount = order.coupon.discount_for(gross) if order.coupon else Decimal("0.00")
    order.total = gross - order.discount
    order.bill_finalised = True
    order.save(update_fields=["subtotal", "express_charge", "discount", "total", "bill_finalised", "updated_at"])


@transaction.atomic
def finish_tagging(order, by, confirm_mismatch=False):
    """All garments tagged: record the store count, make the final bill, move to Tagged."""
    order = _locked(order)
    if order.status != S.AT_STORE:
        raise TaggingError("This order is not waiting to be tagged.")
    count = order.garments.count()
    if count == 0:
        raise TaggingError("Tag at least one garment first.")
    expected = expected_count(order, CP.STORE)
    if expected is not None and expected != count and not confirm_mismatch:
        raise TaggingError(
            f"The agent counted {expected} garments at pickup but {count} are tagged. "
            "Re-check the bag, then tick the confirmation box to continue (admin will be alerted)."
        )
    record_count(order, CP.STORE, count, by, note="Tagged garments")
    finalise_bill(order)
    return change_status(order, S.TAGGED, by, note=f"{count} garments tagged")


# ------------------------------------------------------------- store steps ----

# Simple one-click steps on the staff order page: current status -> (next status, button text)
STAFF_STEPS = {
    S.PICKED_UP: (S.AT_STORE, "Mark received at store"),
    S.TAGGED: (S.IN_CLEANING, "Start cleaning"),
    S.IN_CLEANING: (S.READY, "Mark ready for delivery"),
}


def staff_step(order, by):
    step = STAFF_STEPS.get(S(order.status))
    if step is None:
        raise InvalidTransition("There is no store action for this order right now.")
    return change_status(order, step[0], by, note=step[1])
