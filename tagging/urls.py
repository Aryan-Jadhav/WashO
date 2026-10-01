from django.urls import path

from . import views

app_name = "tagging"

urlpatterns = [
    path("", views.panel, name="panel"),
    path("alerts/", views.alerts, name="alerts"),
    path("alerts/<int:pk>/resolve/", views.alert_resolve, name="alert_resolve"),
    path("tag/", views.garment_lookup, name="garment_search"),
    path("tag/<str:tag_code>/", views.garment_lookup, name="garment_lookup"),
    path("orders/<str:code>/", views.order_detail, name="order"),
    path("orders/<str:code>/step/", views.order_step, name="order_step"),
    path("orders/<str:code>/garments/add/", views.garment_add, name="garment_add"),
    path("orders/<str:code>/garments/<int:seq>/edit/", views.garment_edit, name="garment_edit"),
    path("orders/<str:code>/garments/<int:seq>/delete/", views.garment_delete, name="garment_delete"),
    path("orders/<str:code>/finish-tagging/", views.tagging_finish, name="finish_tagging"),
    path("orders/<str:code>/tags/", views.tags_print, name="tags_print"),
]
