from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import UserLanguagePreference


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_language_preference(sender, instance, created, **kwargs):
    if created:
        UserLanguagePreference.objects.get_or_create(user=instance)
