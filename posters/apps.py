from django.apps import AppConfig


class PostersConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "posters"
    verbose_name = "Talk posters"

    def ready(self):
        from . import signals  # noqa: F401
