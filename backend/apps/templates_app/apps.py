from django.apps import AppConfig


class TemplatesAppConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.templates_app"

    def ready(self):
        from apps.templates_app import signals  # noqa: F401
