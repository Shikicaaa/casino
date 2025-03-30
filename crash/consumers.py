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

waiting_queue = []

class CrashGameConsumer(AsyncWebsocketConsumer):
    server_seed = None
    client_seed = "default_client_seed"
    nonce = 0
    hash_server_seed = None
    crash_point = None
    time_step = 0.05  # Interval u sekundama (50ms)
    max_time = 100  # Maksimalno trajanje igre u sekundama
    channel_layer = None
    multiplier = 1.0
    game_running = False
    connected = False
    user = None
    current_game = None
    active_users = {}
    r = 0.075 # Rast faktor

    """
    Connection, receive and disconnect methods
    """

    async def connect(self):
        await self.accept()
        print("WebSocket connection with crash established.")

        if self.active_users is None:
            self.active_users = {}
        self.user = await self.get_user_from_token(self.scope["query_string"])
        print(f"Connected user: {self.user}")  # Debug

        if not self.user:
            await self.send(json.dumps({"error": "Authentication failed"}))
            await self.close()
            print("WebSocket closed due to authentication failure.")  # Debug
            return

        await self.channel_layer.group_add("crash_game", self.channel_name)
        print("User added to crash_game group.")  # Debug

        await self.send(json.dumps({"status": "connected"}))
        print("WebSocket connected message sent.")  # Debug
        cache.set("websocket_connected", True)
        asyncio.create_task(self.keep_alive())  # Debug

        if self.game_running:
            await self.send(json.dumps({"hashed_server_seed": self.hash_server_seed, "status": "game_start"}))
            print("Game start message sent.")  # Debug

    async def disconnect(self, close_code):
        cache.set("websocket_connected", False)
        await self.channel_layer.group_discard("crash_game", self.channel_name)
        print(f"WebSocket disconnected (code {close_code})")

    async def receive(self, text_data):
        if self.user.is_authenticated:
            text_data_json = json.loads(text_data)
            text_data_json["user_id"] = self.user.id
            text_data_json["balance"] = self.user.balance
            action = text_data_json.get("action")

            if action == "join":
                auto_cashout_at = text_data_json.get("auto_cashout", None)
                user_id = text_data_json.get("user_id")
                bet_amount = text_data_json.get("bet_amount")
                user = await self.get_user(user_id)
                if auto_cashout_at is not None:
                    if auto_cashout_at == 0:
                        print("Manual Cashout")
                    elif auto_cashout_at <= 1.0:
                        await self.send(json.dumps({
                            "status" : "error",
                            "message" : "Auto cashout must be greater than 1.0!"
                        }))
                        return
                else:
                    auto_cashout_at = 0
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
                game_user = await self.add_user_to_game(user_id = user_id, auto_cashout= auto_cashout_at, bet_amount=bet_amount)
                if game_user is None:
                    await self.send(json.dumps({
                        "status" : "in_queue",
                        "message" : "Game is running. You are in queue."
                    }))
                    return
                
                await self.send(json.dumps({
                    "status" : "joined",
                    "message" : f"User {user_id} joined the game with {bet_amount} bet. Cashing out at {auto_cashout_at if auto_cashout_at != 0 else 'Not set'}"
                }))
            elif action == "cashout":
                print("Cashout action received")
                await self.cashout(text_data_json)
        else:
            await self.send(text_data=json.dumps({
                "message": "You are not authenticated."
            }))

    async def keep_alive(self):
        while True:
            try:
                if not cache.get("websocket_connected", False):
                    print("WebSocket not connected, stopping keep alive.")
                    break
                cache.set("websocket_connected", True, timeout=40)
                await asyncio.sleep(20)

            except Exception as e:
                print(f"Ping error: {e}")
                break

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

    @database_sync_to_async
    def get_game(self, game_id = None):
        from .models import CrashGame
        return CrashGame.objects.get(id=game_id) if game_id else CrashGame.objects.order_by("-id").first()

    @database_sync_to_async
    def get_user(self, user_id):
        from users.models import User
        return User.objects.get(id=user_id)

    @classmethod
    @database_sync_to_async
    def pay_players(cls, user_id, amount):
        from users.models import User
        user = User.objects.get(id=user_id)
        print(amount)
        user.balance += amount
        user.save()
        print(f"Novi balans: {user.balance}")

    @classmethod
    @database_sync_to_async
    def take_money(cls, user_id):
        from users.models import User
        user = User.objects.get(id=user_id)
        bet_amount = cls.active_users.get(user_id, {}).get("bet_amount", 0)

        if bet_amount > 0:
            user.balance -= bet_amount
            user.save()
            print(f"Oduzet novac: {bet_amount}. Novi balans: {user.balance}")


    @classmethod
    async def add_user_to_game(cls, user_id, bet_amount, auto_cashout = None, game_id=None):
        from asgiref.sync import sync_to_async
        from users.models import User
        from .models import CrashGameUser
        game = await cls.get_game(game_id)
        user = await sync_to_async(User.objects.get)(id=user_id)
        if auto_cashout is not None :
            if auto_cashout == 0:
                print("Manual Cashout")
            elif auto_cashout < 1.0:
                cls.send_to_group({"status": "error", "message": "Auto cashout must be greater than 1.0"})
                print("Auto cashout must be greater than 1.0")
                return None
            else:
                auto_cashout = round(auto_cashout, 2)
                print(f"Auto cashout rounded {auto_cashout}")
        else:
            auto_cashout = 0
        print(auto_cashout)
        if game.game_running:
            waiting_queue.append({"user_id": user_id, "bet_amount": bet_amount, "auto_cashout": auto_cashout})
            print(f"User {user_id} added to waiting queue.")
            return None

        game_user = await sync_to_async(CrashGameUser.objects.create)(
            game=cls.current_game,
            user=user,
            bet_amount=bet_amount
        )

        cls.active_users[user_id] = {
            "bet_amount": bet_amount,
            "auto_cashout": auto_cashout,
            "cashed_out" : False
        }
        print(f"User {user_id} joined the game {game.server_seed} immediately.")
        await cls.take_money(user_id)
        print(f"User now has {user.balance} balance.")
        return game_user
    
    @classmethod
    async def cashout_class(cls, user_id, auto_cashout):
        print(f"Active users: {cls.active_users}")
        if user_id in cls.active_users and not cls.active_users[user_id]["cashed_out"]:
            multiplier = round(cls.multiplier,2) if not auto_cashout else auto_cashout
            bet_amount = cls.active_users[user_id]["bet_amount"]
            print(bet_amount)
            cashout_amount = bet_amount * multiplier
            print(f"Cashed out successfuly {cashout_amount}")

            await cls.send_to_group({
                "status": "cashout",
                "message": f"User {user_id} cashed out {cashout_amount} with multiplier {multiplier}"
            })

            cls.active_users[user_id]["cashed_out"] = True

            await cls.pay_players(user_id, multiplier)

            user = await cls.get_user(user_id)
            print(f"Auto cahed out. User now has {user.balance} balance.")

    async def cashout(self, data):
        print(f"Active users: {self.active_users}")
        text_data = data
        user_id = int(text_data.get("user_id"))
        try:
            if self.active_users[user_id]['auto_cashout'] != 0:
                await self.send(json.dumps({
                    "status": "error",
                    "message": "Auto cashout is already set."
                }))
                return
            if user_id in self.active_users and not self.active_users[user_id]["cashed_out"]:
                multiplier = round(self.multiplier,2)
                bet_amount = self.active_users[user_id]["bet_amount"]
                print(bet_amount)
                cashout_amount = bet_amount * multiplier
                print(f"Cashed out successfuly {cashout_amount}")

                await self.send(json.dumps({
                    "status": "cashout",
                    "message": f"User {user_id} cashed out {cashout_amount} with multiplier {multiplier}"
                }))

                await self.pay_players(user_id, cashout_amount)
                self.active_users[user_id]["cashed_out"] = True

                user = await self.get_user(user_id)
                print(f"User now has {user.balance} balance.")

            else:
                print("Cashed out failed")
                await self.send(json.dumps({
                    "status": "error",
                    "message": "Cannot cashout, not in game or already cashed out."
                }))
        except KeyError:
            print("KeyError ID nije u active_users")
            print(type(user_id))
        except Exception as e:
            print(e)

    @classmethod
    async def start_new_game(cls):
        try:
            cls.multiplier = 1.0
            cls.game_running = False
            global waiting_queue

            if not (is_connected := cache.get("websocket_connected", False)) or cls.game_running:
                return

            print("Creating game in DB")

            from asgiref.sync import sync_to_async
            from .models import CrashGame
            server_seed = secrets.token_hex(16)
            client_seed = "default_client_seed"
            hashed_input = f"{cls.server_seed}-{cls.client_seed}-{cls.nonce}".encode()
            hashed_server_seed = hashlib.sha256(hashed_input).hexdigest()
            crash_point = cls.calculate_crash_point(server_seed, client_seed, cls.nonce)
            nonce = rnd.uniform(0,1)

            new_game = await sync_to_async(CrashGame.objects.create)(
                server_seed=server_seed,
                client_seed=client_seed,
                hashed_server_seed=hashed_server_seed,
                nonce=nonce,
                crash_point=crash_point,
                game_running=False
            )
            print(new_game)
            cls.current_game = new_game

            for player in waiting_queue:
                print(f"Added user from queue {player}")
                await cls.add_user_to_game(user_id=player["user_id"], bet_amount=player["bet_amount"], auto_cashout=player.get("auto_cashout", None))
                
            waiting_queue = []
            asyncio.sleep(2)
            print(f"Game starting... {cls.current_game.id}")
            
            new_game.game_running = True

            new_game.server_seed = server_seed
            new_game.hash_server_seed = hashed_server_seed
            new_game.client_seed = client_seed
            new_game.crash_point = crash_point
            new_game.nonce = nonce

            await cls.save_game(new_game)

            print(new_game)

            await cls.send_to_group({"hash_server_seed": cls.hash_server_seed, "status": "game_start"})

            elapsed_time = 0
            while elapsed_time < cls.max_time:
                cls.multiplier = (1+cls.r)**elapsed_time


                await cls.send_to_group({"multiplier": round(cls.multiplier, 2), "status": "running"})
                for x in cls.active_users:
                    if(cls.active_users[x]["auto_cashout"] and not cls.active_users[x]["cashed_out"]):
                        if cls.multiplier >= cls.active_users[x]["auto_cashout"]:
                            print(f"Auto cashed out {x}")
                            await cls.cashout_class(x, cls.active_users[x]["auto_cashout"])

                if cls.multiplier >= new_game.crash_point:
                    cls.active_users = {}
                    break
              
                await asyncio.sleep(cls.time_step)
                elapsed_time += cls.time_step

            print("Game ended. Updating database...")
            new_game.game_running = False
            await cls.save_game(new_game)
            print(new_game)
            await cls.send_to_group({
                "crash_point": round(new_game.crash_point,2),
                "server_seed": new_game.server_seed,
                "nonce" : new_game.nonce,
                "status": "game_end",
                })
        except Exception as e:
            print(e)
        finally:
            new_game.game_running = False
            cls.game_running = False
            await cls.save_game(new_game)
            cls.active_users = {}
            for x in range(10):
                cls.send_to_group(
                    {
                        "status": "game_ended",
                        "message": f"Game Starting in {10-x} seconds."
                    }
                )
                await asyncio.sleep(1)

    @staticmethod
    def calculate_crash_point(server_seed, client_seed, nonce):
        hash_input = f"{server_seed}-{client_seed}-{nonce}".encode()
        hashed = hashlib.sha256(hash_input).hexdigest()
        number = int(hashed[:8], 16)
        return max(1.0,(10000.0 / (number % 10000 + 1)))

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

    @classmethod
    async def update_db(cls):
        from asgiref.sync import sync_to_async
        from .models import CrashGame
        game = await sync_to_async(CrashGame.objects.order_by("-id").first)()
        if game:
            game.game_running = False
            await sync_to_async(game.save)()

    @classmethod
    async def save_to_db(cls):
        from asgiref.sync import sync_to_async
        from .models import CrashGame
        await sync_to_async(CrashGame.objects.create)(
            server_seed=cls.server_seed,
            client_seed=cls.client_seed,
            hashed_server_seed=cls.hash_server_seed,
            nonce=cls.nonce,
            crash_point=cls.crash_point,
            game_running=cls.game_running
        )

    async def send_message(self, event):
        await self.send(event["message"])
