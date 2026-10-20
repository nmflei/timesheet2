from django.conf import settings
from django.middleware.locale import LocaleMiddleware
from django.utils import translation


class SessionLocaleMiddleware(LocaleMiddleware):
    def process_request(self, request):
        language = request.COOKIES.get(settings.SESSION_LANGUAGE_COOKIE_NAME)
        if language not in dict(settings.LANGUAGES):
            language = settings.LANGUAGE_CODE
        translation.activate(language)
        request.LANGUAGE_CODE = language

    def process_response(self, request, response):
        response = super().process_response(request, response)
        if settings.LANGUAGE_COOKIE_NAME in request.COOKIES:
            response.delete_cookie(
                settings.LANGUAGE_COOKIE_NAME,
                path=settings.LANGUAGE_COOKIE_PATH,
                domain=settings.LANGUAGE_COOKIE_DOMAIN,
            )
        return response
