from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import Group
from django.contrib.auth.views import PasswordChangeView
from django.shortcuts import redirect, render
from django.urls import reverse_lazy

from .forms import ProfileForm, RegisterForm, StyledPasswordChangeForm
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
