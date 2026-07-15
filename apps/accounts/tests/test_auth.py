import pytest
from rest_framework.test import APIClient
from rest_framework import status

from apps.accounts.models import User
from .factories import UserFactory

pytestmark = pytest.mark.django_db


@pytest.fixture
def api_client():
    return APIClient()


class TestRegister:
    url = "/api/v1/auth/register/"

    def test_register_success(self, api_client):
        payload = {
            "email": "newuser@example.com",
            "first_name": "Ahmed",
            "last_name": "Ali",
            "password": "SecurePass123",
            "password_confirm": "SecurePass123",
        }
        response = api_client.post(self.url, payload)

        assert response.status_code == status.HTTP_201_CREATED
        assert "tokens" in response.data
        assert "access" in response.data["tokens"]
        assert User.objects.filter(email="newuser@example.com").exists()

    def test_register_duplicate_email_rejected(self, api_client):
        UserFactory(email="taken@example.com")
        payload = {
            "email": "taken@example.com",
            "first_name": "Ahmed",
            "last_name": "Ali",
            "password": "SecurePass123",
            "password_confirm": "SecurePass123",
        }
        response = api_client.post(self.url, payload)

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_register_password_mismatch_rejected(self, api_client):
        payload = {
            "email": "mismatch@example.com",
            "first_name": "Ahmed",
            "last_name": "Ali",
            "password": "SecurePass123",
            "password_confirm": "DifferentPass123",
        }
        response = api_client.post(self.url, payload)

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_register_stores_hashed_password(self, api_client):
        payload = {
            "email": "hashcheck@example.com",
            "first_name": "Ahmed",
            "last_name": "Ali",
            "password": "SecurePass123",
            "password_confirm": "SecurePass123",
        }
        api_client.post(self.url, payload)
        user = User.objects.get(email="hashcheck@example.com")

        assert user.password != "SecurePass123"
        assert user.check_password("SecurePass123")


class TestLogin:
    url = "/api/v1/auth/login/"

    def test_login_success(self, api_client):
        UserFactory(email="login@example.com", password="SecurePass123")
        response = api_client.post(
            self.url,
            {
                "email": "login@example.com",
                "password": "SecurePass123",
            },
        )

        assert response.status_code == status.HTTP_200_OK
        assert "access" in response.data["tokens"]
        assert "refresh" in response.data["tokens"]

    def test_login_wrong_password_rejected(self, api_client):
        UserFactory(email="login2@example.com", password="SecurePass123")
        response = api_client.post(
            self.url,
            {
                "email": "login2@example.com",
                "password": "WrongPassword",
            },
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_login_nonexistent_email_rejected(self, api_client):
        response = api_client.post(
            self.url,
            {
                "email": "ghost@example.com",
                "password": "SecurePass123",
            },
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_login_inactive_user_rejected(self, api_client):
        UserFactory(
            email="inactive@example.com", password="SecurePass123", is_active=False
        )
        response = api_client.post(
            self.url,
            {
                "email": "inactive@example.com",
                "password": "SecurePass123",
            },
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST


class TestRefresh:
    def test_refresh_returns_new_access_token(self, api_client):
        UserFactory(email="refresh@example.com", password="SecurePass123")
        login_response = api_client.post(
            "/api/v1/auth/login/",
            {
                "email": "refresh@example.com",
                "password": "SecurePass123",
            },
        )
        refresh_token = login_response.data["tokens"]["refresh"]

        response = api_client.post("/api/v1/auth/refresh/", {"refresh": refresh_token})

        assert response.status_code == status.HTTP_200_OK
        assert "access" in response.data


class TestLogout:
    def test_logout_blacklists_refresh_token(self, api_client):
        UserFactory(email="logout@example.com", password="SecurePass123")
        login_response = api_client.post(
            "/api/v1/auth/login/",
            {
                "email": "logout@example.com",
                "password": "SecurePass123",
            },
        )
        access_token = login_response.data["tokens"]["access"]
        refresh_token = login_response.data["tokens"]["refresh"]

        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")
        logout_response = api_client.post(
            "/api/v1/auth/logout/", {"refresh": refresh_token}
        )

        assert logout_response.status_code == status.HTTP_205_RESET_CONTENT

        # The real proof: the blacklisted token can no longer be used
        retry_response = api_client.post(
            "/api/v1/auth/refresh/", {"refresh": refresh_token}
        )
        assert retry_response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_logout_requires_authentication(self, api_client):
        response = api_client.post("/api/v1/auth/logout/", {"refresh": "some-token"})
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
