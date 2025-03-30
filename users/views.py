from django.contrib.auth import authenticate, get_user_model
from rest_framework import status, generics
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from .serializers import RegisterSerializer, LoginSerializer
from .utils import generate_jwt, decode_jwt
from kockarnica import settings
from django.core.cache import cache
import jwt
# Create your views here.

User = get_user_model()

def is_token_blacklisted(token):
    return cache.get(f"blacklisted_{token}") is not None

class RegisterView(generics.CreateAPIView):
    queryset = User.objects.all()
    serializer_class = RegisterSerializer

class LoginView(APIView):
    def post(self,request):
        serializer = LoginSerializer(data = request.data)
        if serializer.is_valid():
            email = serializer.validated_data["email"]
            password = serializer.validated_data["password"]
            user = authenticate(request, email=email,password=password)
            if user:
                old_token = request.headers.get("Authorization")
                if old_token and old_token.startswith("Bearer "):
                    old_token = old_token.split(" ")[1]
                    cache.delete(f"blacklisted_{old_token}")
                
                token = generate_jwt(user)
                user.is_active = True
                user.save()
                return Response({
                    "token" : token,
                },status=status.HTTP_200_OK)
            else:
                return Response({
                    "error" : "Invalid credentials"
                },status=status.HTTP_401_BAD_REQUEST)
        return Response(serializer.errors,status=status.HTTP_400_BAD_REQUEST)

class LogoutView(APIView):
    permission_classes = [IsAuthenticated]  # Samo autentifikovani korisnici mogu se odjaviti
    
    def post(self, request):
        token = request.data.get("token")
        if is_token_blacklisted(token):
            return Response({"error": "Token is blacklisted"}, status=status.HTTP_401_UNAUTHORIZED)
        if not token:
            return Response({"error": "Token is required"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
            user = User.objects.get(id=payload["id"])

            # Dodaj token na blacklist (koristimo Django cache za skladištenje blokiranih tokena)
            cache.set(f"blacklisted_{token}", True, timeout=payload["exp"] - payload["iat"])

            return Response({"message": "User logged out successfully"}, status=status.HTTP_200_OK)

        except jwt.ExpiredSignatureError:
            return Response({"error": "Token has expired"}, status=status.HTTP_400_BAD_REQUEST)

        except jwt.InvalidTokenError:
            return Response({"error": "Invalid token"}, status=status.HTTP_400_BAD_REQUEST)

        except User.DoesNotExist:
            return Response({"error": "User not found"}, status=status.HTTP_404_NOT_FOUND)

    
class VerifyTokenView(APIView):
    def post(self, request):
        token = request.data.get("token")
        payload = decode_jwt(token)
        if payload:
            return Response({
                "valid" : True,
                "user_id" : payload["id"],
                "email" : payload["email"]
            })
        return Response({
            "valid" : False
        },status=status.HTTP_401_BAD_REQUEST)