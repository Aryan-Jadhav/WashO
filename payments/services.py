"""Cash on Delivery collection."""
from django.db import transaction

from .models import Payment


class PaymentError(Exception):
    pass


def amount_due(order):
    """What the agent must collect: the final bill, unless already paid."""
    if hasattr(order, "payment"):
        return 0
    return order.total


@transaction.atomic
def record_collection(order, agent, method, reference=""):
    """Record that the agent collected the full bill. Runs inside the delivery transaction,
    so 'Delivered' and 'Paid' are saved together or not at all."""
    if Payment.objects.filter(order=order).exists():
        raise PaymentError("Payment for this order is already recorded.")
    if not order.bill_finalised:
        raise PaymentError("The final bill isn't ready yet.")
    if order.total <= 0:
        return None  # fully covered by a coupon: nothing to collect
    if method not in Payment.Method.values:
        raise PaymentError("Choose how the customer paid (cash or UPI).")
    return Payment.objects.create(order=order, method=method, amount=order.total, collected_by=agent,
                                  reference=reference.strip())
