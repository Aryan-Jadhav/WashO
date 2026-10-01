from django.contrib.auth.models import Group
from django.core.exceptions import PermissionDenied
from django.db import IntegrityError, transaction
from django.http import HttpResponse
from django.test import RequestFactory, TestCase
from django.urls import reverse

from .models import User
from .permissions import role_required
from .roles import Role
from .validators import normalize_phone


class UserModelTests(TestCase):
    def test_phone_is_normalised(self):
        self.assertEqual(normalize_phone("+91 98765-43210"), "9876543210")
        self.assertEqual(normalize_phone("09876543210"), "9876543210")
        user = User.objects.create_user("+91 9876543210", "Str0ng!pass")
        self.assertEqual(user.phone, "9876543210")

    def test_db_rejects_invalid_phone(self):
        # The CHECK constraint works even when forms are bypassed.
        with self.assertRaises(IntegrityError), transaction.atomic():
            User.objects.create_user("1234567890", "Str0ng!pass")

    def test_email_optional_but_unique(self):
        User.objects.create_user("9876543210", "x", email="")
        User.objects.create_user("9876543211", "x", email="")  # many blank emails are fine
        User.objects.create_user("9876543212", "x", email="a@b.com")
        with self.assertRaises(IntegrityError), transaction.atomic():
            User.objects.create_user("9876543213", "x", email="A@b.com")  # stored lowercase -> duplicate

    def test_roles_exist_and_superuser_is_admin(self):
        self.assertEqual(Group.objects.filter(name__in=Role.ALL).count(), 4)
        admin = User.objects.create_superuser("9000000000", "x")
        self.assertTrue(admin.has_role(Role.ADMIN))
        self.assertFalse(admin.has_role(Role.CUSTOMER))


class RegistrationAndLoginTests(TestCase):
    def test_register_creates_customer_and_logs_in(self):
        resp = self.client.post(reverse("accounts:register"), {
            "first_name": "Asha", "last_name": "Patil", "phone": "98765 43210", "email": "",
            "password1": "Laundry@2026", "password2": "Laundry@2026",
        })
        self.assertRedirects(resp, reverse("accounts:after_login"), target_status_code=302)
        user = User.objects.get(phone="9876543210")
        self.assertTrue(user.has_role(Role.CUSTOMER))
        self.assertEqual(int(self.client.session["_auth_user_id"]), user.pk)

    def test_register_rejects_duplicate_and_bad_phone(self):
        User.objects.create_user("9876543210", "x")
        for phone in ["9876543210", "12345"]:
            resp = self.client.post(reverse("accounts:register"), {
                "first_name": "A", "last_name": "B", "phone": phone,
                "password1": "Laundry@2026", "password2": "Laundry@2026",
            })
            self.assertEqual(resp.status_code, 200)
            self.assertTrue(resp.context["form"].errors.get("phone"))

    def test_login_with_formatted_phone(self):
        User.objects.create_user("9876543210", "Laundry@2026")
        resp = self.client.post(reverse("login"), {"username": "+91 98765 43210", "password": "Laundry@2026"})
        self.assertEqual(resp.status_code, 302)

    def test_account_page_needs_login(self):
        resp = self.client.get(reverse("accounts:account"))
        self.assertRedirects(resp, f"{reverse('login')}?next={reverse('accounts:account')}")


class RoleRequiredTests(TestCase):
    def test_wrong_role_gets_403(self):
        @role_required(Role.STAFF)
        def staff_view(request):
            return HttpResponse("ok")

        customer = User.objects.create_user("9876543210", "x")
        customer.groups.add(Group.objects.get(name=Role.CUSTOMER))
        staff = User.objects.create_user("9876543211", "x")
        staff.groups.add(Group.objects.get(name=Role.STAFF))

        request = RequestFactory().get("/staff/")
        request.user = customer
        with self.assertRaises(PermissionDenied):
            staff_view(request)

        request.user = staff
        self.assertEqual(staff_view(request).status_code, 200)
