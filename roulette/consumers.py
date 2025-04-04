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

    @database_sync_to_async
    def get_game(self, game_id = None):
        from .models import CrashGame
        return CrashGame.objects.get(id=game_id) if game_id else CrashGame.objects.order_by("-id").first()

    @database_sync_to_async
    def get_user(self, user_id):
        from users.models import User
        return User.objects.get(id=user_id)
    
    async def get_user_from_token(self, query_string):
        try:

            params = dict(q.split("=") for q in query_string.decode().split("&"))
            token = params.get("token", None)
            
            if not token:
                print("Token not found in query string")
                return

            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])

            if not payload:
                return
            
            user_id = payload.get("id", None)
            if user_id is None:
                print("User ID not found in token payload.")
                return None
            
            from asgiref.sync import sync_to_async
            from users.models import User

            user = await sync_to_async(User.objects.get)(id=user_id)
            print(f"User found: {user}")
            return user
        except jwt.ExpiredSignatureError:
            print("Token has expired")
            return
        except jwt.InvalidTokenError:
            print("Invalid token")
        except Exception as e:
            print(f"Desila se greska {e}")
            return

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

        self.user = await self.get_user_from_token(self.scope["query_string"])
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
            data["user_id"] = self.user.id
            data["balance"] = self.user.balance
            action = data.get("action")

            if action == "join":
                user_id = data.get("user_id")
                bet_amount = data.get("bet_amount")
                type = data.get("type")
                user = await self.get_user(user_id)
                if bet_amount < 0.1:
                    await self.send(json.dumps({
                        "status" : "error",
                        "message" : "Bet must be greater than 0.1!"
                    }))
                    return
                if bet_amount > user.balance:
                    await self.send(json.dumps({
                        "status" : "error",
                        "message" : "Insufficient funds."
                    }))
                    return
                game_user = await self.add_user_to_game(user_id, bet_amount,type)



    @classmethod
    async def add_user_to_game(cls, user_id, bet_amount,type):
        from asgiref.sync import sync_to_async
        from users.models import User
        from .models import RouletteGameUser
        game = await cls.get_game()
        user = await sync_to_async(User.objects.get)(id=user_id)

        if game.game_running:
            waiting_queue.append(
                {
                    "user_id" : user_id,
                    "bet_amount" : bet_amount
                }
            )
            print(f"User {user_id} added to waiting queue")
            return None
        game_user = await sync_to_async(RouletteGameUser.objects.create)(
            game=game,
            user=user,
            bet_amount=bet_amount
        )

        cls.active_users[user_id] = {
            "bet_amount" : bet_amount,
            "type" : type,
        }
        print(f"User {user_id} joined game {game.id} with bet amount {bet_amount}")
        await cls.take_money(user_id)
        return game_user
    
    @classmethod
    async def take_money(cls, user_id):
        from users.models import User
        user = User.objects.get(id=user_id)
        bet_amount = cls.active_users.get(user_id, {}).get("bet_amount", 0)

        if bet_amount > 0:
            user.balance -= bet_amount
            user.save()
            print(f"Oduzet novac: {bet_amount}. Novi balans: {user.balance}")
            
    @classmethod
    @database_sync_to_async
    def give_money(cls, user_id, amount):
        from users.models import User
        user = User.objects.get(id=user_id)
        print(amount)
        user.balance += amount
        user.save()
        print(f"Novi balans: {user.balance}")

    @classmethod
    def calculate_outcome(server_seed, client_seed, nonce):
        hash_input = f"{server_seed}-{client_seed}-{nonce}".encode()
        hashed = hashlib.sha256(hash_input).hexdigest()
        number = int(hashed[:8], 16)
        return number % 37

    @classmethod
    async def start_game(cls):
        try:
            cls.game_running = False
            global waiting_queue

            if not (is_connected := cache.get("websocket_connected")) or cls.game_running:
                return
            
            print("Creating game in DB")

            from asgiref.sync import sync_to_async
            from .models import RouletteGame
            server_seed = secrets.token_hex(16)
            client_seed = "default_client_seed"
            hashed_input = f"{cls.server_seed}-{cls.client_seed}-{cls.nonce}".encode()
            hashed_server_seed = hashlib.sha256(hashed_input).hexdigest()
            nonce = rnd.uniform(0,1)
            number = cls.calculate_outcome(server_seed,client_seed,nonce)

            new_game = await sync_to_async(RouletteGame.objects.create)(
                server_seed=server_seed,
                client_seed=client_seed,
                hashed_server_seed=hashed_server_seed,
                nonce=nonce,
                game_running=True,
                game_result=outcome
            )
            print(new_game)
            cls.current_game = new_game
            
            for player in waiting_queue:
                print(f"Added user from queue {player}")
                await cls.add_user_to_game(user_id=player["user_id"], bet_amount=player["bet_amount"])
            
            waiting_queue = []
            asyncio.sleep(1)
            print(f"Game starting... {cls.current_game.id}")

            new_game.game_running = True

            new_game.server_seed = server_seed
            new_game.client_seed = client_seed
            new_game.hashed_server_seed = hashed_server_seed
            new_game.nonce = nonce
            new_game.number = number

            await cls.save_game(new_game)

            await cls.send_to_group({"hash_server_seed" : cls.hash_server_seed, "status" : "game_start"})
            asyncio.sleep(5)
            if outcome == 0:
                print("Green")
                outcome = "Green"
                multiplier = 14
            elif outcome == 36 or outcome == 1:
                print("Bait")
                outcome = "Bait"
                multiplier = 7
            elif outcome % 2 == 1:
                print("Red")
                outcome = "Red"
                multiplier = 2
            elif outcome % 2 == 0:
                print("Black")
                outcome = "Black"
                multiplier = 2

            await cls.send_to_group({"status" : "game_end", "outcome" : outcome})
            
            for player in cls.active_users:
                  if cls.active_users[player]["type"] == outcome:
                      await cls.give_money(player, cls.active_users[player]["bet_amount"] * multiplier)
            cls.game_running = False
            for x in range(10):
                await asyncio.sleep(1)
                await cls.send_to_group({"status" : "game_end", "message" : f"Game will start in {10 - x} seconds."})
            
            print("Game ended, updating DB")
            new_game.game_running = False
            await cls.save_game(new_game)

        except Exception as e:
            print(f"Error: {e}")
            return
        
    @classmethod
    async def send_to_group(cls, message):
        cls.channel_layer = get_channel_layer()
        await cls.channel_layer.group_send(
            "crash_game",
            {"type": "send_message", "message": json.dumps(message)}
        )

    @classmethod
    async def save_game(cls, game = None):
        if game is None:
            game = cls.current_game
        from asgiref.sync import sync_to_async
        await sync_to_async(cls.current_game.save)()

    async def send_message(self, event):
        await self.send(event["message"])