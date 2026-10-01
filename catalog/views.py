from itertools import groupby

from django.shortcuts import render

from core.htmx import is_htmx, vary_on_htmx

from .forms import PriceSearchForm
from .models import ServiceCategory, ServicePrice


def active_prices():
    """Prices that should be visible: price, category and item must all be active."""
    return ServicePrice.objects.filter(
        is_active=True, category__is_active=True, item__is_active=True,
    ).select_related("category", "item")  # 1 query with JOINs instead of 1 query per row


def price_list(request):
    form = PriceSearchForm(request.GET or None)
    prices = active_prices()
    selected_category = None

    if form.is_valid():
        selected_category = form.cleaned_data["category"]
        q = form.cleaned_data["q"]
        if selected_category:
            prices = prices.filter(category=selected_category)
        if q:
            prices = prices.filter(item__name__icontains=q)
    elif form.is_bound:
        prices = prices.none()  # invalid filter (e.g. unknown category) -> show the error, no rows

    prices = prices.order_by("category__sort_order", "category__name", "item__sort_order", "item__name")
    # Group rows by category so the template can print one table per service.
    groups = [(cat, list(rows)) for cat, rows in groupby(prices, key=lambda p: p.category)]

    context = {
        "form": form,
        "groups": groups,
        "categories": ServiceCategory.objects.filter(is_active=True),
        "selected_category": selected_category,
        "query": request.GET.get("q", ""),
    }
    # HTMX live search only needs the results table, not the whole page.
    template = "catalog/_price_results.html" if is_htmx(request) else "catalog/price_list.html"
    return vary_on_htmx(render(request, template, context))
