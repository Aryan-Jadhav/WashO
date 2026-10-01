from django.conf import settings
from django.contrib import messages
from django.core.mail import send_mail
from django.shortcuts import redirect, render

from .forms import ContactForm
from .models import FAQ

# Service categories shown on the public pages. In Phase 2 these come from the database.
SERVICE_HIGHLIGHTS = [
    {"icon": "basket", "name": "Laundry", "text": "Everyday wash for your regular clothes, charged by the item."},
    {"icon": "layers", "name": "Wash & Fold", "text": "Washed, dried and neatly folded, ready for the cupboard."},
    {"icon": "fire", "name": "Wash & Iron", "text": "Washed and steam-ironed, ready for office or college."},
    {"icon": "stars", "name": "Dry Clean", "text": "Gentle solvent cleaning for sarees, suits, silk and woollens."},
    {"icon": "bag-check", "name": "Shoe Cleaning", "text": "Deep cleaning for sneakers, sports and leather shoes."},
    {"icon": "house-heart", "name": "Home Textiles", "text": "Curtains, carpets, blankets and sofa covers."},
]


def home(request):
    return render(request, "core/home.html", {"services": SERVICE_HIGHLIGHTS})


def services(request):
    return render(request, "core/services.html", {"services": SERVICE_HIGHLIGHTS})


def about(request):
    return render(request, "core/about.html")


def faq(request):
    faqs = FAQ.objects.filter(is_active=True)
    return render(request, "core/faq.html", {"faqs": faqs})


def contact(request):
    if request.method == "POST":
        form = ContactForm(request.POST)
        if form.is_valid():  # server-side validation, even if the browser checks too
            msg = form.save()
            # Let support know (printed in the terminal while developing).
            send_mail(
                subject=f"[WashO contact] {msg.subject}",
                message=f"From: {msg.name} <{msg.email}> {msg.phone}\n\n{msg.message}",
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[settings.SUPPORT_EMAIL],
                fail_silently=True,
            )
            messages.success(request, "Thank you! We will get back to you within one working day.")
            # Redirect after POST so refreshing the page doesn't send the form twice.
            return redirect("core:contact")
    else:
        initial = {}
        if request.user.is_authenticated:
            initial = {"name": request.user.get_full_name(), "phone": request.user.phone, "email": request.user.email}
        form = ContactForm(initial=initial)
    return render(request, "core/contact.html", {"form": form})
