from django.conf import settings

# for handling errors in case of invalid configuration of apps
from django.core.exceptions import ImproperlyConfigured

from .base import InvalidWebhook, PaymentGateway
from .fake import FakeGateway

_REGISTRY = {"fake": FakeGateway}


def get_gateway() -> PaymentGateway:
    name = settings.PAYMENT_GATEWAY
    try:
        return _REGISTRY[name]()
    except KeyError:
        raise ImproperlyConfigured(f"Unknown payment gateway '{name}'.")
