# Data migration: the full WashO service catalog and Pune price list.
# WHY a migration: every new database (second laptop, test database) gets the
# same master data automatically when `migrate` runs. Admin can edit prices later;
# get_or_create never overwrites an edited price.

from decimal import Decimal

from django.db import migrations

# slug: (name, icon, description, std_hours, express?, surcharge %, express_hours)
CATEGORIES = {
    "laundry": ("Laundry", "basket",
                "Premium laundry for your everyday wear: gentle wash, stain pre-treatment and steam press, "
                "returned on hangers.", 48, True, 50, 24),
    "wash-fold": ("Wash & Fold", "layers",
                  "Machine washed, dried and neatly folded. Great value for daily clothes and linen.",
                  48, True, 50, 24),
    "wash-iron": ("Wash & Iron", "fire",
                  "Washed, dried and crisply ironed, ready to wear for office or college.",
                  48, True, 50, 24),
    "dry-clean": ("Dry Clean", "stars",
                  "Gentle solvent cleaning for sarees, suits, silk, woollens and party wear that water can damage.",
                  72, True, 50, 36),
    "shoe-cleaning": ("Shoe Cleaning", "bag-check",
                      "Deep cleaning, deodorising and conditioning for sports, casual and leather shoes.",
                      96, False, 0, None),
    "home-textiles": ("Home Textiles", "house-heart",
                      "Curtains, carpets, blankets, quilts and sofa covers, deep cleaned and sanitised.",
                      96, False, 0, None),
}

# name: (group, unit)
ITEMS = {
    "Shirt": ("men", "piece"), "T-Shirt": ("men", "piece"), "Trousers": ("men", "piece"),
    "Jeans": ("men", "piece"), "Shorts": ("men", "piece"), "Kurta": ("men", "piece"),
    "Blazer / Coat": ("men", "piece"), "Suit (2 piece)": ("men", "set"), "Sherwani": ("men", "piece"),
    "Jacket": ("men", "piece"), "Sweater": ("men", "piece"),
    "Saree (Cotton)": ("women", "piece"), "Saree (Silk)": ("women", "piece"),
    "Saree (Designer / Heavy work)": ("women", "piece"), "Salwar Kurta (2 piece)": ("women", "set"),
    "Top": ("women", "piece"), "Dress": ("women", "piece"), "Dupatta": ("women", "piece"),
    "Lehenga (3 piece)": ("women", "set"),
    "Kids Wear": ("kids", "piece"),
    "Bedsheet (Single)": ("household", "piece"), "Bedsheet (Double)": ("household", "piece"),
    "Pillow Cover": ("household", "piece"), "Towel": ("household", "piece"),
    "Blanket (Single)": ("household", "piece"), "Blanket (Double)": ("household", "piece"),
    "Quilt / Razai": ("household", "piece"), "Curtain (per panel)": ("household", "piece"),
    "Carpet (up to 4x6 ft)": ("household", "piece"), "Carpet (up to 6x9 ft)": ("household", "piece"),
    "Sofa Cover (per seat)": ("household", "piece"),
    "Sports Shoes": ("footwear", "pair"), "Leather Shoes": ("footwear", "pair"),
    "Sandals / Heels": ("footwear", "pair"),
    "Tie": ("accessories", "piece"),
}

# category slug -> {item name: price in ₹}
PRICES = {
    "laundry": {
        "Shirt": 59, "T-Shirt": 49, "Trousers": 69, "Jeans": 79, "Kurta": 79, "Top": 59, "Dress": 99,
        "Salwar Kurta (2 piece)": 119, "Saree (Cotton)": 149, "Kids Wear": 39,
    },
    "wash-fold": {
        "Shirt": 25, "T-Shirt": 20, "Trousers": 30, "Jeans": 35, "Shorts": 20, "Kurta": 30, "Top": 25,
        "Dress": 40, "Dupatta": 25, "Kids Wear": 15, "Bedsheet (Single)": 40, "Bedsheet (Double)": 60,
        "Pillow Cover": 10, "Towel": 20,
    },
    "wash-iron": {
        "Shirt": 35, "T-Shirt": 30, "Trousers": 40, "Jeans": 45, "Shorts": 30, "Kurta": 40, "Top": 35,
        "Dress": 55, "Dupatta": 35, "Salwar Kurta (2 piece)": 60, "Saree (Cotton)": 90, "Kids Wear": 25,
        "Bedsheet (Single)": 55, "Bedsheet (Double)": 80, "Pillow Cover": 15,
    },
    "dry-clean": {
        "Shirt": 99, "Trousers": 109, "Jeans": 119, "Kurta": 129, "Blazer / Coat": 299,
        "Suit (2 piece)": 449, "Sherwani": 599, "Jacket": 349, "Sweater": 179,
        "Saree (Cotton)": 199, "Saree (Silk)": 299, "Saree (Designer / Heavy work)": 449,
        "Salwar Kurta (2 piece)": 199, "Dress": 249, "Dupatta": 99, "Lehenga (3 piece)": 699, "Tie": 79,
        "Blanket (Single)": 349, "Blanket (Double)": 449, "Quilt / Razai": 499,
    },
    "shoe-cleaning": {"Sports Shoes": 399, "Leather Shoes": 449, "Sandals / Heels": 299},
    "home-textiles": {
        "Curtain (per panel)": 149, "Carpet (up to 4x6 ft)": 499, "Carpet (up to 6x9 ft)": 899,
        "Sofa Cover (per seat)": 149, "Blanket (Single)": 299, "Blanket (Double)": 399, "Quilt / Razai": 449,
    },
}


def load_catalog(apps, schema_editor):
    ServiceCategory = apps.get_model("catalog", "ServiceCategory")
    Item = apps.get_model("catalog", "Item")
    ServicePrice = apps.get_model("catalog", "ServicePrice")

    categories = {}
    for order, (slug, (name, icon, desc, std, express, pct, exp_hours)) in enumerate(CATEGORIES.items(), 1):
        categories[slug], _ = ServiceCategory.objects.get_or_create(slug=slug, defaults={
            "name": name, "icon": icon, "description": desc, "standard_turnaround_hours": std,
            "express_available": express, "express_surcharge_percent": Decimal(pct),
            "express_turnaround_hours": exp_hours, "sort_order": order * 10,
        })

    items = {}
    for order, (name, (group, unit)) in enumerate(ITEMS.items(), 1):
        items[name], _ = Item.objects.get_or_create(name=name, defaults={
            "group": group, "unit": unit, "sort_order": order * 10,
        })

    for slug, item_prices in PRICES.items():
        for item_name, price in item_prices.items():
            ServicePrice.objects.get_or_create(
                category=categories[slug], item=items[item_name], defaults={"price": Decimal(price)},
            )


def unload_catalog(apps, schema_editor):
    apps.get_model("catalog", "ServicePrice").objects.filter(category__slug__in=CATEGORIES).delete()
    apps.get_model("catalog", "Item").objects.filter(name__in=ITEMS).delete()
    apps.get_model("catalog", "ServiceCategory").objects.filter(slug__in=CATEGORIES).delete()


class Migration(migrations.Migration):

    dependencies = [("catalog", "0001_initial")]

    operations = [migrations.RunPython(load_catalog, unload_catalog)]
