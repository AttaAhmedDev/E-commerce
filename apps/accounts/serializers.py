from django.contrib.auth import authenticate
from rest_framework import serializers
from rest_framework_simplejwt.tokens import RefreshToken

from .models import User


class RegisterSerializer(serializers.ModelSerializer):
    """
    Handles new user signup. Password is write-only and validated
    against Django's configured password validators (length, common
    passwords, etc. — set in AUTH_PASSWORD_VALIDATORS).
    """

    password = serializers.CharField(write_only=True, min_length=8)
    password_confirm = serializers.CharField(write_only=True, min_length=8)

    class Meta:
        model = User
        fields = [
            "email",
            "first_name",
            "last_name",
            "phone_number",
            "password",
            "password_confirm",
        ]

    def validate_email(self, value: str) -> str:
        value = value.lower().strip()
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return value

    def validate(self, attrs: dict) -> dict:
        if attrs["password"] != attrs["password_confirm"]:
            raise serializers.ValidationError(
                {"password_confirm": "Passwords do not match."}
            )
        return attrs

    def create(self, validated_data: dict) -> User:
        validated_data.pop("password_confirm")
        password = validated_data.pop("password")
        user = User.objects.create_user(password=password, **validated_data)
        return user


class LoginSerializer(serializers.Serializer):
    """
    Validates credentials and returns the authenticated user.
    Deliberately does NOT reveal whether the email or password was
    wrong — same generic error for both, to avoid leaking which
    emails are registered (user enumeration protection).
    """

    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, attrs: dict) -> dict:
        email = attrs.get("email", "").lower().strip()
        password = attrs.get("password")

        user = authenticate(
            request=self.context.get("request"),
            username=email,  # Django's authenticate() always uses 'username' kwarg internally,
            password=password,  # even though our USERNAME_FIELD is 'email'
        )

        if user is None:
            raise serializers.ValidationError("Invalid email or password.")
        if not user.is_active:
            raise serializers.ValidationError("This account has been deactivated.")

        attrs["user"] = user
        return attrs


class UserSerializer(serializers.ModelSerializer):
    """Read-only representation returned after auth actions."""

    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "first_name",
            "last_name",
            "phone_number",
            "role",
            "date_joined",
        ]
        read_only_fields = fields


class LogoutSerializer(serializers.Serializer):
    refresh = serializers.CharField()

    def validate_refresh(self, value: str) -> str:
        try:
            RefreshToken(value)
        except Exception:
            raise serializers.ValidationError("Invalid or expired refresh token.")
        return value


class ProfileSerializer(serializers.ModelSerializer):
    """
    Used for both viewing and updating the authenticated user's own
    profile. Email is intentionally excluded from editable fields —
    changing login identifiers needs its own verified flow, not a
    casual PATCH here.
    """

    full_name = serializers.CharField(read_only=True)

    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "first_name",
            "last_name",
            "phone_number",
            "full_name",
            "role",
            "date_joined",
        ]
        read_only_fields = ["id", "email", "role", "date_joined"]


class ChangePasswordSerializer(serializers.Serializer):
    """
    Requires the current password to prevent a scenario where someone
    with a hijacked, still-logged-in session (e.g. an unlocked device)
    can silently lock the real owner out by changing the password
    without knowing it.
    """

    current_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True, min_length=8)
    new_password_confirm = serializers.CharField(write_only=True, min_length=8)

    def validate_current_password(self, value: str) -> str:
        user = self.context["request"].user
        if not user.check_password(value):
            raise serializers.ValidationError("Current password is incorrect.")
        return value

    def validate(self, attrs: dict) -> dict:
        if attrs["new_password"] != attrs["new_password_confirm"]:
            raise serializers.ValidationError(
                {"new_password_confirm": "Passwords do not match."}
            )
        return attrs

    def save(self, **kwargs) -> User:
        user = self.context["request"].user
        user.set_password(self.validated_data["new_password"])
        user.save(update_fields=["password"])
        return user
