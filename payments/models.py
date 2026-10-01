from django.conf import settings
from django.db import models
from django.db.models import Q


class Payment(models.Model):
    """Money collected for an order. WashO uses Cash on Delivery: the agent collects
    the final bill at the door, in cash or by UPI to the store's QR.

    WHY a separate table (not just a 'paid' tick on the order): it records who collected
    how much, how and when. That's needed to reconcile each agent's cash at the end
    of the day, and it leaves room for other payment methods later.
    """

    class Method(models.TextChoices):
        CASH = "cash", "Cash on delivery"
        UPI = "upi", "UPI on delivery"

    order = models.OneToOneField("orders.Order", on_delete=models.PROTECT, related_name="payment")
    method = models.CharField(max_length=10, choices=Method.choices)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    collected_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="collections")
    collected_at = models.DateTimeField(auto_now_add=True, db_index=True)
    reference = models.CharField(max_length=40, blank=True, help_text="UPI transaction ID (optional).")

    class Meta:
        ordering = ["-collected_at"]
        constraints = [
            models.CheckConstraint(condition=Q(amount__gt=0), name="payment_amount_positive"),
        ]
        indexes = [models.Index(fields=["collected_by", "collected_at"])]

    def __str__(self):
        return f"{self.order} · ₹{self.amount} · {self.get_method_display()}"
