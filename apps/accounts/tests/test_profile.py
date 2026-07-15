# apps/accounts/tests/test_profile.py
import pytest
from rest_framework.test import APIClient
from rest_framework import status

from .factories import UserFactory

pytestmark = pytest.mark.django_db


@pytest.fixture
def authenticated_client():
    user = UserFactory(email="profile@example.com", password="OldPass123")
    client = APIClient()
    client.force_authenticate(user=user)
    return client, user


class TestProfile:
    url = "/api/v1/auth/profile/"

    def test_get_profile_returns_own_data(self, authenticated_client):
        client, user = authenticated_client
        response = client.get(self.url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["email"] == user.email

    def test_update_profile_success(self, authenticated_client):
        client, user = authenticated_client
        response = client.patch(self.url, {"first_name": "Updated"})

        assert response.status_code == status.HTTP_200_OK
        user.refresh_from_db()
        assert user.first_name == "Updated"

    def test_cannot_update_role_via_profile(self, authenticated_client):
        client, user = authenticated_client
        client.patch(self.url, {"role": "admin"})

        user.refresh_from_db()
        assert user.role == "customer"

    def test_cannot_update_email_via_profile(self, authenticated_client):
        client, user = authenticated_client
        original_email = user.email
        client.patch(self.url, {"email": "hacked@example.com"})

        user.refresh_from_db()
        assert user.email == original_email

    def test_profile_requires_authentication(self):
        client = APIClient()
        response = client.get(self.url)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


class TestChangePassword:
    url = "/api/v1/auth/change-password/"

    def test_change_password_success(self, authenticated_client):
        client, user = authenticated_client
        response = client.post(
            self.url,
            {
                "current_password": "OldPass123",
                "new_password": "NewPass456",
                "new_password_confirm": "NewPass456",
            },
        )

        assert response.status_code == status.HTTP_200_OK
        user.refresh_from_db()
        assert user.check_password("NewPass456")

    def test_change_password_wrong_current_rejected(self, authenticated_client):
        client, user = authenticated_client
        response = client.post(
            self.url,
            {
                "current_password": "WrongOldPass",
                "new_password": "NewPass456",
                "new_password_confirm": "NewPass456",
            },
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_change_password_mismatch_rejected(self, authenticated_client):
        client, user = authenticated_client
        response = client.post(
            self.url,
            {
                "current_password": "OldPass123",
                "new_password": "NewPass456",
                "new_password_confirm": "Different789",
            },
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
