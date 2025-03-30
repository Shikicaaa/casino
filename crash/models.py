from django.db import models
import hashlib
import secrets
from asgiref.sync import sync_to_async

# Create your models here.
class CrashGameUser(models.Model):
    game = models.ForeignKey("crash.CrashGame", on_delete=models.CASCADE, related_name="players")
    user = models.ForeignKey("users.User", on_delete=models.CASCADE)
    bet_amount = models.DecimalField(max_digits=10, decimal_places=2)
    is_out = models.BooleanField(default=False)
    cashout_multiplier = models.DecimalField(max_digits=10, decimal_places=2, default=1.0)
    entry_time = models.DateTimeField(auto_now_add=True)
    exit_time = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.user.email} in game {self.game.id}"
    
    async def join(self, amount):
        self.is_out = False
        self.bet_amount = amount
        await sync_to_async(self.update_balance)(amount=-amount)
        await sync_to_async(self.save)()
        await sync_to_async(self.user.save)()

    def update_balance(self, amount):
        self.user.balance += amount
        self.save()

    async def cashout(self, amount):
        self.is_out = True
        self.exit_time = models.DateTimeField(auto_now=True)
        await sync_to_async(self.save)() 
        await sync_to_async(self.update_balance)(amount=amount)
        await sync_to_async(self.user.save)()


class CrashGame(models.Model):
    server_seed = models.CharField(max_length=64, unique=True)
    client_seed = models.CharField(max_length=64, default="default_client_seed")
    hashed_server_seed = models.CharField(max_length=64)
    nonce = models.IntegerField(default=0)
    crash_point = models.FloatField(default=1.0)
    game_running = models.BooleanField(default=False)

    users = models.ManyToManyField("users.User", related_name="games")

    def __str__(self):
        return f"Game {self.id} - {'Running' if self.game_running else 'Finished'}" 

    @staticmethod
    def generate_seed():
        return secrets.token_hex(16)
    
    @staticmethod
    def hash_seed(seed):
        return hashlib.sha256(seed.encode()).hexdigest()
    
    def calculate_crash(self):
        """Calculate the crash point for the game"""
        hash_input = f"{self.server_seed}-{self.client_seed}-{self.nonce}".encode()
        hashed = hashlib.sha256(hash_input).hexdigest()
        number = int(hashed[:8], 16)
        return max(1.0,(10000.0 / (number % 10000 + 1)))
    
    def save(self, *args, **kwargs):
        if not self.server_seed:
            self.server_seed = self.generate_seed()
            self.hashed_server_seed = self.hash_seed(self.server_seed)
            self.crash_point = self.calculate_crash()
        super().save(*args, **kwargs)
