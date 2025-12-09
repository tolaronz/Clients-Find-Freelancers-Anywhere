from django.urls import resolve, Resolver404
from django.utils import timezone

from profiles.models import Profile


class MessageAvailabilityMiddleware:
    """
    Marks whether a user is currently viewing the messaging area.
    Sets Profile.message_available True on messaging routes and False elsewhere
    (logout is also handled via signal).
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        user = getattr(request, "user", None)
        if not user or not user.is_authenticated:
            return response

        try:
            match = resolve(request.path_info)
            in_messages = match.namespace == "messaging"
        except Resolver404:
            in_messages = False

        profile, _ = Profile.objects.get_or_create(user=user)
        desired_state = bool(in_messages)
        if profile.message_available != desired_state or desired_state:
            profile.message_available = desired_state
            profile.message_available_at = timezone.now()
            profile.save(update_fields=["message_available", "message_available_at"])

        return response
