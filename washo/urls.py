from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path

from accounts.forms import PhoneLoginForm

admin.site.site_header = "WashO Administration"
admin.site.site_title = "WashO Admin"
admin.site.index_title = "Master data & management"

urlpatterns = [
    path("admin/", admin.site.urls),
    path(
        "login/",
        auth_views.LoginView.as_view(authentication_form=PhoneLoginForm, redirect_authenticated_user=True),
        name="login",
    ),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),  # POST only (safer)
    path("account/", include("accounts.urls")),
    path("prices/", include("catalog.urls")),
    path("stores/", include("stores.urls")),
    path("orders/", include("orders.urls")),
    path("staff/", include("tagging.urls")),
    path("agent/", include("delivery.urls")),
    path("payments/", include("payments.urls")),
    path("", include("core.urls")),
]

if settings.DEBUG:
    # Serve uploaded files (e.g. damage photos) while developing.
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
