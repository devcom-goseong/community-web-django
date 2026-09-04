from django.contrib import admin
from django.urls import include, path

from applications.views import health

admin.site.site_header = "KDU Developer Community"
admin.site.site_title = "KDU Developer Community"
admin.site.index_title = "Applications and enquiries"

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("applications.urls")),
    path("account/", include("accounts.urls")),
    path("healthz", health, name="health"),
    # Last, because it owns the catch-all slug route for prose pages.
    path("", include("content.urls")),
]
