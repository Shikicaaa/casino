import os
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from crash.routing import websocket_urlpatterns as crash_websocket_urlpatterns
from roulette.routing import websocket_urlpatterns as roulette_websocket_urlpatterns

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "kockarnica.settings")

websocket_urlpatterns = crash_websocket_urlpatterns + roulette_websocket_urlpatterns

application = ProtocolTypeRouter({
    "http": get_asgi_application(),
    "websocket": AuthMiddlewareStack(
        URLRouter(websocket_urlpatterns),
    ),
})