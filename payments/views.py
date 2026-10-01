from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404

from accounts.roles import Role
from orders.models import Order
from tagging.views import visible_orders

from .invoice import build_invoice_pdf, invoice_number


def can_view_order(user, order):
    """The customer who owns the order, staff of its store, or admin."""
    if order.customer_id == user.pk:
        return True
    return visible_orders(user).filter(pk=order.pk).exists() if user.has_role(Role.STAFF, Role.ADMIN) else False


@login_required
def invoice_pdf(request, code):
    order = get_object_or_404(Order.objects.select_related("customer", "store__city", "pickup_slot__time_slot",
                                                           "coupon"), code=code)
    if not can_view_order(request.user, order):
        raise Http404  # don't reveal that the order exists
    if not order.bill_finalised:
        raise Http404("The invoice is available once the store has tagged your garments.")
    pdf = build_invoice_pdf(order)
    response = HttpResponse(pdf, content_type="application/pdf")
    # inline = open in the browser's PDF viewer; ?download=1 saves the file instead
    mode = "attachment" if request.GET.get("download") else "inline"
    response["Content-Disposition"] = f'{mode}; filename="{invoice_number(order)}.pdf"'
    return response
