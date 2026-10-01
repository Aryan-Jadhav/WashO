from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.forms import UserChangeForm, UserCreationForm

from .models import User


class AdminUserCreationForm(UserCreationForm):
    class Meta:
        model = User
        fields = ["phone", "first_name", "last_name", "email"]


class AdminUserChangeForm(UserChangeForm):
    class Meta:
        model = User
        fields = "__all__"


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """Django's user admin, adapted because we have 'phone' instead of 'username'."""

    form = AdminUserChangeForm
    add_form = AdminUserCreationForm

    list_display = ["phone", "first_name", "last_name", "email", "role_name", "is_active"]
    list_filter = ["groups", "is_active", "is_staff"]
    search_fields = ["phone", "first_name", "last_name", "email"]
    ordering = ["phone"]

    fieldsets = (
        (None, {"fields": ("phone", "password")}),
        ("Personal info", {"fields": ("first_name", "last_name", "email")}),
        (
            "Role & permissions",
            {
                "fields": ("groups", "is_active", "is_staff", "is_superuser", "user_permissions"),
                "description": "Pick ONE role group: Customer, Store Staff, Delivery Agent or Admin. "
                "Tick 'Staff status' only for people who should open this admin site.",
            },
        ),
        ("Important dates", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("phone", "first_name", "last_name", "email", "password1", "password2"),
            },
        ),
    )

    @admin.display(description="Role")
    def role_name(self, obj):
        return obj.role or "—"
