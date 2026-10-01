from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import Group
from django.contrib.auth.views import PasswordChangeView
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from .forms import AddressForm, ProfileForm, RegisterForm, StyledPasswordChangeForm
from .permissions import role_required
from .roles import Role


def register(request):
    if request.user.is_authenticated:
        return redirect("accounts:account")
    if request.method == "POST":
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            # Everyone who signs up on the website is a Customer.
            user.groups.add(Group.objects.get(name=Role.CUSTOMER))
            login(request, user)
            messages.success(request, f"Welcome to WashO, {user.first_name}! Your account is ready.")
            return redirect("accounts:after_login")
    else:
        form = RegisterForm()
    return render(request, "accounts/register.html", {"form": form})


@login_required
def after_login(request):
    """Single place that decides where each role lands after logging in.

    Later phases point Staff, Agents and Admin to their own panels.
    """
    return redirect("accounts:account")


@login_required
def account(request):
    return render(request, "accounts/account.html")


@login_required
def profile_edit(request):
    if request.method == "POST":
        form = ProfileForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Your profile has been updated.")
            return redirect("accounts:account")
    else:
        form = ProfileForm(instance=request.user)
    return render(request, "accounts/profile_edit.html", {"form": form})


class WashOPasswordChangeView(PasswordChangeView):
    form_class = StyledPasswordChangeForm
    template_name = "accounts/password_change.html"
    success_url = reverse_lazy("accounts:account")

    def form_valid(self, form):
        messages.success(self.request, "Your password has been changed.")
        return super().form_valid(form)


# --- Address book (customers only) ------------------------------------------------


def _customer_addresses(user):
    return user.addresses.filter(is_active=True).select_related("area__store__city")


@role_required(Role.CUSTOMER)
def address_list(request):
    return render(request, "accounts/address_list.html", {"addresses": _customer_addresses(request.user)})


@transaction.atomic
def _save_address(form, user):
    address = form.save(commit=False)
    address.user = user
    others = user.addresses.filter(is_active=True).exclude(pk=address.pk)
    if not others.exists():
        address.is_default = True  # the first address is always the default
    if address.is_default:
        # Clear the old default first, otherwise the "one default" unique index would reject the save.
        others.filter(is_default=True).update(is_default=False)
    elif not others.filter(is_default=True).exists():
        address.is_default = True  # never leave the customer without a default
    address.save()
    return address


@role_required(Role.CUSTOMER)
def address_create(request):
    form = AddressForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        _save_address(form, request.user)
        messages.success(request, "Address saved.")
        # After adding an address from the booking page, go back there.
        next_url = request.GET.get("next")
        if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
            return redirect(next_url)
        return redirect("accounts:address_list")
    return render(request, "accounts/address_form.html", {"form": form, "is_new": True})


@role_required(Role.CUSTOMER)
def address_edit(request, pk):
    # Filtering by user means a customer can never open someone else's address (404).
    address = get_object_or_404(_customer_addresses(request.user), pk=pk)
    form = AddressForm(request.POST or None, instance=address)
    if request.method == "POST" and form.is_valid():
        _save_address(form, request.user)
        messages.success(request, "Address updated.")
        return redirect("accounts:address_list")
    return render(request, "accounts/address_form.html", {"form": form, "is_new": False})


@role_required(Role.CUSTOMER)
@require_POST
@transaction.atomic
def address_delete(request, pk):
    address = get_object_or_404(_customer_addresses(request.user), pk=pk)
    address.is_active = False
    address.is_default = False
    address.save(update_fields=["is_active", "is_default"])
    # Promote another address to default so the customer always has one.
    nxt = _customer_addresses(request.user).first()
    if nxt and not _customer_addresses(request.user).filter(is_default=True).exists():
        nxt.is_default = True
        nxt.save(update_fields=["is_default"])
    messages.success(request, "Address removed.")
    return redirect("accounts:address_list")
