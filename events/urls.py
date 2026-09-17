from django.urls import path

from . import views

app_name = "events"

urlpatterns = [
    path("", views.event_list, name="list"),
    path("<slug:slug>/", views.event_detail, name="detail"),
    path("<slug:slug>/register/", views.event_register, name="register"),
    path("<slug:slug>/cancel/", views.event_cancel, name="cancel"),
    path("<slug:slug>/calendar.ics", views.event_calendar, name="calendar"),
]
