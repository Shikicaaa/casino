from django.urls import path
from .views import NewGameView, RevealSeedView, VerifyGameView

urlpatterns = [
    path('new_game/',NewGameView.as_view(), name="new_game"),
    path('reveal_seed/',RevealSeedView.as_view(), name="reveal_seed"),
    path('verify_game/',VerifyGameView.as_view(), name="verify_game"),
]
