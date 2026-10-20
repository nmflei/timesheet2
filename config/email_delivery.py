from django.conf import settings
from django.utils.translation import gettext_lazy as _

EMAIL_CONFIGURATION_ERROR = _(
    "O envio de emails está incompleto. Configure no ficheiro .env o SMTP do seu fornecedor (EMAIL_HOST, EMAIL_PORT, EMAIL_HOST_USER, EMAIL_HOST_PASSWORD, EMAIL_USE_TLS/EMAIL_USE_SSL e DEFAULT_FROM_EMAIL). Use a credencial SMTP/palavra-passe de aplicação do fornecedor, não a palavra-passe normal da caixa de correio; depois recrie o serviço web com docker compose up -d --force-recreate web e tente novamente."
)


def email_delivery_is_configured():
    sender = settings.DEFAULT_FROM_EMAIL.casefold()
    return bool(
        settings.EMAIL_HOST.strip()
        and settings.EMAIL_HOST_USER.strip()
        and settings.EMAIL_HOST_PASSWORD
        and sender.strip()
        and "noreply@example.com" not in sender
    )
