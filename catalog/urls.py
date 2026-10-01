from django.urls import path

from . import views

app_name = "catalog"

urlpatterns = [
    path("", views.price_list, name="price_list"),
]
