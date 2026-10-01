from django import forms

from core.forms import BootstrapFormMixin

from .models import City


class StoreSearchForm(BootstrapFormMixin, forms.Form):
    """Store locator filters: city + free text (locality name or 6-digit pincode)."""

    city = forms.ModelChoiceField(
        queryset=City.objects.filter(is_active=True), to_field_name="slug",
        required=False, empty_label="All cities",
    )
    q = forms.CharField(
        label="Area or pincode", max_length=50, required=False,
        widget=forms.TextInput(attrs={"placeholder": "e.g. Kothrud or 411038", "type": "search"}),
    )

    def clean_q(self):
        q = self.cleaned_data["q"].strip()
        # Only digits typed = a pincode, which must be exactly 6 digits.
        if q.isdigit() and len(q) != 6:
            raise forms.ValidationError("A pincode has exactly 6 digits.")
        return q

    @property
    def pincode(self):
        q = self.cleaned_data.get("q", "") if hasattr(self, "cleaned_data") else ""
        return q if q.isdigit() else None
