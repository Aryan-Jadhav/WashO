from django import forms
from django.contrib.auth.forms import AuthenticationForm, PasswordChangeForm, UserCreationForm

from core.forms import BootstrapFormMixin

from .models import User
from .validators import normalize_phone, phone_validator


def phone_form_field(required=True):
    """Form field that allows typing "+91 98765 43210"; clean_phone() reduces it to 10 digits.

    WHY not the model's max_length=10 here: that check would run before the spaces and
    "+91" are removed, rejecting numbers that are actually valid.
    """
    return forms.CharField(
        label="Mobile number",
        max_length=20,
        required=required,
        widget=forms.TextInput(attrs={"inputmode": "tel", "placeholder": "9876543210"}),
    )


class PhoneCleanMixin:
    def clean_phone(self):
        phone = normalize_phone(self.cleaned_data.get("phone"))
        phone_validator(phone)
        if User.objects.filter(phone=phone).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError("An account with this mobile number already exists.")
        return phone


class EmailCleanMixin:
    def clean_email(self):
        email = (self.cleaned_data.get("email") or "").strip().lower()
        if email and User.objects.filter(email=email).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError("This email is already registered.")
        return email


class RegisterForm(BootstrapFormMixin, PhoneCleanMixin, EmailCleanMixin, UserCreationForm):
    """Customer self-registration. Staff and agents are created by the admin."""

    first_name = forms.CharField(max_length=150)
    last_name = forms.CharField(max_length=150)
    phone = phone_form_field()

    class Meta:
        model = User
        fields = ["first_name", "last_name", "phone", "email"]
        help_texts = {"email": "Optional — used for order updates and invoices."}


class PhoneLoginForm(BootstrapFormMixin, AuthenticationForm):
    """Django's login form, but the 'username' box is the mobile number."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].label = "Mobile number"
        # maxlength 20 so the browser lets people type "+91 98765 43210".
        self.fields["username"].widget.attrs.update({"inputmode": "tel", "placeholder": "9876543210", "maxlength": "20"})

    def clean_username(self):
        # Accept '+91 98765 43210' etc. by normalising before authentication.
        return normalize_phone(self.cleaned_data.get("username"))


class ProfileForm(BootstrapFormMixin, EmailCleanMixin, forms.ModelForm):
    """Phone is the login ID, so it is not editable here."""

    class Meta:
        model = User
        fields = ["first_name", "last_name", "email"]


class StyledPasswordChangeForm(BootstrapFormMixin, PasswordChangeForm):
    pass
