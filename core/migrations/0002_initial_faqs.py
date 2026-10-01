# Data migration: starter FAQ entries (the admin can edit them later).

from django.db import migrations

FAQS = [
    ("How do I book a pickup?",
     "Sign up with your mobile number, choose your services, pick a date and time slot, and confirm. "
     "Our delivery agent will come to your address in that slot."),
    ("Is pickup and delivery free?",
     "Yes, pickup and delivery are free. You only pay for the cleaning services."),
    ("How is my bill calculated?",
     "When you book, we show an estimated total based on the approximate item counts you enter. "
     "The final bill is made at the store from the garments actually received and tagged, using our per-item price list."),
    ("How do you make sure my clothes don't go missing?",
     "Every garment gets its own QR-code tag at the store. We count your clothes at pickup, at the store and at delivery. "
     "If any count doesn't match, our admin team is alerted straight away."),
    ("What if a garment is already stained or damaged?",
     "Our staff note any existing stain or damage (with a photo) while tagging, before cleaning starts, so you are informed early."),
    ("How long does it take?",
     "Standard orders are usually delivered within 48 hours. Choose Express for faster delivery at a small extra charge."),
    ("How can I pay?",
     "You can pay online (UPI, cards, net banking) or choose Cash on Delivery."),
    ("Can I cancel my order?",
     "Yes. You can cancel any time before our agent picks up your clothes."),
    ("I have a problem with my order. What should I do?",
     "Open the order from 'My orders' and raise a complaint. Our support team will follow it up until it is resolved."),
]


def add_faqs(apps, schema_editor):
    FAQ = apps.get_model("core", "FAQ")
    for i, (q, a) in enumerate(FAQS, start=1):
        FAQ.objects.get_or_create(question=q, defaults={"answer": a, "sort_order": i * 10})


def remove_faqs(apps, schema_editor):
    FAQ = apps.get_model("core", "FAQ")
    FAQ.objects.filter(question__in=[q for q, _ in FAQS]).delete()


class Migration(migrations.Migration):

    dependencies = [("core", "0001_initial")]

    operations = [migrations.RunPython(add_faqs, remove_faqs)]
