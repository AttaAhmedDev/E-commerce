import json
import threading
import pytest
from decimal import Decimal
from django.db import connection
from rest_framework import status
from rest_framework.test import APIClient

from apps.accounts.models import Address
from apps.accounts.tests.factories import UserFactory
from apps.cart.models import Cart, CartItem
from apps.orders.models import Order
from apps.payments.gateways.fake import FakeGateway
from apps.payments.models import Payment, PaymentStatus
from apps.products.models import Inventory
from apps.products.tests.factories import ProductVariantFactory

pytestmark = pytest.mark.django_db


def client_for(user) -> APIClient:
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def stock(variant):
    inv = Inventory.objects.get(variant=variant)
    return inv.quantity, inv.reserved_quantity


def place_order(user, variant, payment_method="online", quantity=2) -> Order:
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
    response = client_for(user).post(
        "/api/v1/orders/checkout/",
        {
            "shipping_address_id": address.id,
            "billing_address_id": address.id,
            "payment_method": payment_method,
        },
    )
    assert response.status_code == status.HTTP_201_CREATED
    return Order.objects.get(pk=response.data["id"])


def start_payment(user, order) -> Payment:
    response = client_for(user).post(f"/api/v1/orders/{order.id}/pay/")
    assert response.status_code == status.HTTP_201_CREATED
    return Payment.objects.get(order=order)


def send_webhook(reference, succeeded=True, signature=None, provider="fake"):
    body = json.dumps(
        {"reference": reference, "status": "succeeded" if succeeded else "failed"}
    ).encode()
    sig = signature if signature is not None else FakeGateway.sign(body)
    return APIClient().post(
        f"/api/v1/payments/webhook/{provider}/",
        data=body,
        content_type="application/json",
        HTTP_X_FAKE_SIGNATURE=sig,
    )


@pytest.fixture
def customer():
    return UserFactory(email="payer@example.com", password="Pass123")


@pytest.fixture
def variant():
    return ProductVariantFactory(price=Decimal("50.00"), inventory=10)


class TestPay:
    def test_pay_creates_pending_payment_with_order_amount(self, customer, variant):
        order = place_order(customer, variant)

        response = client_for(customer).post(f"/api/v1/orders/{order.id}/pay/")

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["payment_url"]
        payment = Payment.objects.get(order=order)
        assert payment.status == PaymentStatus.PENDING
        assert payment.amount == order.total == Decimal("100.00")
        assert payment.provider_reference == response.data["reference"]

    def test_cod_order_cannot_be_paid(self, customer, variant):
        order = place_order(customer, variant, payment_method="cod")
        response = client_for(customer).post(f"/api/v1/orders/{order.id}/pay/")
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert Payment.objects.count() == 0

    def test_cannot_pay_another_users_order(self, customer, variant):
        other = UserFactory(email="payer_other@example.com", password="Pass123")
        order = place_order(other, variant)
        response = client_for(customer).post(f"/api/v1/orders/{order.id}/pay/")
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_second_pay_while_pending_returns_409(self, customer, variant):
        order = place_order(customer, variant)
        start_payment(customer, order)

        response = client_for(customer).post(f"/api/v1/orders/{order.id}/pay/")

        assert response.status_code == status.HTTP_409_CONFLICT
        assert Payment.objects.filter(order=order).count() == 1

    def test_anonymous_cannot_pay(self, customer, variant):
        order = place_order(customer, variant)
        response = APIClient().post(f"/api/v1/orders/{order.id}/pay/")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


class TestWebhook:
    def test_success_confirms_order_and_commits_stock(self, customer, variant):
        order = place_order(customer, variant, quantity=2)
        payment = start_payment(customer, order)
        assert stock(variant) == (10, 2)

        response = send_webhook(payment.provider_reference, succeeded=True)

        assert response.status_code == status.HTTP_200_OK
        order.refresh_from_db()
        payment.refresh_from_db()
        assert order.status == "confirmed"
        assert payment.status == PaymentStatus.PAID
        assert stock(variant) == (8, 0)

    def test_failure_fails_order_releases_stock_and_restores_cart(
        self, customer, variant
    ):
        order = place_order(customer, variant, quantity=2)
        payment = start_payment(customer, order)
        assert not CartItem.objects.filter(cart__user=customer).exists()

        response = send_webhook(payment.provider_reference, succeeded=False)

        assert response.status_code == status.HTTP_200_OK
        order.refresh_from_db()
        assert order.status == "payment_failed"
        assert stock(variant) == (10, 0)
        restored = CartItem.objects.get(cart__user=customer, variant=variant)
        assert restored.quantity == 2

    def test_invalidsignature_rejected_and_nothing_changes(self, customer, variant):
        order = place_order(customer, variant)
        payment = start_payment(customer, order)

        response = send_webhook(payment.provider_reference, signature="forged")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        order.refresh_from_db()
        payment.refresh_from_db()
        assert order.status == "pending_payment"
        assert payment.status == PaymentStatus.PENDING
        assert stock(variant) == (10, 2)

    def test_duplicate_webhook_is_idempotent(self, customer, variant):
        order = place_order(customer, variant, quantity=2)
        payment = start_payment(customer, order)

        first = send_webhook(payment.provider_reference)
        second = send_webhook(payment.provider_reference)

        assert first.status_code == second.status_code == status.HTTP_200_OK
        assert stock(variant) == (8, 0)  # decremented once, not twice

    def test_unknown_reference_returns_404(self):
        assert (
            send_webhook("fake_does_not_exist").status_code == status.HTTP_404_NOT_FOUND
        )

    def test_provider_other_than_configured_returns_404(self, customer, variant):
        order = place_order(customer, variant)
        payment = start_payment(customer, order)

        response = send_webhook(payment.provider_reference, provider="stripe")

        assert response.status_code == status.HTTP_404_NOT_FOUND
        order.refresh_from_db()
        assert order.status == "pending_payment"

    def test_success_after_cancel_does_not_resurrect_order(self, customer, variant):
        order = place_order(customer, variant, quantity=2)
        payment = start_payment(customer, order)
        client_for(customer).post(f"/api/v1/orders/{order.id}/cancel/")
        assert stock(variant) == (10, 0)

        response = send_webhook(payment.provider_reference, succeeded=True)

        # Money moved but the order stays cancelled and stock is untouched.
        # The payment row records it so a refund can be issued.
        assert response.status_code == status.HTTP_200_OK
        order.refresh_from_db()
        payment.refresh_from_db()
        assert order.status == "cancelled"
        assert payment.status == PaymentStatus.PAID
        assert stock(variant) == (10, 0)


class TestWebhookConcurrency:
    @pytest.mark.django_db(transaction=True)
    def test_simultaneous_identical_webhooks_commit_stock_once(self):
        user = UserFactory(email="race_pay@example.com", password="Pass123")
        variant = ProductVariantFactory(price=Decimal("50.00"), inventory=10)
        order = place_order(user, variant, quantity=2)
        payment = start_payment(user, order)

        results = []

        def deliver():
            results.append(send_webhook(payment.provider_reference).status_code)
            connection.close()

        threads = [threading.Thread(target=deliver) for _ in range(2)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert results == [200, 200]
        assert stock(variant) == (8, 0)  # not (6, 0)
