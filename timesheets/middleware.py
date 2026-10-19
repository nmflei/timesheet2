from django.conf import settings
from django.middleware.locale import LocaleMiddleware
from django.utils import translation

from .models import UserLanguagePreference


class UserPreferenceLocaleMiddleware(LocaleMiddleware):
    def process_request(self, request):
        if request.user.is_authenticated:
            try:
                preference = request.user.language_preference
            except UserLanguagePreference.DoesNotExist:
                preference = None
            if preference and preference.language in dict(settings.LANGUAGES):
                language = preference.language
                translation.activate(language)
                request.LANGUAGE_CODE = language
                return
        super().process_request(request)
