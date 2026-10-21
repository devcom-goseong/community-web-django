from django.urls import path

from . import views

app_name = "posters"

urlpatterns = [
    path("<str:token>/", views.present, name="present"),
]
