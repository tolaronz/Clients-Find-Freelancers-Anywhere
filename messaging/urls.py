from django.urls import path

from .views import MessagesView, MessageAvailabilityView, TypingStatusView, MessageDraftView

app_name = "messaging"

urlpatterns = [
    path("", MessagesView.as_view(), name="inbox"),
    path("presence/", MessageAvailabilityView.as_view(), name="presence"),
    path("typing/", TypingStatusView.as_view(), name="typing"),
    path("draft/", MessageDraftView.as_view(), name="draft"),
]
