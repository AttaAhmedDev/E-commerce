import pytest
from rest_framework.test import APIClient
from rest_framework import status

from apps.accounts.tests.factories import UserFactory
from apps.products.tests.factories import ProductFactory
from apps.wishlist.models import WishlistItem

pytestmark = pytest.mark.django_db


@pytest.fixture
def authenticated_client():
    user = UserFactory(email="wishuser@example.com", password="Pass123")
    client = APIClient()
    client.force_authenticate(user=user)
    return client, user


class TestWishlistAdd:
    url = "/api/v1/wishlist/items/"

    def test_anonymous_cannot_add_to_wishlist(self):
        product = ProductFactory()
        response = APIClient().post(self.url, {"product_id": product.id})

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_authenticated_user_can_add_product(self, authenticated_client):
        client, user = authenticated_client
        product = ProductFactory()

        response = client.post(self.url, {"product_id": product.id})

        assert response.status_code == status.HTTP_201_CREATED
        assert WishlistItem.objects.filter(user=user, product=product).exists()

    def test_duplicate_product_rejected(self, authenticated_client):
        client, user = authenticated_client
        product = ProductFactory()
        WishlistItem.objects.create(user=user, product=product)

        response = client.post(self.url, {"product_id": product.id})

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_same_product_can_be_wishlisted_by_different_users(
        self, authenticated_client
    ):
        client, user = authenticated_client
        other_user = UserFactory(email="other@example.com", password="Pass123")
        product = ProductFactory()
        WishlistItem.objects.create(user=other_user, product=product)

        response = client.post(self.url, {"product_id": product.id})

        assert response.status_code == status.HTTP_201_CREATED


class TestWishlistList:
    url = "/api/v1/wishlist/"

    def test_anonymous_cannot_view_wishlist(self):
        response = APIClient().get(self.url)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_returns_only_own_wishlist_items(self, authenticated_client):
        client, user = authenticated_client
        other_user = UserFactory(email="other2@example.com", password="Pass123")

        WishlistItem.objects.create(user=user, product=ProductFactory())
        WishlistItem.objects.create(user=other_user, product=ProductFactory())

        response = client.get(self.url)

        assert len(response.data["results"]) == 1

    def test_uses_lightweight_product_serializer(self, authenticated_client):
        client, user = authenticated_client
        WishlistItem.objects.create(user=user, product=ProductFactory())

        response = client.get(self.url)

        product_data = response.data["results"][0]["product_detail"]
        # Lightweight serializer shouldn't include full variant/image data
        assert "variants" not in product_data
        assert "price_range" in product_data


class TestWishlistRemove:
    def test_can_remove_own_wishlist_item(self, authenticated_client):
        client, user = authenticated_client
        item = WishlistItem.objects.create(user=user, product=ProductFactory())

        response = client.delete(f"/api/v1/wishlist/items/{item.id}/")

        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not WishlistItem.objects.filter(pk=item.id).exists()

    def test_cannot_remove_another_users_wishlist_item(self, authenticated_client):
        client, user = authenticated_client
        other_user = UserFactory(email="other3@example.com", password="Pass123")
        other_item = WishlistItem.objects.create(
            user=other_user, product=ProductFactory()
        )

        response = client.delete(f"/api/v1/wishlist/items/{other_item.id}/")

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert WishlistItem.objects.filter(
            pk=other_item.id
        ).exists()  # still there, untouched
