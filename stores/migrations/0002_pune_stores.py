# Data migration: 3 WashO stores in Pune and the localities each one serves.
# Addresses and phone numbers are fictional (academic project); pincodes are real Pune pincodes.

import datetime
from decimal import Decimal

from django.db import migrations

STORES = [
    {
        "name": "WashO Kothrud", "slug": "washo-kothrud",
        "address": "Shop 4, Shree Krupa Complex, Paud Road", "locality": "Kothrud", "pincode": "411038",
        "phone": "020-4000-0101", "email": "kothrud@washo.local",
        "lat": "18.507400", "lng": "73.807700",
        "areas": [("Kothrud", "411038"), ("Karve Nagar", "411052"), ("Warje", "411058"),
                  ("Erandwane", "411004"), ("Deccan Gymkhana", "411004"), ("Bavdhan", "411021")],
    },
    {
        "name": "WashO Baner", "slug": "washo-baner",
        "address": "Shop 11, Green Arcade, Baner Road", "locality": "Baner", "pincode": "411045",
        "phone": "020-4000-0202", "email": "baner@washo.local",
        "lat": "18.559000", "lng": "73.786800",
        "areas": [("Baner", "411045"), ("Balewadi", "411045"), ("Aundh", "411007"),
                  ("Pashan", "411021"), ("Wakad", "411057")],
    },
    {
        "name": "WashO Viman Nagar", "slug": "washo-viman-nagar",
        "address": "Shop 2, Sky Plaza, Nagar Road", "locality": "Viman Nagar", "pincode": "411014",
        "phone": "020-4000-0303", "email": "vimannagar@washo.local",
        "lat": "18.567900", "lng": "73.914300",
        "areas": [("Viman Nagar", "411014"), ("Kharadi", "411014"), ("Wadgaon Sheri", "411014"),
                  ("Kalyani Nagar", "411006"), ("Yerawada", "411006"), ("Koregaon Park", "411001")],
    },
]


def load_stores(apps, schema_editor):
    City = apps.get_model("stores", "City")
    Store = apps.get_model("stores", "Store")
    ServiceArea = apps.get_model("stores", "ServiceArea")

    pune, _ = City.objects.get_or_create(slug="pune", defaults={"name": "Pune", "state": "Maharashtra"})
    for s in STORES:
        store, _ = Store.objects.get_or_create(slug=s["slug"], defaults={
            "name": s["name"], "city": pune, "address": s["address"], "locality": s["locality"],
            "pincode": s["pincode"], "phone": s["phone"], "email": s["email"],
            "opening_time": datetime.time(8, 0), "closing_time": datetime.time(21, 0),
            "latitude": Decimal(s["lat"]), "longitude": Decimal(s["lng"]),
        })
        for area_name, pincode in s["areas"]:
            ServiceArea.objects.get_or_create(name=area_name, pincode=pincode, defaults={"store": store})


def unload_stores(apps, schema_editor):
    slugs = [s["slug"] for s in STORES]
    apps.get_model("stores", "ServiceArea").objects.filter(store__slug__in=slugs).delete()
    apps.get_model("stores", "Store").objects.filter(slug__in=slugs).delete()
    apps.get_model("stores", "City").objects.filter(slug="pune", stores__isnull=True).delete()


class Migration(migrations.Migration):

    dependencies = [("stores", "0001_initial")]

    operations = [migrations.RunPython(load_stores, unload_stores)]
