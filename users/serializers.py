from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from rest_framework.validators import UniqueValidator

User = get_user_model()

class RegisterSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(
        required=True,
        validators=[UniqueValidator(queryset=User.objects.all())]
    )
    password = serializers.CharField(write_only = True,required=True,validators=[validate_password])
    confirm_password = serializers.CharField(write_only = True,required=True)

    class Meta:
        model = User
        fields = ("username","email","password","confirm_password")

    def validate(self,attrs):
        if attrs["password"] != attrs["confirm_password"]:
            raise serializers.ValidationError({"password":"Password fields didn't match"})
        return attrs
    
    def create(self, validated_data):
        validated_data.pop("confirm_password")
        user = User.objects.create_user(**validated_data)
        return user

class LoginSerializer(serializers.ModelSerializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True,required=True)

    class Meta:
        model = User
        fields = ("email","password")
        
    def validate(self,data):
        email = data.get("email")
        password = data.get("password")

        if email and password:
            user = User.objects.get(email=email)
            if user:
                if not user.check_password(password):
                    raise serializers.ValidationError({"password":"Incorrect password"})
            else:
                raise serializers.ValidationError({"email":"User not found"})
        else:
            raise serializers.ValidationError({"email":"Email and password fields are required"})
        data["user"] = user
        return data