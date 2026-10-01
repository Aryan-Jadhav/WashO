import datetime

from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse

from .models import City, ServiceArea, Store


class StoreDataTests(TestCase):
    def test_three_pune_stores_loaded(self):
        self.assertEqual(Store.objects.filter(city__slug="pune").count(), 3)
        self.assertTrue(ServiceArea.objects.filter(pincode="411038").exists())

    def test_store_must_close_after_opening(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            Store.objects.create(
                name="Bad", slug="bad", city=City.objects.get(slug="pune"), address="x", locality="x",
                pincode="411001", phone="1", opening_time=datetime.time(21), closing_time=datetime.time(8),
            )


class StoreLocatorTests(TestCase):
    url = reverse("stores:locator")

    def test_lists_all_stores(self):
        resp = self.client.get(self.url)
        self.assertEqual(len(resp.context["stores"]), 3)

    def test_served_pincode(self):
        resp = self.client.get(self.url, {"q": "411057"})  # Wakad -> Baner store
        self.assertEqual([s.slug for s in resp.context["stores"]], ["washo-baner"])
        self.assertContains(resp, "Great news")

    def test_shared_pincode_store_listed_once(self):
        # 411014 is served through three areas of the same store -> one card, not three.
        resp = self.client.get(self.url, {"q": "411014"})
        self.assertEqual(len(resp.context["stores"]), 1)

    def test_unserved_pincode(self):
        resp = self.client.get(self.url, {"q": "400001"})
        self.assertContains(resp, "Sorry, we don't serve pincode 400001")
        self.assertEqual(len(resp.context["stores"]), 0)

    def test_area_name_search(self):
        resp = self.client.get(self.url, {"q": "koregaon"})
        self.assertEqual([s.slug for s in resp.context["stores"]], ["washo-viman-nagar"])

    def test_bad_pincode_rejected(self):
        resp = self.client.get(self.url, {"q": "4110"})
        self.assertIn("q", resp.context["form"].errors)

    def test_inactive_area_not_matched(self):
        ServiceArea.objects.filter(name="Wakad").update(is_active=False)
        resp = self.client.get(self.url, {"q": "411057"})
        self.assertContains(resp, "Sorry, we don't serve pincode 411057")
