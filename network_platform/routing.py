from django.urls import path, include

from messaging.routing import websocket_urlpatterns as messaging_ws

websocket_urlpatterns = [
    *messaging_ws,
]
