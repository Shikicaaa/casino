import asyncio
import json
import hashlib
import secrets
from django.core.cache import cache
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.layers import get_channel_layer
import random as rnd
import jwt
from django.conf import settings
from channels.db import database_sync_to_async
from urllib.parse import parse_qs
from users.models import get_user_from_token

waiting_queue = []

class RouletteConsumer(AsyncWebsocketConsumer):
    server_seed = None
    client_seed = "default_client_seed"
    nonce = 0
    hash_server_seed = None
    outcome = None
    channel_layer = None
    active_users = {}
    current_game = None
    connected = False
    game_running = False
    user = None
    async def keep_alive(self):
        while True:
            try:

                cache.set("websocket_connected", True, timeout=40)
                await asyncio.sleep(20)

            except Exception as e:
                print(f"Ping error: {e}")
                break

    

    async def connect(self):
        await self.accept()
        print("Websocket connection with roulette established.")

        if self.active_users is None:
            self.active_users = {}

        self.user = await get_user_from_token(self.scope["query_string"])
        if not self.user:
            await self.send(json.dumps({"error" : "Authentication failed"}))
            await self.close()
            return

        await self.channel_layer.group_add("roulette", self.channel_name)
        print("User added to roulette group")

        await self.send(json.dumps({"status": "connected"}))
        cache.set("websocket_connected", True)

        if self.game_running:
            await self.send(json.dumps({"hashed_server_seed": f"{self.hash_server_seed}"}))
    
    async def disconnect(self, code):
        cache.set("websocket_connected", False)
        await self.channel_layer.group_discard("roulette", self.channel_name)
        print(f"User disconnected from roulette group (code {code})")
    
    async def receive(self, text_data):
        if self.user.is_authenticated:
            data = json.loads(text_data)
            