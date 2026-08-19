import pytest
from rest_framework.test import APIClient
from rest_framework import status

from apps.accounts.tests.factories import UserFactory
from apps.products.tests.factories import ProductVariantFactory
from apps.cart.models import Cart, CartItem

pytestmark = pytest.mark.django_db


@pytest.fixture
def api_client():
    return APIClient()


class TestGuestCart:
    def test_guest_can_add_item_without_auth(self, api_client):
        variant = ProductVariantFactory()
        response = api_client.post(
            "/api/v1/cart/items/",
            {
                "variant_id": variant.id,
                "quantity": 2,
            },
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["quantity"] == 2

    def test_guest_cart_persists_across_requests_in_same_session(self, api_client):
        variant = ProductVariantFactory()
        api_client.post(
            "/api/v1/cart/items/", {"variant_id": variant.id, "quantity": 1}
        )

        response = api_client.get("/api/v1/cart/")

        assert response.data["total_items"] == 1

    def test_adding_same_variant_twice_adds_quantity_not_duplicate_row(
        self, api_client
    ):
        variant = ProductVariantFactory()
        api_client.post(
            "/api/v1/cart/items/", {"variant_id": variant.id, "quantity": 1}
        )
        api_client.post(
            "/api/v1/cart/items/", {"variant_id": variant.id, "quantity": 2}
        )

        response = api_client.get("/api/v1/cart/")

        assert len(response.data["items"]) == 1
        assert response.data["items"][0]["quantity"] == 3

    def test_quantity_exceeding_stock_rejected(self, api_client):
        variant = ProductVariantFactory(inventory=5)
        response = api_client.post(
            "/api/v1/cart/items/",
            {
                "variant_id": variant.id,
                "quantity": 10,
            },
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_two_different_guest_sessions_get_separate_carts(self):
        variant = ProductVariantFactory()
        client_a = APIClient()
        client_b = APIClient()

        client_a.post("/api/v1/cart/items/", {"variant_id": variant.id, "quantity": 1})
        response_b = client_b.get("/api/v1/cart/")

        # A fresh client has no session cookie yet, so it gets its own
        # empty cart — proving carts are correctly isolated per session.
        assert response_b.data["total_items"] == 0


class TestCartItemUpdateDelete:
    def test_update_quantity(self, api_client):
        variant = ProductVariantFactory(inventory=20)
        add_response = api_client.post(
            "/api/v1/cart/items/", {"variant_id": variant.id, "quantity": 1}
        )
        item_id = add_response.data["id"]

        response = api_client.patch(f"/api/v1/cart/items/{item_id}/", {"quantity": 5})

        assert response.status_code == status.HTTP_200_OK
        assert response.data["quantity"] == 5

    def test_remove_item(self, api_client):
        variant = ProductVariantFactory()
        add_response = api_client.post(
            "/api/v1/cart/items/", {"variant_id": variant.id, "quantity": 1}
        )
        item_id = add_response.data["id"]

        response = api_client.delete(f"/api/v1/cart/items/{item_id}/")

        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert api_client.get("/api/v1/cart/").data["total_items"] == 0

    def test_cannot_update_another_sessions_cart_item(self, api_client):
        # This is the IDOR protection test — proves scoping via
        # cart.items.filter() actually works, not just in theory.
        other_client = APIClient()
        variant = ProductVariantFactory()
        add_response = other_client.post(
            "/api/v1/cart/items/", {"variant_id": variant.id, "quantity": 1}
        )
        other_item_id = add_response.data["id"]

        response = api_client.patch(
            f"/api/v1/cart/items/{other_item_id}/", {"quantity": 99}
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestLoginMerge:
    def test_guest_cart_merges_into_user_cart_on_login(self, api_client):
        user = UserFactory(email="merge1@example.com", password="Pass123")
        variant = ProductVariantFactory()

        api_client.post(
            "/api/v1/cart/items/", {"variant_id": variant.id, "quantity": 2}
        )

        login_response = api_client.post(
            "/api/v1/auth/login/",
            {
                "email": "merge1@example.com",
                "password": "Pass123",
            },
        )
        access = login_response.data["tokens"]["access"]

        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
        cart_response = api_client.get("/api/v1/cart/")

        assert cart_response.data["total_items"] == 2
        assert cart_response.data["items"][0]["variant_detail"]["id"] == variant.id

    def test_merge_adds_quantities_when_variant_already_in_user_cart(self, api_client):
        user = UserFactory(email="merge2@example.com", password="Pass123")
        variant = ProductVariantFactory(inventory=50)

        # Pre-existing item in the user's permanent cart
        user_cart = Cart.objects.create(user=user)
        CartItem.objects.create(cart=user_cart, variant=variant, quantity=2)

        # Same variant added as a guest, in a fresh session
        api_client.post(
            "/api/v1/cart/items/", {"variant_id": variant.id, "quantity": 3}
        )

        login_response = api_client.post(
            "/api/v1/auth/login/",
            {
                "email": "merge2@example.com",
                "password": "Pass123",
            },
        )
        access = login_response.data["tokens"]["access"]

        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
        cart_response = api_client.get("/api/v1/cart/")

        assert cart_response.data["total_items"] == 5  # 2 + 3, not overwritten
        assert len(cart_response.data["items"]) == 1  # merged into ONE line, not two

    def test_session_cart_deleted_after_merge(self, api_client):
        user = UserFactory(email="merge3@example.com", password="Pass123")
        variant = ProductVariantFactory()

        api_client.post(
            "/api/v1/cart/items/", {"variant_id": variant.id, "quantity": 1}
        )
        session_key = api_client.session.session_key

        api_client.post(
            "/api/v1/auth/login/",
            {
                "email": "merge3@example.com",
                "password": "Pass123",
            },
        )

        assert not Cart.objects.filter(session_key=session_key).exists()

    def test_register_also_merges_guest_cart(self, api_client):
        variant = ProductVariantFactory()
        api_client.post(
            "/api/v1/cart/items/", {"variant_id": variant.id, "quantity": 1}
        )

        register_response = api_client.post(
            "/api/v1/auth/register/",
            {
                "email": "newmerge@example.com",
                "first_name": "New",
                "last_name": "User",
                "password": "SecurePass123",
                "password_confirm": "SecurePass123",
            },
        )
        access = register_response.data["tokens"]["access"]

        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
        cart_response = api_client.get("/api/v1/cart/")

        assert cart_response.data["total_items"] == 1
