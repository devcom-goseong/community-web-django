from django.apps import AppConfig


class EventsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "events"
    verbose_name = "Events"

    def ready(self):
        from . import signals  # noqa: F401  (connects the receivers)
