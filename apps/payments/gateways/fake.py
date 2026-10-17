import hashlib
import json
import uuid

# for checking the signature of the webhook
import hmac

from django.conf import settings

from .base import InvalidWebhook, PaymentGateway, PaymentInitiation, WebhookEvent


class FakeGateway(PaymentGateway):
    name = "fake"

    # header name for the signature
    SIGNATURE_HEADER = "X-Fake-Signature"

    def initiate(self, payment) -> PaymentInitiation:
        reference = f"fake_{uuid.uuid4().hex}"
        return PaymentInitiation(
            reference=reference,
            payment_url=f"https://fake-gateway.invalid/pay/{reference}",
        )

    # encode for converting gateway secret to bytes
    # hashlib.sha256 is the hash function to use
    # hexdigest() is the function to convert the hash to a hexadecimal string to compare with the signature
    @staticmethod
    def sign(body: bytes) -> str:
        return hmac.new(
            settings.FAKE_GATEWAY_SECRET.encode(), body, hashlib.sha256
        ).hexdigest()

    def parse_webhook(self, headers, body: bytes) -> WebhookEvent:
        signature = headers.get(self.SIGNATURE_HEADER, "")
        if not hmac.compare_digest(signature, self.sign(body)):
            raise InvalidWebhook("Invalid signature.")

        try:
            data = json.loads(body)
            status = data["status"]
            if status not in ("succeeded", "failed"):
                raise InvalidWebhook("Malformed payload.")
            return WebhookEvent(
                reference=data["reference"],
                succeeded=status == "succeeded",
            )
        except (ValueError, KeyError, TypeError):
            raise InvalidWebhook("Malformed payload.")
