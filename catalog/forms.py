from django import forms

from core.forms import BootstrapFormMixin

from .models import ServiceCategory


class PriceSearchForm(BootstrapFormMixin, forms.Form):
    """Filters for the public price list (sent as GET parameters)."""

    category = forms.ModelChoiceField(
        queryset=ServiceCategory.objects.filter(is_active=True),
        to_field_name="slug", required=False, empty_label="All services",
    )
    q = forms.CharField(
        label="Search item", max_length=50, required=False,
        widget=forms.TextInput(attrs={"placeholder": "e.g. saree, blanket, shoes", "type": "search"}),
    )

    def clean_q(self):
        return self.cleaned_data["q"].strip()
