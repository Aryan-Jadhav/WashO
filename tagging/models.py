from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

MAX_PHOTO_MB = 5


def validate_photo_size(f):
    if f.size > MAX_PHOTO_MB * 1024 * 1024:
        raise ValidationError(f"Photo is too large. Maximum size is {MAX_PHOTO_MB} MB.")


class Garment(models.Model):
    """ONE physical garment, tagged at the store with its own code + QR.

    WHY one row per garment (not just a count): we can show the customer exactly
    which pieces we received, note stains/damage on the right piece, and prove the
    count at every step. This is our answer to the "missing clothes" complaint.
    """

    order = models.ForeignKey("orders.Order", on_delete=models.PROTECT, related_name="garments")
    seq = models.PositiveSmallIntegerField(help_text="1, 2, 3 ... within the order.")
    tag_code = models.CharField(max_length=20, unique=True, help_text="Printed on the tag, e.g. WO-000012-03.")
    category = models.ForeignKey("catalog.ServiceCategory", on_delete=models.PROTECT)
    item = models.ForeignKey("catalog.Item", on_delete=models.PROTECT)
    # Price copied at tagging, so the final bill never changes afterwards.
    unit_price = models.DecimalField(max_digits=8, decimal_places=2)
    express_surcharge = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    description = models.CharField(max_length=120, blank=True, help_text="Colour / brand, e.g. 'Blue, Raymond'.")

    has_stain = models.BooleanField(default=False)
    has_damage = models.BooleanField(default=False)
    condition_note = models.CharField(max_length=300, blank=True,
                                      help_text="Where and what, e.g. 'Oil stain on left sleeve'.")
    photo = models.ImageField(upload_to="garments/%Y/%m/", blank=True, validators=[validate_photo_size])

    tagged_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+")
    tagged_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["order", "seq"]
        constraints = [
            models.UniqueConstraint(fields=["order", "seq"], name="unique_garment_seq_per_order"),
            # A stain or damage must always be explained, otherwise it can't be shown to the customer.
            models.CheckConstraint(
                condition=Q(has_stain=False, has_damage=False) | ~Q(condition_note=""),
                name="garment_issue_needs_note",
                violation_error_message="Please describe the stain or damage.",
            ),
        ]

    def __str__(self):
        return f"{self.tag_code} · {self.item}"

    @property
    def has_issue(self):
        return self.has_stain or self.has_damage

    @property
    def line_total(self):
        return self.unit_price + self.express_surcharge


class CountCheck(models.Model):
    """How many garments were counted at one checkpoint of an order."""

    class Checkpoint(models.TextChoices):
        PICKUP = "pickup", "At pickup"
        STORE = "store", "At store (tagged)"
        DELIVERY = "delivery", "At delivery"

    order = models.ForeignKey("orders.Order", on_delete=models.CASCADE, related_name="count_checks")
    checkpoint = models.CharField(max_length=10, choices=Checkpoint.choices)
    count = models.PositiveSmallIntegerField()
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+")
    recorded_at = models.DateTimeField(auto_now=True)
    note = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ["order", "recorded_at"]
        constraints = [
            models.UniqueConstraint(fields=["order", "checkpoint"], name="one_count_per_checkpoint"),
        ]

    def __str__(self):
        return f"{self.order} · {self.get_checkpoint_display()}: {self.count}"


class MismatchAlert(models.Model):
    """Raised automatically when a count differs from the previous checkpoint."""

    class Status(models.TextChoices):
        OPEN = "open", "Open"
        RESOLVED = "resolved", "Resolved"

    order = models.ForeignKey("orders.Order", on_delete=models.CASCADE, related_name="mismatch_alerts")
    checkpoint = models.CharField(max_length=10, choices=CountCheck.Checkpoint.choices,
                                  help_text="Where the difference was found.")
    expected_count = models.PositiveSmallIntegerField(help_text="Count at the previous checkpoint.")
    actual_count = models.PositiveSmallIntegerField()
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.OPEN, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    resolved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                                    related_name="+")
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolution_note = models.CharField(max_length=300, blank=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(condition=~Q(expected_count=models.F("actual_count")),
                                   name="alert_only_when_counts_differ"),
            models.CheckConstraint(
                condition=Q(status="open") | Q(resolved_at__isnull=False),
                name="resolved_alert_has_time",
            ),
        ]

    def __str__(self):
        return f"{self.order}: {self.get_checkpoint_display()} {self.actual_count} vs {self.expected_count}"

    @property
    def difference(self):
        return self.actual_count - self.expected_count
