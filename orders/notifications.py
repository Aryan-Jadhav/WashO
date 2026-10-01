"""Email the customer when their order is booked or its status changes.

Sent with transaction.on_commit(), so an email only goes out if the change was
really saved. In development the console backend prints emails in the terminal.
"""
import logging

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.urls import reverse

from .models import Order

log = logging.getLogger(__name__)
S = Order.Status

# Subject line + one friendly sentence for each status.
MESSAGES = {
    S.BOOKED: ("Pickup booked", "We've received your booking. Our agent will come in your chosen slot."),
    S.PICKUP_ASSIGNED: ("Agent assigned", "{agent} will pick up your clothes in your slot."),
    S.PICKED_UP: ("Clothes picked up", "We've collected {pickup_count} garments and they're on the way to our store."),
    S.AT_STORE: ("At our store", "Your clothes have reached {store}."),
    S.TAGGED: ("Final bill ready", "Every garment has been tagged ({garment_count} pieces). Your final bill is {total}."),
    S.IN_CLEANING: ("Cleaning started", "Your clothes are being cleaned."),
    S.READY: ("Ready for delivery", "Your clothes are clean, packed and ready."),
    S.OUT_FOR_DELIVERY: ("Out for delivery", "{agent} is on the way. Please keep {total} ready (cash or UPI)."),
    S.DELIVERED: ("Delivered. Thank you!", "Your order has been delivered. Your invoice is attached."),
    S.CANCELLED: ("Order cancelled", "Your order has been cancelled."),
}


def _context(order):
    from core.templatetags.money import format_inr

    agent = order.delivery_agent if order.status in (S.READY, S.OUT_FOR_DELIVERY, S.DELIVERED) else order.pickup_agent
    counts = {c.checkpoint: c.count for c in order.count_checks.all()}
    return {
        "agent": (agent.first_name or "Our agent") if agent else "Our agent",
        "pickup_count": counts.get("pickup", "your"),
        "garment_count": order.garments.count(),
        "store": order.store.name,
        "total": format_inr(order.total),
    }


def send_order_email(order_id, status):
    """Build and send the email for the status the order just moved to."""
    order = Order.objects.select_related("customer", "store", "pickup_slot__time_slot",
                                         "pickup_agent", "delivery_agent").get(pk=order_id)
    email = order.customer.email
    if not email:
        return False  # email is optional for customers
    subject_text, line = MESSAGES[S(status)]
    ctx = {
        "order": order,
        "customer": order.customer,
        "headline": subject_text,
        "message": line.format(**_context(order)),
        "order_url": settings.SITE_URL.rstrip("/") + reverse("orders:detail", args=[order.code]),
        "site_url": settings.SITE_URL,
    }
    msg = EmailMultiAlternatives(
        subject=f"WashO {order.code}: {subject_text}",
        body=render_to_string("emails/order_status.txt", ctx),
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[email],
    )
    msg.attach_alternative(render_to_string("emails/order_status.html", ctx), "text/html")
    if S(status) == S.DELIVERED and order.bill_finalised:
        from payments.invoice import build_invoice_pdf, invoice_number
        msg.attach(f"{invoice_number(order)}.pdf", build_invoice_pdf(order), "application/pdf")
    try:
        msg.send()
    except Exception:  # a mail server problem must never break an order update
        log.exception("Could not send status email for %s", order.code)
        return False
    return True
