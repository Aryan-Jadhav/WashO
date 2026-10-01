from django.conf import settings


def site_info(request):
    """Values every template needs (brand name, support contacts)."""
    return {
        "SITE_NAME": "WashO",
        "SUPPORT_EMAIL": settings.SUPPORT_EMAIL,
        "SUPPORT_PHONE": settings.SUPPORT_PHONE,
    }
