from django.conf import settings
from django.contrib import messages
from django.core.mail import send_mail
from django.db.models import Min, Q
from django.shortcuts import redirect, render

from catalog.models import ServiceCategory

from .forms import ContactForm
from .models import FAQ


def categories_with_starting_price():
    """Active categories plus their lowest active price ("starting from ₹X"), in one query."""
    return ServiceCategory.objects.filter(is_active=True).annotate(
        starting_price=Min("prices__price", filter=Q(prices__is_active=True, prices__item__is_active=True))
    )


def home(request):
    return render(request, "core/home.html", {"services": categories_with_starting_price()})


def services(request):
    return render(request, "core/services.html", {"services": categories_with_starting_price()})


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
