import jwt
from django.conf import settings
from datetime import timedelta, datetime
from rest_framework.exceptions import AuthenticationFailed

def generate_jwt(user):
    payload = {
        "id" : user.id,
        "email" : user.email,
        "exp" : datetime.utcnow() + settings.JWT_SETTINGS["ACCESS_TOKEN_LIFETIME"],
        "iat" : datetime.utcnow()
    }
    
    token = jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_SETTINGS["ALGORITHM"])
    return token

def decode_jwt(token):
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.JWT_SETTINGS["ALGORITHM"]])
        return payload
    except jwt.ExpiredSignatureError:
        raise AuthenticationFailed("Token expired. Please log in again.")
    except jwt.InvalidTokenError:
        raise AuthenticationFailed("Invalid token. Please log in again.")