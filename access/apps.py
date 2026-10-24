from django.apps import AppConfig


class AccessConfig(AppConfig):
    name = 'access'
    default_auto_field = 'django.db.models.BigAutoField'

    def ready(self):
        from . import signals  # noqa: F401  (connects sign-in / sign-out / failed sign-in logging)
