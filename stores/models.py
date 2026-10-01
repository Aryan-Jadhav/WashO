from django.core.validators import RegexValidator
from django.db import models
from django.db.models import F, Q

pincode_validator = RegexValidator(r"^[1-9]\d{5}$", "Enter a valid 6-digit pincode.")


class City(models.Model):
    name = models.CharField(max_length=60, unique=True)
    slug = models.SlugField(max_length=60, unique=True)
    state = models.CharField(max_length=60, default="Maharashtra")
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "cities"

    def __str__(self):
        return self.name


class Store(models.Model):
    """A physical WashO store where clothes are tagged and cleaned."""

    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=100, unique=True)
    city = models.ForeignKey(City, on_delete=models.PROTECT, related_name="stores")
    address = models.CharField(max_length=255)
    locality = models.CharField(max_length=100, help_text="Area where the store is, e.g. Kothrud.")
    pincode = models.CharField(max_length=6, validators=[pincode_validator], db_index=True)
    phone = models.CharField(max_length=15)
    email = models.EmailField(blank=True)
    opening_time = models.TimeField()
    closing_time = models.TimeField()
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    # WHY is_active instead of deleting: old orders still point to this store.
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["city__name", "name"]
        constraints = [
            models.CheckConstraint(condition=Q(closing_time__gt=F("opening_time")), name="store_closes_after_opening"),
        ]

    def __str__(self):
        return self.name

    @property
    def map_url(self):
        if self.latitude is not None and self.longitude is not None:
            return f"https://www.google.com/maps/search/?api=1&query={self.latitude},{self.longitude}"
        return None


class ServiceArea(models.Model):
    """A locality + pincode where we pick up and deliver, served by one store.

    WHY no city column here: the city is already known through the store
    (area -> store -> city). Storing it twice would break 3NF and could go
    out of sync.
    """

    name = models.CharField("locality", max_length=100)
    pincode = models.CharField(max_length=6, validators=[pincode_validator], db_index=True)
    store = models.ForeignKey(Store, on_delete=models.PROTECT, related_name="areas")
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(fields=["name", "pincode"], name="unique_area_name_pincode"),
        ]

    def __str__(self):
        return f"{self.name} ({self.pincode})"
