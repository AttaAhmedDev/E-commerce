import threading
import pytest
from decimal import Decimal
from django.db import connection
from rest_framework.test import APIClient
from rest_framework import status

from apps.accounts.models import Address
from apps.accounts.tests.factories import UserFactory
from apps.cart.models import Cart, CartItem
from apps.orders.models import Order
from apps.products.models import Inventory
from apps.products.tests.factories import ProductVariantFactory

pytestmark = pytest.mark.django_db


def place_order(user, variant, payment_method, quantity=2) -> Order:
    """Creates a real order through the checkout endpoint, so these tests exercise the true flow."""
    address = Address.objects.create(
        user=user,
        full_name="Ahmed Ali",
        phone_number="0100000000",
        address_line_1="123 Main St",
        city="Cairo",
        postal_code="12345",
        country="Egypt",
        address_type="shipping",
    )
    cart, _ = Cart.objects.get_or_create(user=user)
    CartItem.objects.create(cart=cart, variant=variant, quantity=quantity)

    client = APIClient()
    client.force_authenticate(user=user)
    response = client.post(
        "/api/v1/orders/checkout/",
        {
            "shipping_address_id": address.id,
            "billing_address_id": address.id,
            "payment_method": payment_method,
        },
    )
    assert response.status_code == status.HTTP_201_CREATED
    return Order.objects.get(pk=response.data["id"])


def stock(variant):
    inv = Inventory.objects.get(variant=variant)
    return inv.quantity, inv.reserved_quantity


def client_for(user) -> APIClient:
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.fixture
def customer():
    return UserFactory(email="cust_status@example.com", password="Pass123")


@pytest.fixture
def staff():
    return UserFactory(
        email="staff_status@example.com", password="Pass123", role="staff"
    )


@pytest.fixture
def variant():
    return ProductVariantFactory(price=Decimal("50.00"), inventory=10)


class TestCustomerCancel:
    def test_cancel_cod_order_restores_stock(self, customer, variant):
        order = place_order(customer, variant, "cod", quantity=2)
        assert stock(variant) == (8, 0)

        response = client_for(customer).post(f"/api/v1/orders/{order.id}/cancel/")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["status"] == "cancelled"
        assert stock(variant) == (10, 0)

    def test_cancel_pending_online_order_only_releases_reservation(
        self, customer, variant
    ):
        order = place_order(customer, variant, "online", quantity=2)
        assert stock(variant) == (10, 2)

        response = client_for(customer).post(f"/api/v1/orders/{order.id}/cancel/")

        assert response.status_code == status.HTTP_200_OK
        # quantity was never decremented, so it must NOT be "restored" upward
        assert stock(variant) == (10, 0)

    def test_cannot_cancel_another_users_order(self, customer, variant):
        other = UserFactory(email="other_status@example.com", password="Pass123")
        order = place_order(other, variant, "cod")

        response = client_for(customer).post(f"/api/v1/orders/{order.id}/cancel/")

        assert response.status_code == status.HTTP_404_NOT_FOUND
        order.refresh_from_db()
        assert order.status == "confirmed"

    @pytest.mark.parametrize("locked_status", ["processing", "shipped", "delivered"])
    def test_customer_cannot_cancel_once_fulfillment_started(
        self, customer, variant, locked_status
    ):
        order = place_order(customer, variant, "cod")
        Order.objects.filter(pk=order.pk).update(status=locked_status)

        response = client_for(customer).post(f"/api/v1/orders/{order.id}/cancel/")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert stock(variant) == (8, 0)  # untouched

    def test_cancelling_twice_restores_stock_only_once(self, customer, variant):
        order = place_order(customer, variant, "cod", quantity=2)
        client = client_for(customer)

        first = client.post(f"/api/v1/orders/{order.id}/cancel/")
        second = client.post(f"/api/v1/orders/{order.id}/cancel/")

        assert first.status_code == status.HTTP_200_OK
        assert second.status_code == status.HTTP_400_BAD_REQUEST
        assert stock(variant) == (10, 0)  # not 12

    def test_anonymous_cannot_cancel(self, customer, variant):
        order = place_order(customer, variant, "cod")
        response = APIClient().post(f"/api/v1/orders/{order.id}/cancel/")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


class TestStaffStatusUpdate:
    def url(self, order):
        return f"/api/v1/orders/{order.id}/status/"

    def test_customer_cannot_use_status_endpoint(self, customer, variant):
        order = place_order(customer, variant, "cod")
        response = client_for(customer).post(self.url(order), {"status": "processing"})
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_payment_success_converts_reservation_to_real_decrement(
        self, customer, staff, variant
    ):
        order = place_order(customer, variant, "online", quantity=2)
        assert stock(variant) == (10, 2)

        response = client_for(staff).post(self.url(order), {"status": "confirmed"})

        assert response.status_code == status.HTTP_200_OK
        assert stock(variant) == (8, 0)

    def test_payment_failure_releases_reservation_without_losing_stock(
        self, customer, staff, variant
    ):
        order = place_order(customer, variant, "online", quantity=2)

        response = client_for(staff).post(self.url(order), {"status": "payment_failed"})

        assert response.status_code == status.HTTP_200_OK
        assert response.data["status"] == "payment_failed"
        assert stock(variant) == (10, 0)

    def test_full_fulfillment_flow_does_not_touch_inventory(
        self, customer, staff, variant
    ):
        order = place_order(customer, variant, "cod", quantity=2)
        client = client_for(staff)

        for next_status in ("processing", "shipped", "delivered"):
            response = client.post(self.url(order), {"status": next_status})
            assert response.status_code == status.HTTP_200_OK
            assert stock(variant) == (8, 0)

    def test_invalid_transition_rejected_and_inventory_untouched(
        self, customer, staff, variant
    ):
        order = place_order(customer, variant, "online", quantity=2)

        # Skipping straight to delivered would leave the reservation stuck forever
        response = client_for(staff).post(self.url(order), {"status": "delivered"})

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert stock(variant) == (10, 2)

    def test_terminal_status_cannot_transition_further(self, customer, staff, variant):
        order = place_order(customer, variant, "cod")
        Order.objects.filter(pk=order.pk).update(status="delivered")

        response = client_for(staff).post(self.url(order), {"status": "cancelled"})

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_staff_can_cancel_shipped_order_and_stock_is_restored(
        self, customer, staff, variant
    ):
        order = place_order(customer, variant, "cod", quantity=2)
        Order.objects.filter(pk=order.pk).update(status="shipped")

        response = client_for(staff).post(f"/api/v1/orders/{order.id}/cancel/")

        assert response.status_code == status.HTTP_200_OK
        assert stock(variant) == (10, 0)


class TestCancelConcurrency:
    @pytest.mark.django_db(transaction=True)
    def test_simultaneous_cancels_restore_stock_exactly_once(self):
        """
        Proves the order-row lock works: two cancel requests racing on
        the same order must produce exactly one success, and inventory
        must be restored once (10), never twice (12).
        """
        user = UserFactory(email="race_cancel@example.com", password="Pass123")
        variant = ProductVariantFactory(price=Decimal("50.00"), inventory=10)
        order = place_order(user, variant, "cod", quantity=2)
        assert stock(variant) == (8, 0)

        results = []

        def cancel():
            response = client_for(user).post(f"/api/v1/orders/{order.id}/cancel/")
            results.append(response.status_code)
            connection.close()

        threads = [threading.Thread(target=cancel) for _ in range(2)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert sorted(results) == [200, 400]
        assert stock(variant) == (10, 0)
