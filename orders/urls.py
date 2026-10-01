from django.urls import path

from . import views

app_name = "orders"

urlpatterns = [
    path("book/", views.book, name="book"),
    path("book/estimate/", views.book_estimate, name="book_estimate"),
    path("book/slots/", views.slot_options, name="slot_options"),
    path("", views.order_list, name="list"),
    path("<str:code>/", views.order_detail, name="detail"),
    path("<str:code>/status/", views.order_status_partial, name="status_partial"),
    path("<str:code>/cancel/", views.order_cancel, name="cancel"),
]
