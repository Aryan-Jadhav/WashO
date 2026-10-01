from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from accounts.permissions import role_required
from delivery.forms import AssignDeliveryForm, AssignPickupForm
from accounts.roles import Role
from core.htmx import is_htmx, vary_on_htmx
from orders.models import Order
from orders.services import InvalidTransition
from stores.models import Store

from .forms import FinishTaggingForm, GarmentEditForm, GarmentForm, ResolveAlertForm
from .models import CountCheck, Garment, MismatchAlert
from .services import (EDITABLE_STATUSES, STAFF_STEPS, TaggingError, add_garment, expected_count, finish_tagging,
                       remove_garment, resolve_alert, staff_step)

S = Order.Status
PANEL_ROLES = (Role.STAFF, Role.ADMIN)

# Queue tabs on the staff panel: tab -> (title, statuses)
TABS = {
    "incoming": ("Incoming", [S.BOOKED, S.PICKUP_ASSIGNED, S.PICKED_UP]),
    "tagging": ("To tag", [S.AT_STORE]),
    "cleaning": ("In process", [S.TAGGED, S.IN_CLEANING]),
    "ready": ("Ready / out", [S.READY, S.OUT_FOR_DELIVERY]),
    "done": ("Delivered", [S.DELIVERED]),
}


def visible_orders(user):
    """Admin sees every store; staff see only their own store. (Role check on every view.)"""
    qs = Order.objects.select_related("customer", "store", "pickup_slot__time_slot", "pickup_agent", "delivery_agent")
    if user.has_role(Role.ADMIN):
        return qs
    if user.store_id:
        return qs.filter(store_id=user.store_id)
    return qs.none()


def _get_order(request, code):
    return get_object_or_404(visible_orders(request.user), code=code)


@role_required(*PANEL_ROLES)
def panel(request):
    is_admin = request.user.has_role(Role.ADMIN)
    tab = request.GET.get("tab", "tagging")
    if tab not in TABS:
        tab = "tagging"
    base = visible_orders(request.user)

    store = None
    if is_admin and request.GET.get("store"):
        store = Store.objects.filter(slug=request.GET["store"]).first()
        if store:
            base = base.filter(store=store)

    q = request.GET.get("q", "").strip()[:30]
    orders = base.filter(status__in=TABS[tab][1])
    if q:
        orders = base.filter(Q(code__icontains=q) | Q(customer__phone__contains=q)
                             | Q(customer__first_name__icontains=q))
    orders = orders.annotate(garment_count=Count("garments")).order_by("pickup_slot__date", "created_at")

    counts = {key: base.filter(status__in=statuses).count() for key, (_, statuses) in TABS.items()}
    return render(request, "tagging/panel.html", {
        "tabs": [(key, title, counts[key]) for key, (title, _) in TABS.items()],
        "tab": tab, "q": q,
        "page": Paginator(orders, 20).get_page(request.GET.get("page")),
        "stores": Store.objects.filter(is_active=True) if is_admin else None,
        "store": store,
        "no_store": not is_admin and not request.user.store_id,
        "open_alerts": MismatchAlert.objects.filter(status=MismatchAlert.Status.OPEN,
                                                    order__in=base).count(),
    })


def _order_context(request, order, garment_form=None, finish_form=None):
    counts = {c.checkpoint: c for c in order.count_checks.all()}
    garments = order.garments.select_related("category", "item", "tagged_by")
    return {
        "order": order,
        "items": order.items.select_related("category", "item"),
        "garments": garments,
        "counts": [(cp, cp.label, counts.get(cp.value)) for cp in CountCheck.Checkpoint],
        "expected_store_count": expected_count(order, CountCheck.Checkpoint.STORE),
        "alerts": order.mismatch_alerts.all(),
        "garment_form": garment_form or GarmentForm(order=order),
        "finish_form": finish_form or FinishTaggingForm(),
        "step": STAFF_STEPS.get(S(order.status)),
        "can_tag": order.status == S.AT_STORE,
        # Agent assignment (Phase 5): pickup before collection, delivery once Ready.
        "pickup_form": AssignPickupForm(order=order, initial={"agent": order.pickup_agent})
        if order.status in (S.BOOKED, S.PICKUP_ASSIGNED) else None,
        "delivery_form": AssignDeliveryForm(order=order, initial={"agent": order.delivery_agent})
        if order.status == S.READY else None,
        "can_edit": order.status in EDITABLE_STATUSES,
    }


@role_required(*PANEL_ROLES)
def order_detail(request, code):
    order = _get_order(request, code)
    return render(request, "tagging/order.html", _order_context(request, order))


@role_required(*PANEL_ROLES)
@require_POST
def order_step(request, code):
    order = _get_order(request, code)
    try:
        order = staff_step(order, request.user)
        messages.success(request, f"{order.code} is now {order.get_status_display()}.")
    except InvalidTransition as e:
        messages.error(request, str(e))
    return redirect("tagging:order", code=code)


@role_required(*PANEL_ROLES)
@require_POST
def garment_add(request, code):
    """Tag one garment. With HTMX only the tagging area is replaced, so staff can tag quickly."""
    order = _get_order(request, code)
    form = GarmentForm(request.POST, request.FILES, order=order)
    just_tagged = None
    if form.is_valid():
        d = form.cleaned_data
        try:
            g = add_garment(order, d["service_price"], request.user, d["description"], d["has_stain"],
                            d["has_damage"], d["condition_note"], d["photo"])
            if not is_htmx(request):
                messages.success(request, f"Tagged {g.tag_code} · {g.item.name}")
            just_tagged = g
            form = None  # fresh empty form for the next garment
        except TaggingError as e:
            form.add_error(None, str(e))
    order.refresh_from_db()
    ctx = _order_context(request, order, garment_form=form)
    ctx["just_tagged"] = just_tagged
    if is_htmx(request):
        return vary_on_htmx(render(request, "tagging/_tagging_area.html", ctx))
    if form is None:
        return redirect("tagging:order", code=code)
    return render(request, "tagging/order.html", ctx)


@role_required(*PANEL_ROLES)
def garment_edit(request, code, seq):
    order = _get_order(request, code)
    garment = get_object_or_404(order.garments, seq=seq)
    if order.status not in EDITABLE_STATUSES:
        messages.error(request, "Garments can't be changed once the order is ready.")
        return redirect("tagging:order", code=code)
    form = GarmentEditForm(request.POST or None, request.FILES or None, instance=garment)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, f"{garment.tag_code} updated.")
        return redirect("tagging:order", code=code)
    return render(request, "tagging/garment_edit.html", {"form": form, "garment": garment, "order": order})


@role_required(*PANEL_ROLES)
@require_POST
def garment_delete(request, code, seq):
    order = _get_order(request, code)
    garment = get_object_or_404(order.garments, seq=seq)
    try:
        remove_garment(garment)
        messages.success(request, f"Removed {garment.tag_code}. (Tag numbers already printed stay unused.)")
    except TaggingError as e:
        messages.error(request, str(e))
    return redirect("tagging:order", code=code)


@role_required(*PANEL_ROLES)
@require_POST
def tagging_finish(request, code):
    order = _get_order(request, code)
    form = FinishTaggingForm(request.POST)
    form.is_valid()
    try:
        order = finish_tagging(order, request.user, form.cleaned_data.get("confirm_mismatch", False))
    except TaggingError as e:
        messages.error(request, str(e))
        return render(request, "tagging/order.html", _order_context(request, order, finish_form=form))
    messages.success(request, f"Tagging finished: {order.garments.count()} garments. Final bill ₹{order.total}.")
    if order.mismatch_alerts.filter(status=MismatchAlert.Status.OPEN).exists():
        messages.warning(request, "The count differs from the pickup count. Admin has been alerted.")
    return redirect("tagging:order", code=code)


@role_required(*PANEL_ROLES)
def tags_print(request, code):
    order = _get_order(request, code)
    garments = order.garments.select_related("category", "item")
    if not garments:
        raise Http404("No garments tagged yet")
    return render(request, "tagging/tags_print.html", {"order": order, "garments": garments})


@role_required(*PANEL_ROLES)
def garment_lookup(request, tag_code=None):
    """Opened by scanning a garment's QR code (or typing the tag code)."""
    tag_code = (tag_code or request.GET.get("code", "")).strip().upper()
    garment = None
    if tag_code:
        garment = Garment.objects.select_related("order__customer", "order__store", "category", "item",
                                                 "tagged_by").filter(tag_code=tag_code,
                                                                     order__in=visible_orders(request.user)).first()
        if garment is None:
            messages.error(request, f"No garment with tag {tag_code} in your store.")
    return render(request, "tagging/garment_lookup.html", {"garment": garment, "tag_code": tag_code})


# ------------------------------------------------------------- admin only ----


@role_required(Role.ADMIN)
def alerts(request):
    show = request.GET.get("show", "open")
    qs = MismatchAlert.objects.select_related("order__store", "order__customer", "resolved_by")
    qs = qs.filter(status=MismatchAlert.Status.OPEN) if show == "open" else qs.filter(status=MismatchAlert.Status.RESOLVED)
    return render(request, "tagging/alerts.html", {
        "page": Paginator(qs, 20).get_page(request.GET.get("page")),
        "show": show,
        "form": ResolveAlertForm(),
    })


@role_required(Role.ADMIN)
@require_POST
def alert_resolve(request, pk):
    alert = get_object_or_404(MismatchAlert, pk=pk, status=MismatchAlert.Status.OPEN)
    form = ResolveAlertForm(request.POST)
    if form.is_valid():
        resolve_alert(alert, request.user, form.cleaned_data["resolution_note"])
        messages.success(request, f"Alert for {alert.order.code} resolved.")
    else:
        messages.error(request, "Please write how the mismatch was resolved.")
    return redirect("tagging:alerts")
