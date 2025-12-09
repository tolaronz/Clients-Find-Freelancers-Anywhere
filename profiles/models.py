from django.conf import settings
from django.db import models
from django.utils import timezone
from datetime import date


def avatar_upload_path(instance, filename):
    return f"avatars/{instance.user.username}/{filename}"


class Profile(models.Model):
    """
    Extended user profile.
    - skills stored as a JSON list of strings
    - experience is a related model (Experience) for structure
    """

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile"
    )
    headline = models.CharField(max_length=140, blank=True)
    bio = models.TextField(blank=True)
    about = models.TextField(blank=True, default="About yourself")
    skills = models.JSONField(default=list, blank=True)  # e.g. ["python","django"]
    goals = models.TextField(blank=True)
    profile_picture = models.ImageField(
        upload_to=avatar_upload_path, blank=True, null=True
    )
    location = models.CharField(max_length=255, blank=True)
    share_enabled = models.BooleanField(default=True)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    views = models.PositiveIntegerField(default=0)
    ROLE_CLIENT = "client"
    ROLE_DEVELOPER = "developer"
    ROLE_CHOICES = [
        (ROLE_CLIENT, "Client"),
        (ROLE_DEVELOPER, "Developer"),
    ]
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default=ROLE_DEVELOPER)
    membership_tier = models.CharField(
        max_length=10,
        choices=[("common", "Common"), ("plus", "Plus"), ("pro", "Pro")],
        default="common",
    )
    message_available = models.BooleanField(default=False)
    message_available_at = models.DateTimeField(blank=True, null=True)
    active_connections = models.PositiveIntegerField(default=0)
    remaining_connections = models.PositiveIntegerField(default=2)
    last_connection_reset = models.DateField(blank=True, null=True)

    def __str__(self):
        return f"Profile({self.user.username})"

    def get_primary_skill(self):
        return self.skills[0] if self.skills else None

    @property
    def connection_limit(self):
        if self.membership_tier == "common":
            return 2
        if self.membership_tier == "plus":
            return 5
        return None  # pro = unlimited

    def reset_daily_connections(self, save=True):
        limit = self.connection_limit
        if limit is None:
            return
        today = date.today()
        if self.last_connection_reset != today:
            self.remaining_connections = limit
            self.last_connection_reset = today
            if save:
                self.save(update_fields=["remaining_connections", "last_connection_reset"])


class Experience(models.Model):
    profile = models.ForeignKey(
        Profile, related_name="experiences", on_delete=models.CASCADE
    )
    title = models.CharField(max_length=200)
    company = models.CharField(max_length=200, blank=True)
    location = models.CharField(max_length=200, blank=True)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    is_current = models.BooleanField(default=False)
    description = models.TextField(blank=True)
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-start_date", "-created"]

    def __str__(self):
        return f"{self.title} @ {self.company or '—'}"


class Connection(models.Model):
    STATUS_PENDING = "pending"
    STATUS_ACCEPTED = "accepted"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_ACCEPTED, "Accepted"),
    ]

    requester = models.ForeignKey(
        Profile, related_name="sent_connections", on_delete=models.CASCADE
    )
    receiver = models.ForeignKey(
        Profile, related_name="received_connections", on_delete=models.CASCADE
    )
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING
    )
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("requester", "receiver")

    def __str__(self):
        return f"{self.requester} -> {self.receiver} ({self.status})"
