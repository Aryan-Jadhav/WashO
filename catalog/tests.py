from decimal import Decimal

from django.db import IntegrityError, transaction
from django.template import Context, Template
from django.test import TestCase
from django.urls import reverse

from .models import Item, ServiceCategory, ServicePrice


class CatalogDataTests(TestCase):
    def test_initial_catalog_loaded(self):
        # Loaded by the data migration.
        self.assertEqual(ServiceCategory.objects.count(), 6)
        self.assertTrue(ServicePrice.objects.filter(category__slug="dry-clean", item__name="Saree (Silk)").exists())

    def test_one_price_per_category_and_item(self):
        p = ServicePrice.objects.select_related("category", "item").first()
        with self.assertRaises(IntegrityError), transaction.atomic():
            ServicePrice.objects.create(category=p.category, item=p.item, price=Decimal("10"))

    def test_price_must_be_positive(self):
        cat = ServiceCategory.objects.get(slug="wash-fold")
        item = Item.objects.create(name="Test Cap", group="accessories")
        with self.assertRaises(IntegrityError), transaction.atomic():
            ServicePrice.objects.create(category=cat, item=item, price=Decimal("0"))

    def test_express_requires_surcharge_and_time(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            ServiceCategory.objects.create(name="Bad", slug="bad", description="x",
                                           express_available=True, express_surcharge_percent=0)


class ExpressPriceTests(TestCase):
    def test_express_price_adds_surcharge(self):
        p = ServicePrice.objects.get(category__slug="dry-clean", item__name="Saree (Silk)")  # ₹299, +50%
        self.assertEqual(p.unit_price(), Decimal("299.00"))
        self.assertEqual(p.unit_price(express=True), Decimal("448.50"))
        self.assertEqual(p.express_price, Decimal("448.50"))

    def test_no_express_when_not_offered(self):
        p = ServicePrice.objects.get(category__slug="shoe-cleaning", item__name="Sports Shoes")
        self.assertIsNone(p.express_price)
        self.assertEqual(p.unit_price(express=True), Decimal("399.00"))  # surcharge not applied


class PriceListPageTests(TestCase):
    url = reverse("catalog:price_list")

    def test_shows_all_categories(self):
        resp = self.client.get(self.url)
        self.assertEqual(len(resp.context["groups"]), 6)
        self.assertContains(resp, "Saree (Silk)")

    def test_filter_by_category_and_search(self):
        resp = self.client.get(self.url, {"category": "dry-clean", "q": "saree"})
        groups = resp.context["groups"]
        self.assertEqual([c.slug for c, _ in groups], ["dry-clean"])
        self.assertTrue(all("Saree" in p.item.name for p in groups[0][1]))

    def test_inactive_price_hidden(self):
        ServicePrice.objects.filter(item__name="Tie").update(is_active=False)
        self.assertNotContains(self.client.get(self.url), "Tie")

    def test_unknown_category_shows_error(self):
        resp = self.client.get(self.url, {"category": "space-cleaning"})
        self.assertEqual(resp.context["groups"], [])
        self.assertTrue(resp.context["form"].errors)

    def test_htmx_request_returns_fragment_only(self):
        resp = self.client.get(self.url, {"q": "shirt"}, HTTP_HX_REQUEST="true")
        self.assertNotContains(resp, "<html")
        self.assertContains(resp, "T-Shirt")


class RupeesFilterTests(TestCase):
    def render(self, value):
        return Template("{% load money %}{{ v|rupees }}").render(Context({"v": value}))

    def test_indian_number_format(self):
        self.assertEqual(self.render(Decimal("1499")), "₹1,499")
        self.assertEqual(self.render(Decimal("123456.5")), "₹1,23,456.50")
        self.assertEqual(self.render(Decimal("99")), "₹99")
        self.assertEqual(self.render(None), "")
