from rest_framework import status, generics
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import TokenError

from .serializers import (
    RegisterSerializer,
    LoginSerializer,
    UserSerializer,
    LogoutSerializer,
    ChangePasswordSerializer,
    ProfileSerializer,
)


def _tokens_for_user(user) -> dict:
    """Generates a fresh access/refresh token pair for a given user."""
    refresh = RefreshToken.for_user(user)
    return {
        "access": str(refresh.access_token),
        "refresh": str(refresh),
    }


class RegisterView(generics.CreateAPIView):
    """
    POST /api/v1/auth/register/
    Creates a new user account and returns it along with a token pair,
    so the frontend can log the user in immediately without a second request.
    """

    serializer_class = RegisterSerializer
    permission_classes = [AllowAny]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        return Response(
            {
                "user": UserSerializer(user).data,
                "tokens": _tokens_for_user(user),
            },
            status=status.HTTP_201_CREATED,
        )


class LoginView(APIView):
    """
    POST /api/v1/auth/login/
    Authenticates credentials and returns a fresh token pair.
    """

    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]

        return Response(
            {
                "user": UserSerializer(user).data,
                "tokens": _tokens_for_user(user),
            },
            status=status.HTTP_200_OK,
        )


class LogoutView(APIView):
    """
    POST /api/v1/auth/logout/
    Blacklists the provided refresh token so it can no longer be used
    to obtain new access tokens. Requires authentication so anonymous
    users can't blacklist arbitrary tokens.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = LogoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            token = RefreshToken(serializer.validated_data["refresh"])
            token.blacklist()
        except TokenError:
            return Response(
                {"detail": "Token is invalid or already blacklisted."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(status=status.HTTP_205_RESET_CONTENT)


class ProfileView(generics.RetrieveUpdateAPIView):
    """
    GET  /api/v1/auth/profile/  -> view own profile
    PATCH /api/v1/auth/profile/ -> partially update own profile
    Always operates on request.user — there's no user ID in the URL,
    so there's no way to accidentally (or maliciously) view/edit
    someone else's profile through this endpoint.
    """

    serializer_class = ProfileSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return self.request.user


class ChangePasswordView(APIView):
    """
    POST /api/v1/auth/change-password/
    On success, blacklists all outstanding refresh tokens for this
    user so other sessions (e.g. a stolen device) are forced to log
    in again with the new password.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = ChangePasswordSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()

        self._blacklist_all_tokens_for(request.user)

        return Response(
            {"detail": "Password changed successfully. Please log in again."},
            status=status.HTTP_200_OK,
        )

    @staticmethod
    def _blacklist_all_tokens_for(user) -> None:
        from rest_framework_simplejwt.token_blacklist.models import (
            OutstandingToken,
            BlacklistedToken,
        )

        tokens = OutstandingToken.objects.filter(user=user)
        for token in tokens:
            BlacklistedToken.objects.get_or_create(token=token)
