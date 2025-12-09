import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.utils import timezone

from profiles.models import Profile
from .models import Conversation, Message


class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.conversation_id = self.scope["url_route"]["kwargs"]["conversation_id"]
        self.room_group_name = f"chat_{self.conversation_id}"
        user = self.scope["user"]
        if not user.is_authenticated:
            await self.close()
            return
        allowed = await self._is_participant(user.id, self.conversation_id)
        if not allowed:
            await self.close()
            return
        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, code):
        await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

    async def receive(self, text_data=None, bytes_data=None):
        if not text_data:
            return
        data = json.loads(text_data)
        user = self.scope["user"]
        if not user.is_authenticated:
            return

        # Typing indicator
        if "typing" in data:
            sender_name = user.get_full_name() or user.username
            raw = data.get("typing")
            if isinstance(raw, bool):
                is_typing = raw
            else:
                val = str(raw).lower()
                is_typing = val in ["1", "true", "yes", "on"]
            await self._broadcast_typing(sender_name, is_typing)
            return

        # Chat message
        message = data.get("message", "").strip()
        if not message:
            return
        msg_obj = await self._save_message(user.id, self.conversation_id, message)
        payload = {
            "kind": "message",
            "sender": msg_obj["sender"],
            "text": msg_obj["text"],
            "timestamp": msg_obj["timestamp"],
        }
        await self.channel_layer.group_send(
            self.room_group_name, {"type": "chat.message", "payload": payload}
        )

    async def chat_message(self, event):
        await self.send(text_data=json.dumps(event["payload"]))

    @database_sync_to_async
    def _is_participant(self, user_id, conversation_id):
        try:
            conv = Conversation.objects.get(pk=conversation_id)
        except Conversation.DoesNotExist:
            return False
        return conv.participants.filter(user_id=user_id).exists()

    @database_sync_to_async
    def _save_message(self, user_id, conversation_id, text):
        sender = Profile.objects.get(user_id=user_id)
        conv = Conversation.objects.get(pk=conversation_id)
        msg = Message.objects.create(conversation=conv, sender=sender, text=text)
        conv.updated = timezone.now()
        conv.save(update_fields=["updated"])
        return {
            "sender": sender.user.get_full_name() or sender.user.username,
            "text": msg.text,
            "timestamp": msg.created.strftime("%-I:%M %p"),
        }

    async def _broadcast_typing(self, sender_name, is_typing):
        payload = {
            "kind": "typing",
            "sender": sender_name,
            "typing": is_typing,
        }
        await self.channel_layer.group_send(
            self.room_group_name, {"type": "chat.message", "payload": payload}
        )
