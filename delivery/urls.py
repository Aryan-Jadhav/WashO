from django.urls import path

from . import views

app_name = "delivery"

urlpatterns = [
    # Agent panel
    path("", views.my_jobs, name="my_jobs"),
    path("jobs/<str:code>/", views.job, name="job"),
    path("jobs/<str:code>/pickup/", views.job_pickup, name="job_pickup"),
    path("jobs/<str:code>/start-delivery/", views.job_start_delivery, name="job_start_delivery"),
    path("jobs/<str:code>/deliver/", views.job_deliver, name="job_deliver"),
    # Used from the staff panel
    path("assign/<str:code>/pickup/", views.assign_pickup, name="assign_pickup"),
    path("assign/<str:code>/delivery/", views.assign_delivery, name="assign_delivery"),
]
