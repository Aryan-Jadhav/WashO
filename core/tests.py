from django.core import mail
from django.test import TestCase
from django.urls import reverse

from .models import FAQ, ContactMessage


class PublicPagesTests(TestCase):
    def test_public_pages_load(self):
        for name in ["home", "services", "about", "faq", "contact"]:
            resp = self.client.get(reverse(f"core:{name}"))
            self.assertEqual(resp.status_code, 200, name)

    def test_faq_shows_only_active(self):
        FAQ.objects.create(question="Hidden question?", answer="x", is_active=False)
        resp = self.client.get(reverse("core:faq"))
        self.assertNotContains(resp, "Hidden question?")
        self.assertContains(resp, "How do I book a pickup?")  # from the data migration


class ContactFormTests(TestCase):
    def test_valid_message_is_saved_and_emailed(self):
        resp = self.client.post(reverse("core:contact"), {
            "name": "Rahul", "phone": "9822012345", "email": "rahul@example.com",
            "subject": "Bulk order", "message": "Do you handle hostel laundry in bulk?",
        })
        self.assertRedirects(resp, reverse("core:contact"))
        self.assertEqual(ContactMessage.objects.count(), 1)
        self.assertEqual(len(mail.outbox), 1)

    def test_invalid_message_is_rejected(self):
        resp = self.client.post(reverse("core:contact"), {
            "name": "", "phone": "123", "email": "not-an-email", "subject": "", "message": "hi",
        })
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(set(resp.context["form"].errors), {"name", "phone", "email", "subject", "message"})
        self.assertEqual(ContactMessage.objects.count(), 0)


class TemplateHygieneTests(TestCase):
    def test_no_multiline_hash_comments(self):
        """Django's {# #} only works on ONE line; a multi-line one is printed on the page as text.

        (This once made the live order-status block show its comment again on every refresh.)
        Use {% comment %} ... {% endcomment %} for longer comments.
        """
        from pathlib import Path

        from django.conf import settings

        bad = []
        for path in Path(settings.BASE_DIR, "templates").rglob("*.html"):
            for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                if "{#" in line and "#}" not in line.split("{#", 1)[1]:
                    bad.append(f"{path.name}:{n}")
        self.assertEqual(bad, [], "Multi-line {# #} comments found - use {% comment %} instead")
