from django.urls import path

from . import views

app_name = "payments"

urlpatterns = [
    path("invoice/<str:code>/", views.invoice_pdf, name="invoice"),
]
