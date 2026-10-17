from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.orders.models import Order

from .gateways.base import InvalidWebhook
from .services import (
    PaymentAlreadyPending,
    PaymentGatewayError,
    PaymentNotAllowed,
    UnknownPayment,
    UnknownProvider,
    handle_webhook,
    initiate_payment,
)


class PayView(APIView):
    """POST /api/v1/orders/<id>/pay/. Starts an online payment for the caller's own order."""

    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        order = Order.objects.filter(pk=pk, user=request.user).first()
        if order is None:
            return Response(
                {"detail": "Order not found."}, status=status.HTTP_404_NOT_FOUND
            )

        try:
            payment, initiation = initiate_payment(order)
        except PaymentNotAllowed as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except PaymentAlreadyPending as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)
        except PaymentGatewayError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_502_BAD_GATEWAY)

        return Response(
            {
                "payment_id": payment.id,
                "amount": str(payment.amount),
                "reference": initiation.reference,
                "payment_url": initiation.payment_url,
            },
            status=status.HTTP_201_CREATED,
        )


class WebhookView(APIView):
    """
    POST /api/v1/payments/webhook/<provider>/
    Called by the gateway, not by a logged-in user, so there is no JWT
    auth. The signature check inside the gateway is the authentication.
    We read the RAW body (never request.data) because the signature is
    computed over the exact bytes the gateway sent.
    """

    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request, provider):
        try:
            handle_webhook(provider, request.headers, request.body)
        except (UnknownProvider, UnknownPayment):
            return Response(status=status.HTTP_404_NOT_FOUND)
        except InvalidWebhook:
            return Response(
                {"detail": "Invalid webhook."}, status=status.HTTP_400_BAD_REQUEST
            )
        return Response(status=status.HTTP_200_OK)
