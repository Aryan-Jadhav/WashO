from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from django.db.models import Q

from .roles import Role
from .validators import PHONE_REGEX, normalize_phone, phone_validator


class UserManager(BaseUserManager):
    """Creates users with a phone number instead of a username."""

    use_in_migrations = True

    def _create_user(self, phone, password, **extra_fields):
        if not phone:
            raise ValueError("A phone number is required.")
        phone = normalize_phone(phone)
        email = extra_fields.pop("email", "") or ""
        user = self.model(phone=phone, email=self.normalize_email(email).lower(), **extra_fields)
        user.set_password(password)  # stores a salted hash, never the plain password
        user.save(using=self._db)
        return user

    def create_user(self, phone, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(phone, password, **extra_fields)

    def create_superuser(self, phone, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        if extra_fields.get("is_staff") is not True or extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_staff=True and is_superuser=True.")
        return self._create_user(phone, password, **extra_fields)


class User(AbstractUser):
    """Custom user: logs in with mobile number; email is optional.

    WHY a custom model from day one: Django cannot easily switch the user model
    after the first migration, and our users are identified by phone (as is
    normal for Indian service apps), not by a username.
    """

    username = None  # remove the username field inherited from AbstractUser
    phone = models.CharField(
        "mobile number",
        max_length=10,
        unique=True,  # unique also creates a DB index -> fast login lookups
        validators=[phone_validator],
        help_text="10-digit mobile number, used to log in.",
    )
    email = models.EmailField("email address", blank=True)

    USERNAME_FIELD = "phone"
    REQUIRED_FIELDS = []  # asked by `createsuperuser` besides phone + password

    objects = UserManager()

    class Meta:
        ordering = ["first_name", "last_name"]
        constraints = [
            # Email is optional, but if given it must not belong to someone else.
            # This is a PostgreSQL *partial unique index* (only rows with an email).
            models.UniqueConstraint(
                fields=["email"],
                condition=~Q(email=""),
                name="unique_email_when_present",
                violation_error_message="This email is already registered.",
            ),
            # Second line of defence: the database itself rejects bad phone numbers,
            # even if data is inserted without going through our forms.
            models.CheckConstraint(
                condition=Q(phone__regex=PHONE_REGEX),
                name="phone_is_valid_indian_mobile",
            ),
        ]

    def __str__(self):
        name = self.get_full_name()
        return f"{name} ({self.phone})" if name else self.phone

    def save(self, *args, **kwargs):
        self.phone = normalize_phone(self.phone)
        self.email = (self.email or "").strip().lower()
        super().save(*args, **kwargs)

    # --- Role helpers (used by templates and permission checks) ---------------
    def has_role(self, *roles):
        """True if the user belongs to any of the given role groups.

        A superuser is always treated as Admin.
        """
        if self.is_superuser and Role.ADMIN in roles:
            return True
        # Cache group names on the object so repeated checks don't hit the DB again.
        if not hasattr(self, "_role_names"):
            self._role_names = set(self.groups.values_list("name", flat=True))
        return bool(self._role_names.intersection(roles))

    @property
    def role(self):
        """The user's main role, for display."""
        for r in (Role.ADMIN, Role.STAFF, Role.AGENT, Role.CUSTOMER):
            if self.has_role(r):
                return r
        return None

    @property
    def is_customer(self):
        return self.has_role(Role.CUSTOMER)

    @property
    def is_store_staff(self):
        return self.has_role(Role.STAFF)

    @property
    def is_delivery_agent(self):
        return self.has_role(Role.AGENT)

    @property
    def is_admin_role(self):
        return self.has_role(Role.ADMIN)
