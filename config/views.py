from django.conf import settings
from django.contrib.auth import views as auth_views

from .email_delivery import EMAIL_CONFIGURATION_ERROR, email_delivery_is_configured


class ConfiguredPasswordResetView(auth_views.PasswordResetView):
    def form_valid(self, form):
        if (
            not email_delivery_is_configured()
            and settings.EMAIL_BACKEND
            != "django.core.mail.backends.console.EmailBackend"
        ):
            form.add_error(None, EMAIL_CONFIGURATION_ERROR)
            return self.form_invalid(form)
        return super().form_valid(form)
