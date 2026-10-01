from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("register/", views.register, name="register"),
    path("welcome/", views.after_login, name="after_login"),
    path("", views.account, name="account"),
    path("profile/", views.profile_edit, name="profile_edit"),
    path("password/", views.WashOPasswordChangeView.as_view(), name="password_change"),
    path("addresses/", views.address_list, name="address_list"),
    path("addresses/new/", views.address_create, name="address_create"),
    path("addresses/<int:pk>/edit/", views.address_edit, name="address_edit"),
    path("addresses/<int:pk>/delete/", views.address_delete, name="address_delete"),
]
