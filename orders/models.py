from decimal import ROUND_HALF_UP, Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import F, Q
from django.db.models.functions import Now, Upper

TWO_PLACES = Decimal("0.01")


def money(value):
    """Round to paise the way money is normally rounded (0.005 -> 0.01)."""
    return Decimal(value).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


# --------------------------------------------------------------------------------------
# Pickup slots
# --------------------------------------------------------------------------------------


class TimeSlot(models.Model):
    """A pickup window such as 10:00–12:00, offered every day.

    `capacity` = how many pickups ONE area can have in this window on ONE day
    (roughly: how many homes an agent can visit in two hours).
    """

    start_time = models.TimeField()
    end_time = models.TimeField()
    capacity = models.PositiveSmallIntegerField(default=5, validators=[MinValueValidator(1)])
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["start_time"]
        constraints = [
            models.UniqueConstraint(fields=["start_time", "end_time"], name="unique_time_slot"),
            models.CheckConstraint(condition=Q(end_time__gt=F("start_time")), name="slot_ends_after_start"),
            models.CheckConstraint(condition=Q(capacity__gte=1), name="slot_capacity_at_least_1"),
        ]

    def __str__(self):
        return f"{self.start_time:%I:%M %p} – {self.end_time:%I:%M %p}"


class DailySlot(models.Model):
    """How many pickups are booked for one slot, on one date, in one area.

    WHY a counter row: when two customers book the last place at the same
    moment, the booking code locks THIS row (SELECT ... FOR UPDATE). The second
    customer waits, then sees the slot is full - so a slot can never be overbooked.
    """

    date = models.DateField()
    time_slot = models.ForeignKey(TimeSlot, on_delete=models.PROTECT, related_name="daily_slots")
    area = models.ForeignKey("stores.ServiceArea", on_delete=models.PROTECT, related_name="daily_slots")
    booked_count = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["date", "time_slot__start_time"]
        constraints = [
            models.UniqueConstraint(fields=["date", "time_slot", "area"], name="unique_daily_slot"),
            models.CheckConstraint(condition=Q(booked_count__gte=0), name="daily_slot_count_not_negative"),
        ]
        indexes = [models.Index(fields=["date", "area"])]

    def __str__(self):
        return f"{self.date} {self.time_slot} {self.area} ({self.booked_count}/{self.time_slot.capacity})"


# --------------------------------------------------------------------------------------
# Coupons
# --------------------------------------------------------------------------------------


class CouponError(Exception):
    """Raised with a customer-friendly message when a coupon can't be used."""


class Coupon(models.Model):
    class DiscountType(models.TextChoices):
        FLAT = "flat", "Flat amount (₹)"
        PERCENT = "percent", "Percentage (%)"

    code = models.CharField(max_length=20, unique=True, help_text="Customers type this. Stored in CAPITALS.")
    description = models.CharField(max_length=200)
    discount_type = models.CharField(max_length=10, choices=DiscountType.choices)
    value = models.DecimalField(max_digits=8, decimal_places=2, help_text="₹ amount or % depending on type.")
    max_discount = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True,
                                       help_text="Upper limit for percentage coupons (optional).")
    min_order_value = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal("0"))
    valid_from = models.DateField()
    valid_until = models.DateField()
    usage_limit = models.PositiveIntegerField(null=True, blank=True, help_text="Total uses allowed. Empty = unlimited.")
    per_user_limit = models.PositiveSmallIntegerField(default=1, help_text="Uses per customer. 0 = unlimited.")
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["-valid_until", "code"]
        constraints = [
            models.CheckConstraint(condition=Q(value__gt=0), name="coupon_value_positive"),
            models.CheckConstraint(
                condition=Q(discount_type="flat") | Q(value__lte=100), name="coupon_percent_max_100",
            ),
            models.CheckConstraint(condition=Q(valid_until__gte=F("valid_from")), name="coupon_dates_in_order"),
            models.CheckConstraint(condition=Q(code=Upper("code")), name="coupon_code_uppercase"),
        ]

    def __str__(self):
        return self.code

    def save(self, *args, **kwargs):
        self.code = self.code.strip().upper()
        super().save(*args, **kwargs)

    def _used_orders(self):
        return self.orders.exclude(status=Order.Status.CANCELLED)  # cancelled orders give the use back

    def times_used(self):
        return self._used_orders().count()

    def check_usable(self, user, order_amount, today):
        """Raise CouponError (with the reason) if this coupon can't be applied."""
        if not self.is_active:
            raise CouponError("This coupon is no longer active.")
        if today < self.valid_from:
            raise CouponError(f"This coupon starts on {self.valid_from:%d %b %Y}.")
        if today > self.valid_until:
            raise CouponError("This coupon has expired.")
        if self.usage_limit is not None and self.times_used() >= self.usage_limit:
            raise CouponError("This coupon has been fully used.")
        if user is not None and self.per_user_limit and \
                self._used_orders().filter(customer=user).count() >= self.per_user_limit:
            raise CouponError("You have already used this coupon.")
        if order_amount < self.min_order_value:
            short = money(self.min_order_value - order_amount)
            raise CouponError(f"Add items worth ₹{short} more to use this coupon (minimum ₹{self.min_order_value:.0f}).")

    def discount_for(self, amount):
        """Discount in ₹ for an order amount; never more than the amount itself."""
        if amount < self.min_order_value:
            return Decimal("0.00")
        if self.discount_type == self.DiscountType.FLAT:
            discount = self.value
        else:
            discount = amount * self.value / Decimal("100")
            if self.max_discount is not None:
                discount = min(discount, self.max_discount)
        return money(min(discount, amount))


# --------------------------------------------------------------------------------------
# Orders
# --------------------------------------------------------------------------------------


class OrderStatus(models.TextChoices):
    BOOKED = "booked", "Booked"
    PICKUP_ASSIGNED = "pickup_assigned", "Pickup Assigned"
    PICKED_UP = "picked_up", "Picked Up"
    AT_STORE = "at_store", "At Store"
    TAGGED = "tagged", "Tagged"
    IN_CLEANING = "in_cleaning", "In Cleaning"
    READY = "ready", "Ready"
    OUT_FOR_DELIVERY = "out_for_delivery", "Out for Delivery"
    DELIVERED = "delivered", "Delivered"
    CANCELLED = "cancelled", "Cancelled"


class Order(models.Model):
    Status = OrderStatus  # so code can say Order.Status.BOOKED

    # NULL until the row exists (the number is built from the id). Unique ignores NULLs,
    # so two orders being created at the same moment never clash.
    code = models.CharField(max_length=12, unique=True, null=True, blank=True,
                            help_text="Order number shown to customers.")
    customer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="orders")
    address = models.ForeignKey("accounts.Address", on_delete=models.PROTECT, related_name="orders")
    # WHY a text copy too: the order (and its invoice) must keep the address as it was
    # on the booking day, even if the customer edits the saved address later.
    address_snapshot = models.TextField()
    store = models.ForeignKey("stores.Store", on_delete=models.PROTECT, related_name="orders")
    pickup_slot = models.ForeignKey(DailySlot, on_delete=models.PROTECT, related_name="orders")
    is_express = models.BooleanField(default=False)
    status = models.CharField(max_length=20, choices=OrderStatus.choices, default=OrderStatus.BOOKED, db_index=True)
    coupon = models.ForeignKey(Coupon, on_delete=models.PROTECT, null=True, blank=True, related_name="orders")

    # Money. `estimated_total` is frozen at booking. The other four are the current bill:
    # equal to the estimate until the store tags the garments (Phase 4), then the final bill.
    estimated_total = models.DecimalField(max_digits=10, decimal_places=2)
    subtotal = models.DecimalField(max_digits=10, decimal_places=2)
    express_charge = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0"))
    discount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0"))
    total = models.DecimalField(max_digits=10, decimal_places=2)
    bill_finalised = models.BooleanField(default=False)

    customer_note = models.CharField(max_length=300, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["customer", "-created_at"])]
        constraints = [
            models.CheckConstraint(condition=Q(status__in=OrderStatus.values), name="order_status_valid"),
            models.CheckConstraint(
                condition=Q(subtotal__gte=0, express_charge__gte=0, discount__gte=0, total__gte=0),
                name="order_amounts_not_negative",
            ),
            # The database itself guarantees the bill adds up.
            models.CheckConstraint(
                condition=Q(total=F("subtotal") + F("express_charge") - F("discount")),
                name="order_total_adds_up",
            ),
        ]

    def __str__(self):
        return self.code or f"Order #{self.pk}"

    @property
    def is_open(self):
        return self.status not in (self.Status.DELIVERED, self.Status.CANCELLED)

    @property
    def can_cancel(self):
        from .services import CANCELLABLE_STATUSES
        return self.status in CANCELLABLE_STATUSES

    @property
    def piece_count(self):
        return sum(i.quantity for i in self.items.all())


class OrderItem(models.Model):
    """One line of the booking estimate, e.g. 'Wash & Iron – Shirt × 5'.

    Prices are COPIED here at booking time, so later price changes in the
    catalog don't change an existing order.
    """

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    category = models.ForeignKey("catalog.ServiceCategory", on_delete=models.PROTECT)
    item = models.ForeignKey("catalog.Item", on_delete=models.PROTECT)
    quantity = models.PositiveSmallIntegerField(validators=[MinValueValidator(1)])
    unit_price = models.DecimalField(max_digits=8, decimal_places=2)
    express_surcharge = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal("0"),
                                            help_text="Extra per unit for Express.")

    class Meta:
        ordering = ["category__sort_order", "item__sort_order"]
        constraints = [
            models.UniqueConstraint(fields=["order", "category", "item"], name="unique_item_per_order"),
            models.CheckConstraint(condition=Q(quantity__gte=1), name="order_item_quantity_positive"),
        ]

    def __str__(self):
        return f"{self.category} – {self.item} × {self.quantity}"

    @property
    def line_total(self):
        return money(self.quantity * (self.unit_price + self.express_surcharge))


class OrderStatusHistory(models.Model):
    """Audit trail: every status change with time and the user who made it.

    Rows are written by a PostgreSQL TRIGGER on the orders table (see
    migration 0002), not by Python code. So even a change made directly in
    the database is recorded.
    """

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="history")
    from_status = models.CharField(max_length=20, blank=True)
    to_status = models.CharField(max_length=20)
    changed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name="+")
    note = models.CharField(max_length=300, blank=True, db_default="")
    changed_at = models.DateTimeField(db_default=Now())

    class Meta:
        ordering = ["changed_at", "id"]
        verbose_name_plural = "order status history"
        indexes = [models.Index(fields=["order", "changed_at"])]

    def __str__(self):
        return f"{self.order}: {self.from_status or '—'} → {self.to_status}"

    @property
    def to_label(self):
        return Order.Status(self.to_status).label
