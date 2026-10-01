from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("register/", views.register, name="register"),
    path("welcome/", views.after_login, name="after_login"),
    path("", views.account, name="account"),
    path("profile/", views.profile_edit, name="profile_edit"),
    path("password/", views.WashOPasswordChangeView.as_view(), name="password_change"),
]
