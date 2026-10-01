from django import forms

from accounts.validators import normalize_phone, phone_validator

from .models import ContactMessage


class BootstrapFormMixin:
    """Adds Bootstrap 5 CSS classes to every field, so templates stay short."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            widget = field.widget
            if isinstance(widget, (forms.CheckboxInput, forms.CheckboxSelectMultiple, forms.RadioSelect)):
                css = "form-check-input"
            elif isinstance(widget, (forms.Select, forms.SelectMultiple)):
                css = "form-select"
            else:
                css = "form-control"
            widget.attrs["class"] = f"{widget.attrs.get('class', '')} {css}".strip()


class ContactForm(BootstrapFormMixin, forms.ModelForm):
    # Wider than 10 so "+91 98765 43210" is accepted, then normalised in clean_phone().
    phone = forms.CharField(
        label="Mobile number", max_length=20, required=False,
        widget=forms.TextInput(attrs={"inputmode": "tel", "placeholder": "9876543210"}),
    )

    class Meta:
        model = ContactMessage
        fields = ["name", "phone", "email", "subject", "message"]
        widgets = {
            "message": forms.Textarea(attrs={"rows": 5}),
        }

    def clean_phone(self):
        phone = normalize_phone(self.cleaned_data.get("phone"))
        if phone:
            phone_validator(phone)
        return phone

    def clean_message(self):
        message = self.cleaned_data["message"].strip()
        if len(message) < 10:
            raise forms.ValidationError("Please write at least 10 characters.")
        return message
