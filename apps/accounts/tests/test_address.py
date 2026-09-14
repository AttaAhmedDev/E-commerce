import pytest
from rest_framework.test import APIClient
from rest_framework import status
from .factories import UserFactory
from apps.accounts.models import Address

pytestmark = pytest.mark.django_db


@pytest.fixture
def authenticated_client():
    user = UserFactory(email="address_test@example.com", password="TestPass123")
    client = APIClient()
    client.force_authenticate(user=user)
    return client, user


def _address_payload(**override):
    payload = {
        "full_name": "Ahmed Ali",
        "phone_number": "01000000000",
        "address_line_1": "123 Main St",
        "city": "Cairo",
        "postal_code": "12345",
        "country": "Egypt",
        "address_type": "shipping",
        "state": "Cairo Governorate",
    }
    payload.update(override)
    return payload


class TestAddressCRUD:
    url = "/api/v1/auth/addresses/"

    def test_anonymous_cannot_access_addresses(self):
        response = APIClient().get(self.url)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_user_can_create_address(self, authenticated_client):
        client, user = authenticated_client
        response = client.post(self.url, _address_payload())

        assert response.status_code == status.HTTP_201_CREATED
        assert Address.objects.filter(user=user, city="Cairo").exists()

    def test_user_only_sees_own_addresses(self, authenticated_client):
        client, user = authenticated_client
        other_user = UserFactory(email="other@example.com", password="Pass123")
        # (**) is used to unpack the dictionary and pass the values to the function for create object in database (create fun take field = value)
        Address.objects.create(user=other_user, **_address_payload())
        Address.objects.create(user=user, **_address_payload(city="Alexandria"))

        response = client.get(self.url)

        assert len(response.data["results"]) == 1
        assert response.data["results"][0]["city"] == "Alexandria"

    def test_cannot_update_another_users_address(self, authenticated_client):
        client, user = authenticated_client
        other_user = UserFactory(email="other2@example.com", password="Pass123")
        other_address = Address.objects.create(user=other_user, **_address_payload())

        response = client.patch(f"{self.url}{other_address.id}/", {"city": "Hacked"})

        assert response.status_code == status.HTTP_404_NOT_FOUND
        other_address.refresh_from_db()
        assert other_address.city != "Hacked"

    def test_cannot_delete_another_users_address(self, authenticated_client):
        client, user = authenticated_client
        other_user = UserFactory(email="other3@example.com", password="Pass123")
        other_address = Address.objects.create(user=other_user, **_address_payload())

        response = client.delete(f"{self.url}{other_address.id}/")

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert Address.objects.filter(pk=other_address.id).exists()


class TestAddressDefault:
    url = "/api/v1/auth/addresses/"

    def test_setting_new_default_unsets_previous_default_same_type(
        self, authenticated_client
    ):
        client, user = authenticated_client

        first = client.post(self.url, _address_payload(is_default=True))
        second = client.post(self.url, _address_payload(city="Giza", is_default=True))

        assert second.data["is_default"] is True
        # use firat.data["id"] to get the id of the first address and use it to get the address from the database
        first_address = Address.objects.get(pk=first.data["id"])
        assert first_address.is_default is False

    def test_default_shipping_and_default_billing_can_coexist(
        self, authenticated_client
    ):
        client, user = authenticated_client

        shipping = client.post(
            self.url, _address_payload(address_type="shipping", is_default=True)
        )
        billing = client.post(
            self.url,
            _address_payload(address_type="billing", is_default=True, city="Giza"),
        )

        assert shipping.data["is_default"] is True
        assert billing.data["is_default"] is True
