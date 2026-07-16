import pytest
from rest_framework.test import APIClient
from rest_framework import status

from apps.accounts.tests.factories import UserFactory
from .factories import BrandFactory

pytestmark = pytest.mark.django_db


@pytest.fixture
def admin_client():
    admin = UserFactory(
        email="admin2@example.com", password="AdminPass123", role="admin"
    )
    client = APIClient()
    client.force_authenticate(user=admin)
    return client


class TestBrand:
    url = "/api/v1/brands/"

    def test_anonymous_can_list_brands(self):
        BrandFactory.create_batch(2)
        response = APIClient().get(self.url)

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["results"]) == 2

    def test_admin_can_create_brand(self, admin_client):
        response = admin_client.post(self.url, {"name": "Nike"})

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["slug"] == "nike"

    def test_duplicate_brand_name_rejected(self, admin_client):
        BrandFactory(name="Nike")
        response = admin_client.post(self.url, {"name": "Nike"})

        assert response.status_code == status.HTTP_400_BAD_REQUEST
