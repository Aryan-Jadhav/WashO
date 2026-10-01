import datetime

from django.contrib import messages
from django.db.models import Count, Sum
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from accounts.permissions import role_required
from accounts.roles import Role
from orders.models import Order
from orders.services import InvalidTransition
from tagging.models import CountCheck
from tagging.services import expected_count
from tagging.views import PANEL_ROLES, visible_orders

from payments.models import Payment
from payments.services import amount_due

from .forms import AssignDeliveryForm, AssignPickupForm, DeliveryCountForm, PickupCountForm
from .services import (DeliveryError, agent_jobs, assign_delivery_agent, assign_pickup_agent, confirm_delivery,
                       confirm_pickup, start_delivery)

S = Order.Status
CP = CountCheck.Checkpoint


# ---------------------------------------------------- staff: assign agents ----


@role_required(*PANEL_ROLES)
@require_POST
def assign_pickup(request, code):
    order = get_object_or_404(visible_orders(request.user), code=code)
    form = AssignPickupForm(request.POST, order=order)
    if form.is_valid():
        try:
            assign_pickup_agent(order, form.cleaned_data["agent"], request.user)
            messages.success(request, f"Pickup agent assigned for {order.code}.")
        except (DeliveryError, InvalidTransition) as e:
            messages.error(request, str(e))
    else:
        messages.error(request, "Please choose a pickup agent.")
    return redirect("tagging:order", code=code)


@role_required(*PANEL_ROLES)
@require_POST
def assign_delivery(request, code):
    order = get_object_or_404(visible_orders(request.user), code=code)
    form = AssignDeliveryForm(request.POST, order=order)
    if form.is_valid():
        try:
            assign_delivery_agent(order, form.cleaned_data["agent"], form.cleaned_data["delivery_date"], request.user)
            messages.success(request, f"Delivery agent assigned for {order.code}.")
        except DeliveryError as e:
            messages.error(request, str(e))
    else:
        messages.error(request, " ".join(e for errs in form.errors.values() for e in errs))
    return redirect("tagging:order", code=code)


# ------------------------------------------------------- agent: my jobs ----


@role_required(Role.AGENT)
def my_jobs(request):
    today = timezone.localdate()
    try:
        day = datetime.date.fromisoformat(request.GET.get("day", ""))
    except ValueError:
        day = today
    pickups, deliveries, to_store = agent_jobs(request.user, day)
    done_today = Order.objects.filter(
        history__changed_by=request.user, history__to_status__in=[S.PICKED_UP, S.DELIVERED],
        history__changed_at__date=today,
    ).distinct().count()
    # For handing over the day's cash at the store.
    collected = Payment.objects.filter(collected_by=request.user, collected_at__date=today) \
        .values("method").annotate(total=Sum("amount"), n=Count("id"))
    return render(request, "delivery/my_jobs.html", {
        "pickups": pickups, "deliveries": deliveries, "to_store": to_store, "done_today": done_today,
        "collected": {row["method"]: row for row in collected},
        "day": day, "today": today,
        "prev_day": day - datetime.timedelta(days=1), "next_day": day + datetime.timedelta(days=1),
        "no_store": not request.user.store_id,
    })


def _my_order(request, code):
    """Agents can open only orders where they are the pickup or delivery agent."""
    qs = Order.objects.select_related("customer", "store", "pickup_slot__time_slot")
    order = get_object_or_404(qs, code=code)
    if request.user.pk not in (order.pickup_agent_id, order.delivery_agent_id):
        raise Http404("Not your job")  # same "not found" page as a wrong order number
    return order


@role_required(Role.AGENT)
def job(request, code, pickup_form=None, delivery_form=None):
    order = _my_order(request, code)
    counts = {c.checkpoint: c.count for c in order.count_checks.all()}
    return render(request, "delivery/job.html", {
        "order": order,
        "items": order.items.select_related("category", "item"),
        "is_pickup": order.pickup_agent_id == request.user.pk and order.status == S.PICKUP_ASSIGNED,
        "is_delivery": order.delivery_agent_id == request.user.pk and order.status in (S.READY, S.OUT_FOR_DELIVERY),
        "pickup_form": pickup_form or PickupCountForm(),
        "delivery_form": delivery_form or DeliveryCountForm(amount_due=amount_due(order)),
        "amount_due": amount_due(order),
        "store_count": counts.get(CP.STORE),
        "pickup_count": counts.get(CP.PICKUP),
        "expected_delivery": expected_count(order, CP.DELIVERY),
    })


@role_required(Role.AGENT)
@require_POST
def job_pickup(request, code):
    order = _my_order(request, code)
    form = PickupCountForm(request.POST)
    if form.is_valid():
        try:
            confirm_pickup(order, request.user, form.cleaned_data["count"], form.cleaned_data["note"])
            messages.success(request, f"Picked up {form.cleaned_data['count']} garments for {order.code}. "
                                      f"Take them to {order.store.name}.")
            return redirect("delivery:my_jobs")
        except DeliveryError as e:
            form.add_error(None, str(e))
    return job(request, code, pickup_form=form)


@role_required(Role.AGENT)
@require_POST
def job_start_delivery(request, code):
    order = _my_order(request, code)
    try:
        start_delivery(order, request.user)
        messages.success(request, f"{order.code} is out for delivery.")
    except DeliveryError as e:
        messages.error(request, str(e))
    return redirect("delivery:job", code=code)


@role_required(Role.AGENT)
@require_POST
def job_deliver(request, code):
    order = _my_order(request, code)
    form = DeliveryCountForm(request.POST, amount_due=amount_due(order))
    if form.is_valid():
        d = form.cleaned_data
        try:
            confirm_delivery(order, request.user, d["count"], d["confirm_mismatch"], d["note"],
                             payment_method=d["payment_method"] or None, reference=d["reference"])
            messages.success(request, f"{order.code} delivered. Thank you!")
            if order.mismatch_alerts.filter(checkpoint=CP.DELIVERY, status="open").exists():
                messages.warning(request, "The count was different from the store count. Admin has been alerted.")
            return redirect("delivery:my_jobs")
        except DeliveryError as e:
            form.add_error(None, str(e))
    return job(request, code, delivery_form=form)
