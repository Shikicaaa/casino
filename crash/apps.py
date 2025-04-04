from django.apps import AppConfig
import asyncio
import os
import threading
import time
from django.core.cache import cache
from .consumers import CrashGameConsumer


class CrashConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "crash"

    def ready(self):
        if os.environ.get("RUN_MAIN") != "true":  # Prevent duplicate execution
            return
        thread = threading.Thread(target=self.run_async_task, daemon=True)
        thread.start()

    def run_async_task(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        print("Crash Waiting for WebSocket connection...")

        game_lock = asyncio.Lock()  # Sprečava pokretanje više igara odjednom

        async def game_loop():
            while True:
                try:
                    is_connected = cache.get("crash_websocket_connected", False)
                    print(is_connected)
                    if is_connected:
                        if not CrashGameConsumer.game_running:  # Provera da li igra već traje
                            async with game_lock:  # Sprečava istovremeno pokretanje više igara
                                print("WebSocket connected. Starting game...")
                                CrashGameConsumer.game_running = True  # Obeležimo da igra počinje
                                await CrashGameConsumer().start_new_game()  # Pokreni igru
                                CrashGameConsumer.game_running = False  # Kada završi, postavi na False
                        else:
                            print("Crash Game already running. Waiting for the next round...")
                    else:
                        print("WebSocket not connected yet. Retrying in 2 seconds...")
                    await asyncio.sleep(2)  # Sprečava prebrzu proveru
                except Exception as e:
                    print(e)
        loop.run_until_complete(game_loop())  # Pokreni asinhroni loop
