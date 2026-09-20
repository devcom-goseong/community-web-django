from django.contrib import admin
from django.contrib.sitemaps.views import sitemap
from django.urls import include, path

from applications.views import health
from content.sitemaps import SITEMAPS

admin.site.site_header = "KDU Developer Community"
admin.site.site_title = "KDU Developer Community"
admin.site.index_title = "Members, events and applications"

urlpatterns = [
    # The Django admin lives at an unguessable path rather than /admin/.
    path("royal-jelly/", admin.site.urls),
    path("api/", include("applications.urls")),
    path("account/", include("accounts.urls")),
    path("members/", include("accounts.members_urls")),
    path("events/", include("events.urls")),
    path("healthz", health, name="health"),
    path("sitemap.xml", sitemap, {"sitemaps": SITEMAPS},
         name="django.contrib.sitemaps.views.sitemap"),
    # Last, because it owns the catch-all slug route for prose pages.
    path("", include("content.urls")),
]
