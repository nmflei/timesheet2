from django.conf import settings
from django.contrib.auth import views as auth_views
from django.utils.translation import gettext_lazy as _


class ConfiguredPasswordResetView(auth_views.PasswordResetView):
    def form_valid(self, form):
        if not settings.DEBUG and not settings.EMAIL_HOST:
            form.add_error(
                None,
                _("O envio de emails não está configurado. Contacte o administrador."),
            )
            return self.form_invalid(form)
        return super().form_valid(form)
