import datetime
from itertools import groupby

from django import forms
from django.utils import timezone

from catalog.views import active_prices
from core.forms import BootstrapFormMixin

from .models import TimeSlot
from .pricing import build_quote
from .services import BookingError, bookable_dates, check_slot_bookable

MAX_QTY_PER_ITEM = 50
MAX_PIECES_PER_ORDER = 200


class EstimateForm(BootstrapFormMixin, forms.Form):
    """Item quantities + express + coupon. Used alone for the live estimate (HTMX),
    and as the base of the full BookingForm."""

    is_express = forms.BooleanField(required=False, label="Express service")
    coupon_code = forms.CharField(max_length=20, required=False, label="Coupon code",
                                  widget=forms.TextInput(attrs={"placeholder": "e.g. WELCOME50",
                                                                "style": "text-transform: uppercase"}))

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        # One quantity box per active price, named qty_<price id>.
        self.prices = list(active_prices().order_by("category__sort_order", "item__sort_order"))
        for p in self.prices:
            self.fields[f"qty_{p.pk}"] = forms.IntegerField(
                min_value=0, max_value=MAX_QTY_PER_ITEM, required=False, label=p.item.name,
                widget=forms.NumberInput(attrs={"class": "form-control form-control-sm qty-input",
                                                "min": 0, "max": MAX_QTY_PER_ITEM, "placeholder": "0"}),
            )

    def item_groups(self):
        """[(category, [(price, bound_field), ...]), ...] for the template."""
        rows = [(p, self[f"qty_{p.pk}"]) for p in self.prices]
        return [(cat, list(r)) for cat, r in groupby(rows, key=lambda row: row[0].category)]

    def selected_items(self):
        data = getattr(self, "cleaned_data", {})
        return [(p, data.get(f"qty_{p.pk}") or 0) for p in self.prices if data.get(f"qty_{p.pk}")]

    def clean(self):
        cleaned = super().clean()
        pieces = sum(qty for _, qty in self.selected_items())
        if pieces > MAX_PIECES_PER_ORDER:
            raise forms.ValidationError(
                f"That's {pieces} pieces. For more than {MAX_PIECES_PER_ORDER} pieces please contact us for a bulk pickup."
            )
        return cleaned

    def quote(self):
        data = getattr(self, "cleaned_data", {})
        return build_quote(self.selected_items(), data.get("is_express", False),
                           data.get("coupon_code", ""), self.user)


class BookingForm(EstimateForm):
    address = forms.ModelChoiceField(queryset=None, widget=forms.RadioSelect, empty_label=None,
                                     label="Pickup address")
    pickup_date = forms.ChoiceField(label="Pickup date")
    time_slot = forms.ModelChoiceField(queryset=TimeSlot.objects.filter(is_active=True),
                                       widget=forms.RadioSelect, empty_label=None, label="Time slot",
                                       error_messages={"required": "Please choose a pickup time slot."})
    note = forms.CharField(max_length=300, required=False, label="Note for the pickup agent",
                           widget=forms.TextInput(attrs={"placeholder": "e.g. Call before coming, 3rd floor"}))

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, user=user, **kwargs)
        self.fields["address"].queryset = user.addresses.filter(is_active=True).select_related("area__store__city")
        self.fields["address"].label_from_instance = lambda a: a.one_line()
        today = timezone.localdate()
        self.fields["pickup_date"].choices = [
            (d.isoformat(), d.strftime("%a, %d %b") + (" (Today)" if d == today else " (Tomorrow)"
                                                       if d == today + datetime.timedelta(days=1) else ""))
            for d in bookable_dates(today)
        ]

    def clean_pickup_date(self):
        return datetime.date.fromisoformat(self.cleaned_data["pickup_date"])

    def clean(self):
        cleaned = super().clean()
        if not self.selected_items() and not self.errors:
            raise forms.ValidationError("Please add at least one item (approximate count is fine).")
        date, slot = cleaned.get("pickup_date"), cleaned.get("time_slot")
        if date and slot:
            try:
                check_slot_bookable(date, slot)
            except BookingError as e:
                self.add_error("time_slot", str(e))
        if cleaned.get("coupon_code"):
            quote = self.quote()
            if quote.coupon_error:
                self.add_error("coupon_code", quote.coupon_error)
        return cleaned


class CancelOrderForm(BootstrapFormMixin, forms.Form):
    reason = forms.CharField(max_length=200, required=False, label="Reason (optional)")
