from django import forms
from django.utils import timezone

from core.forms import BootstrapFormMixin
from payments.models import Payment

from .services import agents_for_store


class _AgentChoiceMixin:
    def __init__(self, *args, order=None, **kwargs):
        super().__init__(*args, **kwargs)
        field = self.fields["agent"]
        field.queryset = agents_for_store(order.store)
        field.label_from_instance = lambda u: f"{u.get_full_name() or 'Agent'} · {u.phone}"
        field.empty_label = "Choose agent" if field.queryset.exists() else "No agents at this store yet"


class AssignPickupForm(_AgentChoiceMixin, BootstrapFormMixin, forms.Form):
    agent = forms.ModelChoiceField(queryset=None, label="Pickup agent")


class AssignDeliveryForm(_AgentChoiceMixin, BootstrapFormMixin, forms.Form):
    agent = forms.ModelChoiceField(queryset=None, label="Delivery agent")
    delivery_date = forms.DateField(label="Delivery date", widget=forms.DateInput(attrs={"type": "date"}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["delivery_date"].initial = timezone.localdate()

    def clean_delivery_date(self):
        d = self.cleaned_data["delivery_date"]
        if d < timezone.localdate():
            raise forms.ValidationError("The delivery date can't be in the past.")
        return d


class PickupCountForm(BootstrapFormMixin, forms.Form):
    count = forms.IntegerField(min_value=1, max_value=300, label="Garments counted with the customer",
                               widget=forms.NumberInput(attrs={"inputmode": "numeric", "class": "form-control-lg"}))
    note = forms.CharField(max_length=200, required=False, label="Note (optional)",
                           widget=forms.TextInput(attrs={"placeholder": "e.g. 2 extra bedsheets added by customer"}))


class DeliveryCountForm(BootstrapFormMixin, forms.Form):
    count = forms.IntegerField(min_value=0, max_value=300, label="Garments handed to the customer",
                               widget=forms.NumberInput(attrs={"inputmode": "numeric", "class": "form-control-lg"}))
    confirm_mismatch = forms.BooleanField(required=False,
                                          label="Counted again with the customer. The number is really different.")
    payment_method = forms.ChoiceField(choices=Payment.Method.choices, required=False, widget=forms.RadioSelect,
                                       label="Paid by")
    payment_collected = forms.BooleanField(required=False, label="Payment collected")
    reference = forms.CharField(max_length=40, required=False, label="UPI transaction ID (optional)")
    note = forms.CharField(max_length=200, required=False, label="Note (optional)")

    def __init__(self, *args, amount_due=0, **kwargs):
        super().__init__(*args, **kwargs)
        self.amount_due = amount_due

    def clean(self):
        cleaned = super().clean()
        if self.amount_due > 0:
            if not cleaned.get("payment_method"):
                self.add_error("payment_method", "Choose how the customer paid.")
            if not cleaned.get("payment_collected"):
                self.add_error("payment_collected", "Tick this after you have collected the full amount.")
        return cleaned
