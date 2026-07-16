import pytest
from rest_framework.test import APIClient
from rest_framework import status

from apps.accounts.tests.factories import UserFactory
from .factories import CategoryFactory

pytestmark = pytest.mark.django_db


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def admin_client():
    admin = UserFactory(
        email="admin@example.com", password="AdminPass123", role="admin"
    )
    client = APIClient()
    client.force_authenticate(user=admin)
    return client


@pytest.fixture
def customer_client():
    customer = UserFactory(
        email="customer@example.com", password="CustPass123", role="customer"
    )
    client = APIClient()
    client.force_authenticate(user=customer)
    return client


class TestCategoryRead:
    url = "/api/v1/categories/"

    def test_anonymous_can_list_categories(self, api_client):
        CategoryFactory.create_batch(3)
        response = api_client.get(self.url)

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["results"]) == 3

    def test_list_only_returns_top_level_categories(self, api_client):
        parent = CategoryFactory(name="Electronics")
        CategoryFactory(name="Laptops", parent=parent)

        response = api_client.get(self.url)

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["results"]) == 1
        assert response.data["results"][0]["name"] == "Electronics"

    def test_subcategory_appears_in_parent_children(self, api_client):
        parent = CategoryFactory(name="Electronics")
        CategoryFactory(name="Laptops", parent=parent)

        response = api_client.get(self.url)

        assert response.data["results"][0]["children"][0]["name"] == "Laptops"


class TestCategoryWrite:
    url = "/api/v1/categories/"

    def test_anonymous_cannot_create_category(self, api_client):
        response = api_client.post(self.url, {"name": "New Category"})
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_customer_cannot_create_category(self, customer_client):
        response = customer_client.post(self.url, {"name": "New Category"})
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_admin_can_create_category(self, admin_client):
        response = admin_client.post(self.url, {"name": "New Category"})

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["slug"] == "new-category"

    def test_category_cannot_be_its_own_parent(self, admin_client):
        category = CategoryFactory(name="Electronics")
        response = admin_client.patch(
            f"{self.url}{category.slug}/",
            {"parent": category.id},
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_duplicate_name_under_same_parent_rejected(self, admin_client):
        parent = CategoryFactory(name="Electronics")
        CategoryFactory(name="Laptops", parent=parent)

        response = admin_client.post(
            self.url,
            {
                "name": "Laptops",
                "parent": parent.id,
            },
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
