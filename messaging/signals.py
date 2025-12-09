from django.contrib.auth.signals import user_logged_out
from django.dispatch import receiver
from django.utils import timezone

from profiles.models import Profile


@receiver(user_logged_out)
def clear_message_available(sender, request, user, **kwargs):
    """
    Ensure message availability is turned off when a user logs out.
    """
    if not user:
        return
    try:
        profile = Profile.objects.get(user=user)
    except Profile.DoesNotExist:
        return
    if profile.message_available:
        profile.message_available = False
        profile.message_available_at = timezone.now()
        profile.save(update_fields=["message_available", "message_available_at"])
