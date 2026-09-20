from django.urls import path

from . import views

app_name = "vault"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("unlock/", views.unlock, name="unlock"),
    path("lock/", views.lock, name="lock"),
    # These come before the bare <label> list so "unlock"/"lock" are not read
    # as section labels. Labels are "app_label.model_name", e.g. "events.event".
    path("<str:label>/", views.object_list, name="list"),
    path("<str:label>/add/", views.object_edit, name="add"),
    path("<str:label>/<str:pk>/edit/", views.object_edit, name="edit"),
    path("<str:label>/<str:pk>/delete/", views.object_delete, name="delete"),
]
