from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse, HttpResponseBadRequest
from django.shortcuts import redirect, render
from django.views import View
from django.db.models import Q, Prefetch
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from datetime import timedelta

from profiles.models import Profile, Connection
from .models import Conversation, Message, MessageDraft


class MessagesView(LoginRequiredMixin, View):
    template_name = "messaging/inbox.html"

    def get(self, request):
        me, _ = Profile.objects.get_or_create(user=request.user)
        connected_profiles = []
        for c in Connection.objects.filter(
            Q(requester=me, status="accepted") | Q(receiver=me, status="accepted")
        ):
            other = c.receiver if c.requester == me else c.requester
            connected_profiles.append(other)

        threads = []
        now = timezone.now()
        presence_ttl = timedelta(seconds=2)
        for other in connected_profiles:
            conv = (
                Conversation.objects.filter(participants=me)
                .filter(participants=other)
                .first()
            )
            if not conv:
                conv = Conversation.objects.create()
                conv.participants.add(me, other)
            last_msg = conv.messages.last()
            is_online = bool(
                other.message_available
                and other.message_available_at
                and other.message_available_at >= now - presence_ttl
            )
            threads.append(
                {
                    "conv": conv,
                    "other": other,
                    "last_msg": last_msg,
                    "is_online": is_online,
                }
            )

        threads = sorted(
            threads,
            key=lambda x: x["last_msg"].created if x["last_msg"] else x["conv"].updated,
            reverse=True,
        )
        conversation_id = request.GET.get("conversation")
        active = None
        if conversation_id:
            for t in threads:
                if str(t["conv"].id) == str(conversation_id):
                    active = t["conv"]
                    break
        if active is None and threads:
            active = threads[0]["conv"]
        messages = active.messages.all() if active else []
        active_other = active.participants.exclude(pk=me.pk).first() if active else None
        draft_text = ""
        if active:
            draft = MessageDraft.objects.filter(profile=me, conversation=active).first()
            draft_text = draft.text if draft else ""
        context = {
            "profile": me,
            "threads": threads,
            "active": active,
            "messages": messages,
            "active_other": active_other,
            "draft_text": draft_text,
        }
        return render(request, self.template_name, context)

    def post(self, request):
        me, _ = Profile.objects.get_or_create(user=request.user)
        conversation_id = request.POST.get("conversation_id")
        text = request.POST.get("text", "").strip()
        if not text:
            return redirect(request.path)
        try:
            conv = Conversation.objects.get(pk=conversation_id, participants=me)
        except Conversation.DoesNotExist:
            return redirect(request.path)
        Message.objects.create(conversation=conv, sender=me, text=text)
        conv.updated = timezone.now()
        conv.save(update_fields=["updated"])
        channel_layer = get_channel_layer()
        payload = {
            "kind": "message",
            "sender": me.user.get_full_name() or me.user.username,
            "text": text,
            "timestamp": timezone.now().strftime("%-I:%M %p"),
        }
        async_to_sync(channel_layer.group_send)(
            f"chat_{conv.id}", {"type": "chat.message", "payload": payload}
        )
        return redirect(f"{request.path}?conversation={conv.id}")


@method_decorator(csrf_exempt, name="dispatch")
class MessageAvailabilityView(LoginRequiredMixin, View):
    """
    Allows the frontend to mark the current user as available/unavailable for messaging
    and query availability of other profiles.
    """

    def post(self, request):
        me, _ = Profile.objects.get_or_create(user=request.user)
        available_raw = request.POST.get("available") or request.GET.get("available")
        val = str(available_raw).lower() if available_raw is not None else ""
        true_vals = ["1", "true", "yes", "on"]
        false_vals = ["0", "false", "off", "no"]
        if val in true_vals:
            desired_state = True
        elif val in false_vals:
            desired_state = False
        else:
            return JsonResponse({"status": "ignored", "available": me.message_available})

        me.message_available = desired_state
        me.message_available_at = timezone.now()
        me.save(update_fields=["message_available", "message_available_at"])
        return JsonResponse({"status": "ok", "available": me.message_available})

    def get(self, request):
        ids_param = request.GET.get("ids", "")
        try:
            ids = [int(i) for i in ids_param.split(",") if i.strip().isdigit()]
        except ValueError:
            ids = []
        now = timezone.now()
        presence_ttl = timedelta(seconds=2)
        states = {}
        for p in Profile.objects.filter(id__in=ids).values(
            "id", "message_available", "message_available_at"
        ):
            active = bool(
                p["message_available"]
                and p["message_available_at"]
                and p["message_available_at"] >= now - presence_ttl
            )
            states[p["id"]] = active
        return JsonResponse({"states": states})


class TypingStatusView(LoginRequiredMixin, View):
    """
    Fallback endpoint to broadcast typing indicators when WebSocket isn't available.
    """

    def post(self, request):
        me, _ = Profile.objects.get_or_create(user=request.user)
        conversation_id = request.POST.get("conversation_id")
        if not conversation_id:
            return HttpResponseBadRequest("conversation_id required")
        try:
            conv = Conversation.objects.get(pk=conversation_id, participants=me)
        except Conversation.DoesNotExist:
            return HttpResponseBadRequest("invalid conversation")

        typing_flag = str(request.POST.get("typing", "")).lower() in ["1", "true", "yes", "on"]
        channel_layer = get_channel_layer()
        payload = {
            "kind": "typing",
            "sender": me.user.get_full_name() or me.user.username,
            "typing": typing_flag,
        }
        async_to_sync(channel_layer.group_send)(
            f"chat_{conv.id}", {"type": "chat.message", "payload": payload}
        )
        return JsonResponse({"status": "ok"})


class MessageDraftView(LoginRequiredMixin, View):
    """
    Save or clear a user's draft for a conversation.
    """

    def post(self, request):
        me, _ = Profile.objects.get_or_create(user=request.user)
        conversation_id = request.POST.get("conversation_id")
        if not conversation_id:
            return HttpResponseBadRequest("conversation_id required")
        try:
            conv = Conversation.objects.get(pk=conversation_id, participants=me)
        except Conversation.DoesNotExist:
            return HttpResponseBadRequest("invalid conversation")

        text = request.POST.get("text", "")
        text = text if text is not None else ""
        text = text.strip()
        draft, _ = MessageDraft.objects.get_or_create(profile=me, conversation=conv)
        if text:
            if draft.text != text:
                draft.text = text
                draft.save(update_fields=["text", "updated"])
        else:
            if draft.pk:
                draft.delete()
        return JsonResponse({"status": "ok"})
