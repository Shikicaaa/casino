from django.db import models
import hashlib
import secrets
from asgiref.sync import sync_to_async
# Create your models here.

class RouletteGameUser(models.Model):
    game = models.ForeignKey("roulette.RouletteGame", on_delete=models.CASCADE, related_name="players")
    user = models.ForeignKey("users.User", on_delete=models.CASCADE)
    bet_amount = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.user.email} in game {self.game.id}"
    
    async def join(self, amount):
        self.bet_amount = amount
        await sync_to_async(self.update_balance)(amount=-amount)
        await sync_to_async(self.save)()
        await sync_to_async(self.user.save)()
    
    def update_balance(self,amount):
        self.user.balance += amount
        self.save()

class RouletteGame(models.Model):
    server_seed = models.CharField(max_length=64,unique=True)
    client_seed = models.CharField(max_length=64,default="default_client_seed")
    hashed_server_seed = models.CharField(max_length=64)
    nonce = models.IntegerField(default=0)
    game_running = models.BooleanField(default=False)
    number = models.IntegerField()
    outcome = models.CharField(max_length=64, default="red")

    users = models.ManyToManyField("users.User",related_name="roulette_games")

    def __str__(self):
        return f"Game {self.id} - {'Running' if self.game_running else 'Finished'}"
    
    @staticmethod
    def generate_seed():
        return secrets.token_hex(16)
    
    @staticmethod
    def hash_seed(seed):
        return hashlib.sha256(seed.encode()).hexdigest()
    
    def calculate_outcome(self):
        hash_input = f"{self.server_seed}-{self.client_seed}-{self.nonce}".encode()
        hashed = hashlib.sha256(hash_input).hexdigest()
        number = int(hashed[:8], 16)
        return number % 37
    
    def save(self, *args, **kwargs):
        if not self.server_seed:
            self.server_seed = self.generate_seed()
            self.hashed_server_seed = self.hash_seed(self.server_seed)
            self.number = self.calculate_outcome()
            if self.number % 37 == 0:
                self.outcome = "green"
            elif self.number == 1 or self.number == 36:
                self.outcome = "bait"
            elif self.number % 2 == 1:
                self.outcome = "red"
            else:
                self.outcome = "black"
        super().save(*args, **kwargs)