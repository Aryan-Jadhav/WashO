from decimal import ROUND_HALF_UP, Decimal

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q

TWO_PLACES = Decimal("0.01")


class ServiceCategory(models.Model):
    """A type of service, e.g. Dry Clean or Wash & Iron."""

    name = models.CharField(max_length=60, unique=True)
    slug = models.SlugField(max_length=60, unique=True, help_text="Used in web addresses, e.g. dry-clean.")
    description = models.TextField()
    icon = models.CharField(max_length=40, default="basket", help_text="Bootstrap Icons name, e.g. 'stars'.")
    standard_turnaround_hours = models.PositiveSmallIntegerField(default=48)
    express_available = models.BooleanField(default=False)
    express_surcharge_percent = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal("0"),
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Extra % added to the price when the customer chooses Express.",
    )
    express_turnaround_hours = models.PositiveSmallIntegerField(null=True, blank=True)
    sort_order = models.PositiveSmallIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["sort_order", "name"]
        verbose_name_plural = "service categories"
        constraints = [
            models.CheckConstraint(
                condition=Q(express_surcharge_percent__gte=0) & Q(express_surcharge_percent__lte=100),
                name="category_surcharge_0_to_100",
            ),
            # If Express is offered it must have a surcharge and a faster turnaround time.
            models.CheckConstraint(
                condition=Q(express_available=False)
                | Q(express_surcharge_percent__gt=0, express_turnaround_hours__isnull=False),
                name="category_express_needs_surcharge_and_time",
                violation_error_message="Express needs a surcharge above 0% and an express turnaround time.",
            ),
        ]

    def __str__(self):
        return self.name


class Item(models.Model):
    """A garment or article, e.g. Shirt, Saree, Blanket, Sports Shoes.

    WHY separate from category: the same item (Shirt) can be washed, ironed or
    dry cleaned at different prices. The price lives in ServicePrice, which
    links one category to one item (keeps the design in 3NF).
    """

    class Group(models.TextChoices):
        MEN = "men", "Men"
        WOMEN = "women", "Women"
        KIDS = "kids", "Kids"
        HOUSEHOLD = "household", "Household"
        FOOTWEAR = "footwear", "Footwear"
        ACCESSORIES = "accessories", "Accessories"

    class Unit(models.TextChoices):
        PIECE = "piece", "per piece"
        PAIR = "pair", "per pair"
        SET = "set", "per set"

    name = models.CharField(max_length=80, unique=True)
    group = models.CharField(max_length=20, choices=Group.choices, db_index=True)
    unit = models.CharField(max_length=10, choices=Unit.choices, default=Unit.PIECE)
    sort_order = models.PositiveSmallIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["sort_order", "name"]

    def __str__(self):
        return self.name


class ServicePrice(models.Model):
    """Price of one item in one service category (e.g. Dry Clean + Saree = ₹299)."""

    category = models.ForeignKey(ServiceCategory, on_delete=models.PROTECT, related_name="prices")
    item = models.ForeignKey(Item, on_delete=models.PROTECT, related_name="prices")
    price = models.DecimalField(max_digits=8, decimal_places=2, validators=[MinValueValidator(Decimal("1"))])
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["category__sort_order", "item__sort_order", "item__name"]
        constraints = [
            # One price per item per category - no conflicting duplicate prices.
            models.UniqueConstraint(fields=["category", "item"], name="unique_price_per_category_item"),
            models.CheckConstraint(condition=Q(price__gt=0), name="price_positive"),
        ]

    def __str__(self):
        return f"{self.category} — {self.item}: ₹{self.price}"

    @property
    def express_price(self):
        """Price with the category's express surcharge, or None if express isn't offered."""
        if not self.category.express_available:
            return None
        return self.unit_price(express=True)

    def unit_price(self, express=False):
        """Price for one unit. Rounded to paise with ROUND_HALF_UP (normal money rounding)."""
        price = self.price
        if express and self.category.express_available:
            price = price * (1 + self.category.express_surcharge_percent / Decimal("100"))
        return price.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
