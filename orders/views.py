import datetime

from django.contrib import messages
from django.core.paginator import Paginator
from django.http import HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from accounts.permissions import role_required
from accounts.roles import Role

from .forms import BookingForm, CancelOrderForm, EstimateForm
from .models import Order
from .services import (STATUS_FLOW, BookingError, InvalidTransition, bookable_dates, cancel_order,
                       create_order, slot_availability)


def _default_pickup_date(area):
    """Today if a slot is still bookable today, otherwise tomorrow."""
    today = timezone.localdate()
    if area and any(not s["is_past"] and not s["is_full"] for s in slot_availability(today, area)):
        return today
    return today + datetime.timedelta(days=1)


@role_required(Role.CUSTOMER)
def book(request):
    addresses = request.user.addresses.filter(is_active=True)
    if not addresses.exists():
        messages.info(request, "First, add the address we should pick up from.")
        return redirect(f"{reverse('accounts:address_create')}?next={reverse('orders:book')}")

    if request.method == "POST":
        form = BookingForm(request.POST, user=request.user)
        if form.is_valid():
            d = form.cleaned_data
            try:
                order = create_order(
                    customer=request.user, address=d["address"], pickup_date=d["pickup_date"],
                    time_slot=d["time_slot"], selected_items=form.selected_items(),
                    is_express=d["is_express"], coupon_code=d["coupon_code"], note=d["note"],
                )
            except BookingError as e:
                # e.g. the slot filled up between page load and submit
                form.add_error(None, str(e))
            else:
                messages.success(request, f"Pickup booked! Your order number is {order.code}.")
                return redirect("orders:detail", code=order.code)
        address = form.cleaned_data.get("address") if hasattr(form, "cleaned_data") else None
        selected_date = form.cleaned_data.get("pickup_date") if hasattr(form, "cleaned_data") else None
        selected_slot = request.POST.get("time_slot")
    else:
        address = addresses.filter(is_default=True).first() or addresses.first()
        selected_date = _default_pickup_date(address.area)
        form = BookingForm(user=request.user, initial={"address": address, "pickup_date": selected_date.isoformat()})
        selected_slot = None

    address = address or addresses.first()
    selected_date = selected_date or _default_pickup_date(address.area)
    if hasattr(form, "cleaned_data"):
        quote = form.quote()
    else:
        quote = EstimateForm(user=request.user).quote()

    return render(request, "orders/book.html", {
        "form": form,
        "quote": quote,
        "slots": slot_availability(selected_date, address.area),
        "selected_slot": str(selected_slot or ""),
    })


@role_required(Role.CUSTOMER)
@require_POST
def book_estimate(request):
    """HTMX: re-calculate the price summary while the customer fills the form."""
    form = EstimateForm(request.POST, user=request.user)
    form.is_valid()  # fills cleaned_data for the valid fields; errors are shown in the summary
    return render(request, "orders/_estimate.html", {"quote": form.quote(), "form": form})


@role_required(Role.CUSTOMER)
def slot_options(request):
    """HTMX: slot buttons for the chosen date + address, with places left."""
    address = get_object_or_404(request.user.addresses.filter(is_active=True), pk=request.GET.get("address"))
    try:
        date = datetime.date.fromisoformat(request.GET.get("pickup_date", ""))
    except ValueError:
        return HttpResponseBadRequest("Invalid date")
    if date not in bookable_dates():
        return HttpResponseBadRequest("Date out of range")
    return render(request, "orders/_slot_options.html", {
        "slots": slot_availability(date, address.area),
        "selected_slot": request.GET.get("time_slot", ""),
    })


# ------------------------------------------------------------ my orders ----


def _my_orders(user):
    return Order.objects.filter(customer=user).select_related("pickup_slot__time_slot", "store")


@role_required(Role.CUSTOMER)
def order_list(request):
    show = request.GET.get("show", "active")
    orders = _my_orders(request.user)
    closed = [Order.Status.DELIVERED, Order.Status.CANCELLED]
    orders = orders.filter(status__in=closed) if show == "past" else orders.exclude(status__in=closed)
    page = Paginator(orders, 10).get_page(request.GET.get("page"))
    return render(request, "orders/order_list.html", {"page": page, "show": show})


def _status_context(order):
    """Data for the progress bar + timeline."""
    history = list(order.history.select_related("changed_by"))
    reached = {h.to_status for h in history}
    steps = [{"status": s, "label": s.label, "done": s.value in reached, "current": s.value == order.status}
             for s in STATUS_FLOW]
    return {"order": order, "history": history, "steps": steps}


@role_required(Role.CUSTOMER)
def order_detail(request, code):
    # Filtering by customer: other people's orders give 404, not someone's private data.
    order = get_object_or_404(_my_orders(request.user).prefetch_related("items__category", "items__item"),
                              code=code)
    ctx = _status_context(order)
    ctx["cancel_form"] = CancelOrderForm()
    # Transparency: the customer sees every garment we tagged and the count at each step.
    ctx["garments"] = order.garments.select_related("category", "item")
    ctx["count_checks"] = order.count_checks.all()
    return render(request, "orders/order_detail.html", ctx)


@role_required(Role.CUSTOMER)
def order_status_partial(request, code):
    """HTMX polling: the status block refreshes itself every few seconds (live status)."""
    order = get_object_or_404(_my_orders(request.user), code=code)
    return render(request, "orders/_order_status.html", _status_context(order))


@role_required(Role.CUSTOMER)
@require_POST
def order_cancel(request, code):
    order = get_object_or_404(_my_orders(request.user), code=code)
    form = CancelOrderForm(request.POST)
    reason = form.cleaned_data["reason"] if form.is_valid() else ""
    try:
        cancel_order(order, by=request.user, reason=reason)
    except InvalidTransition as e:
        messages.error(request, str(e))
    else:
        messages.success(request, f"Order {order.code} has been cancelled.")
    return redirect("orders:detail", code=order.code)
