from django.db import transaction
from django.utils import timezone
from django.contrib.auth import authenticate
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.generics import CreateAPIView
from rest_framework.authtoken.models import Token
from rest_framework_simplejwt.views import TokenObtainPairView

import random
import string
import requests

from .serializers import (
    RegisterValidateSerializer,
    AuthValidateSerializer,
    ConfirmationSerializer,
    CustomTokenObtainPairSerializer
)
from users.models import ConfirmationCode, CustomUser



class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer



class AuthorizationAPIView(CreateAPIView):
    serializer_class = AuthValidateSerializer

    def post(self, request):
        serializer = AuthValidateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = authenticate(**serializer.validated_data)

        if user:
            if not user.is_active:
                return Response(
                    status=status.HTTP_401_UNAUTHORIZED,
                    data={'error': 'User account is not activated yet!'}
                )

            token, _ = Token.objects.get_or_create(user=user)
            user.last_login = timezone.now()
            user.save(update_fields=["last_login"])

            return Response(data={'key': token.key})

        return Response(
            status=status.HTTP_401_UNAUTHORIZED,
            data={'error': 'User credentials are wrong!'}
        )


class RegistrationAPIView(CreateAPIView):
    serializer_class = RegisterValidateSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data['email']
        password = serializer.validated_data['password']

        with transaction.atomic():
            user = CustomUser.objects.create_user(
                email=email,
                password=password,
                is_active=False,
                registration_source="local"
            )

            code = ''.join(random.choices(string.digits, k=6))

            ConfirmationCode.objects.create(
                user=user,
                code=code
            )

        return Response(
            status=status.HTTP_201_CREATED,
            data={
                'user_id': user.id,
                'confirmation_code': code
            }
        )


class ConfirmUserAPIView(CreateAPIView):
    serializer_class = ConfirmationSerializer

    def post(self, request):
        serializer = ConfirmationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user_id = serializer.validated_data['user_id']

        with transaction.atomic():
            user = CustomUser.objects.get(id=user_id)
            user.is_active = True
            user.save()

            token, _ = Token.objects.get_or_create(user=user)

            ConfirmationCode.objects.filter(user=user).delete()

        return Response(
            status=status.HTTP_200_OK,
            data={
                'message': 'User аккаунт успешно активирован',
                'key': token.key
            }
        )

class GoogleAuthAPIView(APIView):

    permission_classes = [AllowAny]

    def post(self, request):
        token = request.data.get("token")
        if not token:
            return Response({"error": "Token is required"}, status=400)

        google_response = requests.get(f"https://oauth2.googleapis.com/tokeninfo?id_token={token}")
        if google_response.status_code != 200:
            return Response({"error": "Invalid Google token"}, status=400)

        google_data = google_response.json()
        email = google_data.get("email")
        first_name = google_data.get("given_name")
        last_name = google_data.get("family_name")

        if not email:
            return Response({"error": "Email not found in Google data"}, status=400)

        user, created = CustomUser.objects.get_or_create(email=email, defaults={
            "first_name": first_name,
            "last_name": last_name,
            "is_active": True,
            "registration_source": "google",
            "last_login": timezone.now(),
        })

        if not created:
            user.first_name = first_name
            user.last_name = last_name
            user.is_active = True
            user.registration_source = "google"
            user.last_login = timezone.now()
            user.save()

        token_obj, _ = Token.objects.get_or_create(user=user)

        return Response({
            "message": "Успешный вход через Google",
            "token": token_obj.key,
            "user": {
                "email": user.email,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "registration_source": user.registration_source,
                "last_login": user.last_login,
            }
        }, status=200)
