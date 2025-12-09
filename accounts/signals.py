from django.dispatch import receiver
from allauth.account.signals import user_signed_up, user_logged_in

from profiles.models import Profile


def ensure_profile(user, full_name=None, role=None):
    defaults = {}
    if full_name:
        defaults["headline"] = full_name
    if role:
        defaults["bio"] = role
    Profile.objects.update_or_create(user=user, defaults=defaults)


@receiver(user_signed_up)
def handle_social_signup(request, user, **kwargs):
    ensure_profile(user)


@receiver(user_logged_in)
def handle_login(request, user, **kwargs):
    ensure_profile(user)
