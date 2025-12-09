from django.db import models
from profiles.models import Profile


class Conversation(models.Model):
    participants = models.ManyToManyField(Profile, related_name="conversations")
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        names = ", ".join(self.participants.values_list("user__username", flat=True))
        return f"Conversation({names})"


class Message(models.Model):
    conversation = models.ForeignKey(
        Conversation, related_name="messages", on_delete=models.CASCADE
    )
    sender = models.ForeignKey(Profile, related_name="sent_messages", on_delete=models.CASCADE)
    text = models.TextField()
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created"]

    def __str__(self):
        return f"{self.sender} @ {self.created:%Y-%m-%d %H:%M}"


class MessageDraft(models.Model):
    profile = models.ForeignKey(Profile, related_name="message_drafts", on_delete=models.CASCADE)
    conversation = models.ForeignKey(
        Conversation, related_name="drafts", on_delete=models.CASCADE
    )
    text = models.TextField(blank=True, default="")
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("profile", "conversation")

    def __str__(self):
        return f"Draft({self.profile} -> {self.conversation_id})"
