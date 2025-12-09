from django.conf import settings
from django.db import models


class Profile(models.Model):
    """
    Legacy signup metadata; kept with a distinct related_name to avoid clashing
    with the profiles.Profile model that powers the dashboard.
    """

    ROLE_CLIENT = "client"
    ROLE_DEVELOPER = "developer"
    ROLE_CHOICES = [
        (ROLE_CLIENT, "Client (Looking for developers)"),
        (ROLE_DEVELOPER, "Developer (Looking for projects)"),
    ]

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="legacy_profile"
    )
    full_name = models.CharField(max_length=150)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)

    def __str__(self):
        return f"{self.full_name} ({self.get_role_display()})"
