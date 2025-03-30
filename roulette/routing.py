from django.urls import path
from .consumers import RouletteConsumer

websocket_urlpatterns = [
    path("ws/roulette/", RouletteConsumer.as_asgi()),
]
