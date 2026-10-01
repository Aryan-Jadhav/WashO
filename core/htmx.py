from django.utils.cache import patch_vary_headers


def is_htmx(request):
    """True when HTMX asked for just a piece of the page (not a full page load).

    History-restore requests (browser Back button) need the full page, so they
    are treated as normal requests.
    """
    return request.headers.get("HX-Request") == "true" and not request.headers.get("HX-History-Restore-Request")


def vary_on_htmx(response):
    # WHY: the same URL returns a full page or a fragment; tell caches they differ.
    patch_vary_headers(response, ["HX-Request"])
    return response
