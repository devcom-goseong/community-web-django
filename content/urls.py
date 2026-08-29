from django.urls import path

from . import views

app_name = "content"

urlpatterns = [
    path("", views.home, name="home"),
    path("about/", views.about, name="about"),
    path("activities/", views.activities, name="activities"),
    path("activities/<slug:slug>/", views.activity, name="activity"),
    path("join/", views.join, name="join"),
    path("questions/", views.faq, name="faq"),
    path("interests/", views.interests, name="interests"),
    path("resources/", views.resources, name="resources"),
    path("contents/", views.contents, name="contents"),
    # Catch-all for the prose pages. Must stay last.
    path("<slug:slug>/", views.page, name="page"),
]
