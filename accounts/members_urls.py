"""The members directory and profiles, under /members/.

A separate URL module from the account pages because they are a separate
place on the site: /account/ is about you, /members/ is about everyone else.
"""

from django.urls import path

from . import views

app_name = "members"

urlpatterns = [
    path("", views.directory, name="directory"),
    # str rather than slug, so a mistyped capital letter reaches the view and
    # is redirected to the lowercase address instead of a bare 404.
    path("<str:handle>/", views.profile, name="profile"),
]
