from django.db.models import Prefetch, Q
from django.shortcuts import render

from core.htmx import is_htmx, vary_on_htmx

from .forms import StoreSearchForm
from .models import ServiceArea, Store


def store_locator(request):
    form = StoreSearchForm(request.GET or None)
    stores = Store.objects.filter(is_active=True).select_related("city").prefetch_related(
        # Load each store's active areas in ONE extra query (not one per store).
        Prefetch("areas", queryset=ServiceArea.objects.filter(is_active=True), to_attr="active_areas")
    )
    pincode = None
    matched_areas = []

    if form.is_valid():
        city = form.cleaned_data["city"]
        q = form.cleaned_data["q"]
        if city:
            stores = stores.filter(city=city)
        if form.pincode:
            pincode = form.pincode
            # Which localities with this pincode do we serve, and from which store?
            matched_areas = list(
                ServiceArea.objects.filter(pincode=pincode, is_active=True, store__is_active=True)
                .select_related("store")
            )
            stores = stores.filter(Q(pincode=pincode) | Q(areas__pincode=pincode, areas__is_active=True))
        elif q:
            stores = stores.filter(
                Q(name__icontains=q) | Q(locality__icontains=q) | Q(address__icontains=q)
                | Q(areas__name__icontains=q, areas__is_active=True)
            )
        stores = stores.distinct()  # a store can match through several areas
    elif form.is_bound:
        stores = stores.none()

    context = {
        "form": form,
        "stores": stores,
        "pincode": pincode,
        "matched_areas": matched_areas,
        "searched": form.is_bound,
    }
    template = "stores/_store_results.html" if is_htmx(request) else "stores/store_locator.html"
    return vary_on_htmx(render(request, template, context))
