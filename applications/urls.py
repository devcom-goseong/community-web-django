from django.urls import path

from . import views

app_name = "applications"

urlpatterns = [
    path("register", views.register, name="register"),
]
