import logging

from django.conf import settings
from django.db import transaction

from apps.orders.models import Order, OrderStatus, PaymentMethod
from apps.orders.services import InvalidTransition, transition_order_status

from .gateways import get_gateway
from .gateways.base import InvalidWebhook, PaymentInitiation  # noqa: F401 (re-exported)
from .models import Payment, PaymentStatus

logger = logging.getLogger(__name__)


class PaymentNotAllowed(Exception):
    """The order isn't in a state where a payment can be started."""


class PaymentAlreadyPending(Exception):
    """A payment for this order is already in progress."""


class PaymentGatewayError(Exception):
    """The gateway failed to start the payment."""


class UnknownProvider(Exception):
    pass


class UnknownPayment(Exception):
    pass


def initiate_payment(order: Order) -> tuple[Payment, PaymentInitiation]:
    gateway = get_gateway()

    # Short transaction: validate under the order lock and create the
    # pending row. The gateway call happens OUTSIDE it, so a slow
    # network call never holds a database lock.
    with transaction.atomic():
        order = Order.objects.select_for_update().get(pk=order.pk)
        if (
            order.payment_method != PaymentMethod.ONLINE
            or order.status != OrderStatus.PENDING_PAYMENT
        ):
            raise PaymentNotAllowed("This order is not awaiting an online payment.")
        if order.payments.filter(status=PaymentStatus.PENDING).exists():
            raise PaymentAlreadyPending(
                "A payment for this order is already in progress."
            )
        # Amount always comes from the order, never from the client.
        payment = Payment.objects.create(
            order=order, provider=gateway.name, amount=order.total
        )

    try:
        initiation = gateway.initiate(payment)
    except Exception as exc:
        # Free the "one pending payment per order" slot so the customer can retry.
        payment.status = PaymentStatus.FAILED
        payment.save(update_fields=["status", "updated_at"])
        logger.exception("Gateway failed to initiate payment %s", payment.pk)
        raise PaymentGatewayError(
            "Could not start the payment. Please try again."
        ) from exc

    payment.provider_reference = initiation.reference
    payment.save(update_fields=["provider_reference", "updated_at"])
    return payment, initiation


def handle_webhook(provider: str, headers, body: bytes) -> None:
    # Only the configured gateway may receive webhooks. Without this check,
    # a registered-but-unused gateway (like "fake" in production) would
    # still be reachable by URL.
    if provider != settings.PAYMENT_GATEWAY:
        raise UnknownProvider(provider)

    gateway = get_gateway()
    event = gateway.parse_webhook(headers, body)  # raises InvalidWebhook

    with transaction.atomic():
        try:
            payment = Payment.objects.select_for_update().get(
                provider=gateway.name, provider_reference=event.reference
            )
        except Payment.DoesNotExist:
            raise UnknownPayment(event.reference)

        # Idempotency: gateways retry webhooks. Under the row lock, a
        # second delivery always sees the already-final status and stops.
        if payment.status != PaymentStatus.PENDING:
            return

        payment.status = PaymentStatus.PAID if event.succeeded else PaymentStatus.FAILED
        payment.save(update_fields=["status", "updated_at"])

        target = (
            OrderStatus.CONFIRMED if event.succeeded else OrderStatus.PAYMENT_FAILED
        )
        try:
            transition_order_status(payment.order, target)
        except InvalidTransition:
            # E.g. the customer cancelled while the payment was in flight.
            # The money moved but the order can't be confirmed, so this
            # needs a refund. Log loudly and return 200 so the gateway
            # doesn't retry forever.
            logger.error(
                "Payment %s (%s) arrived for order %s in status '%s'. Manual refund required.",
                payment.pk,
                payment.status,
                payment.order_id,
                payment.order.status,
            )
