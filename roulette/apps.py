from django.apps import AppConfig
import asyncio
import os
import threading
import time
from django.core.cache import cache
from .consumers import RouletteConsumer

class RouletteConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "roulette"

    def ready(self):
        if os.environ.get("RUN_MAIN") != "true":  # Prevent duplicate execution
            return
        thread = threading.Thread(target=self.run_async_task, daemon=True)
        thread.start()

    def run_async_task(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        print("Waiting for WebSocket connection...")

        game_lock = asyncio.Lock()

        async def game_loop():
            while True:
                try:
                    is_connected = cache.get("websocket_connected", False)
                    print(is_connected)
                    if is_connected:
                        if not RouletteConsumer.game_running:  
                            async with game_lock:  
                                print("WebSocket connected. Starting game...")
                                RouletteConsumer.game_running = True  
                                await RouletteConsumer().start_new_game()  
                                RouletteConsumer.game_running = False
                        else:
                            print("Game already running. Waiting for the next round...")
                    else:
                        print("WebSocket not connected yet. Retrying in 2 seconds...")
                    await asyncio.sleep(1)
                except Exception as e:
                    print(e)
        loop.run_until_complete(game_loop())  # Pokreni asinhroni loop
