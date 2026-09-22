from unittest import result
import pytest

# for test the checkout view(if you have two checkout and you want test it with same data )
import threading
from decimal import Decimal
from rest_framework.test import APIClient
from rest_framework import status
from django.db import connection
from apps.accounts.tests.factories import UserFactory
from apps.accounts.models import Address
from apps.products.tests.factories import ProductVariantFactory
from apps.products.models import Inventory
from apps.cart.models import Cart, CartItem
from apps.orders.models import Order, OrderStatus, PaymentMethod

# for use django db in test
pytestmark = pytest.mark.django_db


# for create the address payload in database (helper function)
# **overrides is for override the default values
# **payload for unpacking the dictionary to keyword arguments like (user=user)
def _address_payload(user, **overrides):
    payload = dict(
        user=user,
        full_name="Ahmed Ali",
        phone_number="0100000000",
        address_line_1="123 Main St",
        city="Cairo",
        postal_code="12345",
        country="Egypt",
        address_type="shipping",
    )
    payload.update(overrides)
    return Address.objects.create(**payload)


@pytest.fixture
def checkout_setup():
    user = UserFactory(email="checkout@example.com", password="Pass123")
    variant = ProductVariantFactory(price=Decimal("50.00"), inventory=10)
    address = _address_payload(user)
    client = APIClient()
    # for authenticate the user in the test
    client.force_authenticate(user=user)
    cart = Cart.objects.create(user=user)
    CartItem.objects.create(cart=cart, variant=variant, quantity=2)
    return client, user, variant, address


class TestCheckout:
    url = "/api/v1/orders/checkout/"

    def test_checkout_cod_creates_confirmed_order(self, checkout_setup):
        client, user, variant, address = checkout_setup
        response = client.post(
            self.url,
            {
                "shipping_address_id": address.id,
                "billing_address_id": address.id,
                "payment_method": "cod",
            },
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["status"] == OrderStatus.CONFIRMED
        assert response.data["payment_method"] == PaymentMethod.COD
        assert len(response.data["items"]) == 1
        assert response.data["total"] == "100.00"  # 50 * 2

    def test_checkout_cod_decrements_quantity_directly(self, checkout_setup):
        client, user, variant, address = checkout_setup
        client.post(
            self.url,
            {
                "shipping_address_id": address.id,
                "billing_address_id": address.id,
                "payment_method": "cod",
            },
        )
        variant.inventory.refresh_from_db()
        assert variant.inventory.quantity == 8  # 10 - 2
        assert variant.inventory.reserved_quantity == 0

    def test_checkout_online_reserves_instead_of_decrementing(self, checkout_setup):
        client, user, variant, address = checkout_setup
        response = client.post(
            self.url,
            {
                "shipping_address_id": address.id,
                "billing_address_id": address.id,
                "payment_method": "online",
            },
        )
        assert response.data["status"] == OrderStatus.PENDING_PAYMENT
        variant.inventory.refresh_from_db()
        assert variant.inventory.quantity == 10  # untouched
        assert variant.inventory.reserved_quantity == 2

    def test_checkout_clears_cart(self, checkout_setup):
        client, user, variant, address = checkout_setup
        client.post(
            self.url,
            {
                "shipping_address_id": address.id,
                "billing_address_id": address.id,
                "payment_method": "cod",
            },
        )
        cart = Cart.objects.get(user=user)
        assert cart.items.count() == 0

    def test_checkout_snapshots_order_item_data(self, checkout_setup):
        client, user, variant, address = checkout_setup
        response = client.post(
            self.url,
            {
                "shipping_address_id": address.id,
                "billing_address_id": address.id,
                "payment_method": "cod",
            },
        )
        item = response.data["items"][0]
        assert item["variant_sku"] == variant.sku
        assert item["product_name"] == variant.product.name
        assert item["price"] == "50.00"
        assert item["quantity"] == 2

    def test_checkout_snapshots_address_data(self, checkout_setup):
        client, user, variant, address = checkout_setup
        response = client.post(
            self.url,
            {
                "shipping_address_id": address.id,
                "billing_address_id": address.id,
                "payment_method": "cod",
            },
        )

        assert response.data["shipping_full_name"] == address.full_name
        assert response.data["shipping_phone_number"] == address.phone_number

    def test_checkout_empty_cart_rejected(self):
        user = UserFactory(email="emptycart@example.com", password="Pass123")
        address = _address_payload(user)
        client = APIClient()
        client.force_authenticate(user=user)
        response = client.post(
            self.url,
            {
                "shipping_address_id": address.id,
                "billing_address_id": address.id,
                "payment_method": "cod",
            },
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_checkout_rejects_quantity_exceeding_stock(self, checkout_setup):
        client, user, variant, address = checkout_setup
        # for set the quantity of the variant to 1 instead of 10
        variant.inventory.quantity = 1
        variant.inventory.save()
        response = client.post(
            self.url,
            {
                "shipping_address_id": address.id,
                "billing_address_id": address.id,
                "payment_method": "cod",
            },
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_cannot_use_another_users_address(self, checkout_setup):
        client, user, variant, address = checkout_setup
        other_user = UserFactory(email="otheraddr@example.com", password="Pass123")
        # pass the other user address to the address payload
        other_address = _address_payload(other_user)
        response = client.post(
            self.url,
            {
                "shipping_address_id": other_address.id,
                "billing_address_id": address.id,
                "payment_method": "cod",
            },
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    # we use checkout_setup without () as we donot need to call it ,just make variables mention to it
    def test_anonymous_cannot_checkout(self, checkout_setup):
        _, _, variant, address = checkout_setup
        response = APIClient().post(
            self.url,
            {
                "shipping_address_id": address.id,
                "billing_address_id": address.id,
                "payment_method": "cod",
            },
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


class TestOrderHistory:
    def test_user_sees_only_own_orders(self, checkout_setup):
        client, user, variant, address = checkout_setup
        other_user = UserFactory(email="otherorder@example.com", password="Pass123")
        Order.objects.create(
            user=other_user,
            payment_method="cod",
            subtotal=10,
            total=10,
            shipping_full_name="X",
            shipping_phone_number="X",
            shipping_address_line_1="X",
            shipping_city="X",
            shipping_postal_code="X",
            shipping_country="X",
            billing_full_name="X",
            billing_phone_number="X",
            billing_address_line_1="X",
            billing_city="X",
            billing_postal_code="X",
            billing_country="X",
        )

        client.post(
            "/api/v1/orders/checkout/",
            {
                "shipping_address_id": address.id,
                "billing_address_id": address.id,
                "payment_method": "cod",
            },
        )

        response = client.get("/api/v1/orders/")
        assert len(response.data["results"]) == 1

        def test_cannot_view_another_users_order_detail(self, checkout_setup):
            client, user, variant, address = checkout_setup
            other_user = UserFactory(
                email="otherorder2@example.com", password="Pass123"
            )
            other_order = Order.objects.create(
                user=other_user,
                payment_method="cod",
                subtotal=10,
                total=10,
                shipping_full_name="X",
                shipping_phone_number="X",
                shipping_address_line_1="X",
                shipping_city="X",
                shipping_postal_code="X",
                shipping_country="X",
                billing_full_name="X",
                billing_phone_number="X",
                billing_address_line_1="X",
                billing_city="X",
                billing_postal_code="X",
                billing_country="X",
            )

            response = client.get(f"/api/v1/orders/{other_order.id}/")
            assert response.status_code == status.HTTP_404_NOT_FOUND


class TestCheckoutConcurrency:
    @pytest.mark.django_db(transaction=True)
    def test_concurrent_checkouts_cannot_oversell_last_unit(self):
        """
        The critical test: two users simultaneously checking out the
        LAST unit of a variant. Without select_for_update(), both
        requests could read quantity=1 before either commits, and
        both would succeed — overselling by one unit. With proper
        locking, exactly one should succeed and the other should be
        rejected.
        """
        user_a = UserFactory(email="race_a@example.com", password="Pass123")
        user_b = UserFactory(email="race_b@example.com", password="Pass123")
        variant = ProductVariantFactory(price=Decimal("50.00"), inventory=1)
        address_a = _address_payload(user_a)
        address_b = _address_payload(user_b)
        cart_a = Cart.objects.create(user=user_a)
        CartItem.objects.create(cart=cart_a, variant=variant, quantity=1)
        cart_b = Cart.objects.create(user=user_b)
        CartItem.objects.create(cart=cart_b, variant=variant, quantity=1)

        results = {}  # for store the results of the threads

        # for checkout the user in the thread
        def checkout(user, address, key):
            client = APIClient()
            client.force_authenticate(user=user)
            response = client.post(
                "/api/v1/orders/checkout/",
                {
                    "shipping_address_id": address.id,
                    "billing_address_id": address.id,
                    "payment_method": "cod",
                },
            )
            results[key] = response.status_code
            connection.close()

        thread_a = threading.Thread(target=checkout, args=(user_a, address_a, "a"))
        thread_b = threading.Thread(target=checkout, args=(user_b, address_b, "b"))
        thread_a.start()
        thread_b.start()
        # join for wait the threads to finish
        thread_a.join()
        thread_b.join()

        assert sorted(results.values()) == [201, 400]
        variant.refresh_from_db()
        assert variant.inventory.quantity == 0
        assert Order.objects.count() == 1
