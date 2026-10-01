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
