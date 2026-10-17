# Abstract base class for payment gateways
from abc import ABC, abstractmethod

# dataclass is a decorator that creates a class from a dataclass
from dataclasses import dataclass


class InvalidWebhook(Exception):
    """Raised when a webhook fails signature verification or is malformed."""


@dataclass(frozen=True)
class PaymentInitiation:
    reference: str
    payment_url: str


@dataclass(frozen=True)
class WebhookEvent:
    reference: str
    succeeded: bool


class PaymentGateway(ABC):
    """
    The only surface the rest of the system knows about. Stripe or
    Paymob later means one new subclass and one registry entry. Orders,
    Inventory, and the webhook view stay untouched.
    """

    @abstractmethod
    def initiate(self, payment) -> PaymentInitiation:
        """Start a payment at the gateway, return its reference and checkout URL."""

    @abstractmethod
    def parse_webhook(self, headers, body: bytes) -> WebhookEvent:
        """Verify the signature and parse the payload. Raise InvalidWebhook on any problem."""
