from django.db import models

from accounts.validators import phone_validator


class ContactMessage(models.Model):
    """A message sent from the public Contact page (anyone, no login needed)."""

    name = models.CharField(max_length=100)
    phone = models.CharField("mobile number", max_length=10, blank=True, validators=[phone_validator])
    email = models.EmailField()
    subject = models.CharField(max_length=150)
    message = models.TextField()
    is_resolved = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["is_resolved", "created_at"])]

    def __str__(self):
        return f"{self.subject} — {self.name}"


class FAQ(models.Model):
    """FAQ entries are stored in the DB so the admin can edit them without code changes."""

    question = models.CharField(max_length=255)
    answer = models.TextField()
    sort_order = models.PositiveSmallIntegerField(default=0, help_text="Smaller numbers show first.")
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["sort_order", "id"]
        verbose_name = "FAQ"
        verbose_name_plural = "FAQs"

    def __str__(self):
        return self.question
