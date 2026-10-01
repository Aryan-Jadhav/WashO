from itertools import groupby

from django import forms

from catalog.views import active_prices
from core.forms import BootstrapFormMixin

from .models import Garment


class ConditionCleanMixin:
    def clean(self):
        cleaned = super().clean()
        if (cleaned.get("has_stain") or cleaned.get("has_damage")) and not (cleaned.get("condition_note") or "").strip():
            self.add_error("condition_note", "Please describe the stain or damage (where and what).")
        return cleaned


class GarmentForm(ConditionCleanMixin, BootstrapFormMixin, forms.Form):
    """Tag one garment. The service list puts what the customer booked first."""

    service_price = forms.ChoiceField(label="Service & item")
    description = forms.CharField(max_length=120, required=False, label="Colour / brand",
                                  widget=forms.TextInput(attrs={"placeholder": "e.g. Blue, Raymond"}))
    has_stain = forms.BooleanField(required=False, label="Stain")
    has_damage = forms.BooleanField(required=False, label="Damage (tear, missing button...)")
    condition_note = forms.CharField(max_length=300, required=False, label="Stain / damage note",
                                     widget=forms.TextInput(attrs={"placeholder": "e.g. Ink mark on right pocket"}))
    photo = forms.ImageField(required=False, label="Photo (optional)",
                             widget=forms.ClearableFileInput(attrs={"accept": "image/*", "capture": "environment"}))

    def __init__(self, *args, order=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.prices = {str(p.pk): p for p in active_prices().order_by("category__sort_order", "item__sort_order")}
        booked = {(i.category_id, i.item_id) for i in order.items.all()} if order else set()

        def label(p):
            return f"{p.item.name} (₹{p.price:.0f})"

        booked_choices = [(pk, f"{p.category.name} – {label(p)}") for pk, p in self.prices.items()
                          if (p.category_id, p.item_id) in booked]
        choices = [("", "Select service & item")]
        if booked_choices:
            choices.append(("Booked by customer", booked_choices))
        for cat, rows in groupby(self.prices.values(), key=lambda p: p.category):
            choices.append((cat.name, [(str(p.pk), label(p)) for p in rows]))
        self.fields["service_price"].choices = choices

    def clean_service_price(self):
        return self.prices[self.cleaned_data["service_price"]]


class GarmentEditForm(ConditionCleanMixin, BootstrapFormMixin, forms.ModelForm):
    """Correct a garment's details later (e.g. a stain found during cleaning)."""

    class Meta:
        model = Garment
        fields = ["description", "has_stain", "has_damage", "condition_note", "photo"]
        labels = {"description": "Colour / brand", "has_stain": "Stain",
                  "has_damage": "Damage (tear, missing button...)", "condition_note": "Stain / damage note"}
        widgets = {"photo": forms.ClearableFileInput(attrs={"accept": "image/*", "capture": "environment"})}


class FinishTaggingForm(forms.Form):
    confirm_mismatch = forms.BooleanField(
        required=False, label="I have re-checked the bag. The count is different from the pickup count.",
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
    )


class ResolveAlertForm(BootstrapFormMixin, forms.Form):
    resolution_note = forms.CharField(max_length=300, label="How was it resolved?",
                                      widget=forms.TextInput(attrs={"placeholder": "e.g. Agent miscounted; customer confirmed 12 pieces"}))
