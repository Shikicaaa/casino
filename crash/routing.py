from django.urls import path
from .consumers import CrashGameConsumer

websocket_urlpatterns = [
    path("ws/crash/", CrashGameConsumer.as_asgi()),
]
