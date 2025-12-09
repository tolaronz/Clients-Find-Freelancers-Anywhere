"""
ASGI config for network_platform project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.2/howto/deployment/asgi/
"""

import os

from django.core.asgi import get_asgi_application
from django.contrib.staticfiles.handlers import ASGIStaticFilesHandler
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from django.conf import settings

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'network_platform.settings')

django_asgi_app = get_asgi_application()

import network_platform.routing  # noqa: E402

application = ProtocolTypeRouter(
    {
        "http": ASGIStaticFilesHandler(django_asgi_app) if settings.DEBUG else django_asgi_app,
        "websocket": AuthMiddlewareStack(
            URLRouter(network_platform.routing.websocket_urlpatterns)
        ),
    }
)
