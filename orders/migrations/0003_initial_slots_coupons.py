# Data migration: the daily pickup time slots and a few starter coupons.

import datetime
from decimal import Decimal

from django.db import migrations

# (start hour, end hour, capacity per area per day)
SLOTS = [(8, 10, 5), (10, 12, 5), (12, 14, 4), (14, 16, 4), (16, 18, 5), (18, 20, 5)]

COUPONS = [
    # code, description, type, value, max discount, min order, valid from, valid until, total limit, per user
    ("WELCOME50", "₹50 off your first order above ₹299", "flat", 50, None, 299,
     datetime.date(2026, 1, 1), datetime.date(2027, 12, 31), None, 1),
    ("FRESH20", "20% off (up to ₹150) on orders above ₹499", "percent", 20, 150, 499,
     datetime.date(2026, 1, 1), datetime.date(2027, 12, 31), 500, 3),
    ("FESTIVE100", "₹100 off on orders above ₹999 - first 50 customers", "flat", 100, None, 999,
     datetime.date(2026, 1, 1), datetime.date(2027, 12, 31), 50, 1),
    ("MONSOON15", "15% off - monsoon offer (expired, for testing)", "percent", 15, 100, 0,
     datetime.date(2025, 6, 1), datetime.date(2025, 9, 30), None, 1),
]


def load(apps, schema_editor):
    TimeSlot = apps.get_model("orders", "TimeSlot")
    Coupon = apps.get_model("orders", "Coupon")
    for start, end, cap in SLOTS:
        TimeSlot.objects.get_or_create(start_time=datetime.time(start), end_time=datetime.time(end),
                                       defaults={"capacity": cap})
    for code, desc, kind, value, max_d, min_o, v_from, v_until, limit, per_user in COUPONS:
        Coupon.objects.get_or_create(code=code, defaults={
            "description": desc, "discount_type": kind, "value": Decimal(value),
            "max_discount": Decimal(max_d) if max_d is not None else None, "min_order_value": Decimal(min_o),
            "valid_from": v_from, "valid_until": v_until, "usage_limit": limit, "per_user_limit": per_user,
        })


def unload(apps, schema_editor):
    apps.get_model("orders", "Coupon").objects.filter(code__in=[c[0] for c in COUPONS]).delete()
    apps.get_model("orders", "TimeSlot").objects.filter(
        start_time__in=[datetime.time(s) for s, _, _ in SLOTS]).delete()


class Migration(migrations.Migration):

    dependencies = [("orders", "0002_status_history_trigger")]

    operations = [migrations.RunPython(load, unload)]
