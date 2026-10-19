from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class TimesheetsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "timesheets"
    verbose_name = _("Folhas de horas")

    def ready(self):
        from . import signals  # noqa: F401
