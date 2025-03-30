from django.shortcuts import render

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .models import CrashGame
import random as rnd

class NewGameView(APIView):
    def post(self, request):
        game = CrashGame.objects.order_by("-id").first()
        if game is None or game.nonce >= 1:
            game = CrashGame.objects.create(nonce = rnd.uniform(0,1))
        return Response({"hashed_server_seed" : game.hashed_server_seed}, status=status.HTTP_201_CREATED)
    
class RevealSeedView(APIView):
    def get(self,request):
        game = CrashGame.objects.order_by("-id").first()
        if game:
            return Response({"server_seed" : game.server_seed}, status=status.HTTP_200_OK)
        return Response({"error" : "Game not found!"},status=status.HTTP_404_NOT_FOUND)

class VerifyGameView(APIView):
    def post(self,request):
        data = request.data
        server_seed = data.get("server_seed",None)
        client_seed = data.get("client_seed",None)
        nonce = data.get("nonce",0)

        hash_server_seed = CrashGame.hash_seed(server_seed)
        game = CrashGame.objects.filter(server_seed=server_seed, client_seed=client_seed,nonce = nonce).first()
        if game is None or not game:
            return Response({"error" : "Game not found!"},status=status.HTTP_404_NOT_FOUND)
        
        expected_crash = game.calculate_crash()
        return Response({"crash_point" : round(expected_crash,2)},status=status.HTTP_200_OK)