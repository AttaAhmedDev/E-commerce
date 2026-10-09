from rest_framework import status, generics
from rest_framework.decorators import permission_classes
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from apps.common.permissions import (
    IsAdminOrReadOnly,
)  # reused, but we need a stricter one below

from .models import Order, OrderStatus, OrderStatus
from .serializers import (
    OrderSerializer,
    CheckoutSerializer,
    OrderStatusUpdateSerializer,
)


class IsAdminOrStaff(IsAuthenticated):
    """
    For fulfillment actions (processing/shipped/delivered) and payment
    resolution — strictly admin/staff only, no 'read-only for everyone
    else' fallback like IsAdminOrReadOnly has, since there's no public
    GET use case here at all.
    """

    def has_permission(self, request, view) -> bool:
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.role in ("admin", "staff")
        )


class CheckoutView(APIView):
    """POST /api/v1/orders/checkout/ — converts the current cart into a real Order."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = CheckoutSerializer(data=request.data, context={"request": request})
        # for check the data is valid or not that come from client or frontend
        serializer.is_valid(raise_exception=True)
        order = serializer.save()
        return Response(OrderSerializer(order).data, status=status.HTTP_201_CREATED)


class OrderListView(generics.ListAPIView):
    """
    GET /api/v1/orders/
    Order history — scoped to request.user, same IDOR-safe pattern
    used everywhere else in this project.
    """

    # for get the order list from the database
    serializer_class = OrderSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Order.objects.filter(user=self.request.user).prefetch_related("items")


class OrderDetailView(generics.RetrieveAPIView):
    """GET /api/v1/orders/<id>/ — a single order's full detail, scoped to its owner."""

    serializer_class = OrderSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Order.objects.filter(user=self.request.user).prefetch_related("items")


class OrderCancelView(APIView):
    """
    POST /api/v1/orders/<id>/cancel/
    Customer-triggered cancellation of their OWN order — only while
    status is still pending_payment or confirmed (before fulfillment
    has started). Staff/admin can also cancel via this same endpoint;
    the ownership check is skipped for them.
    """

    permission_classes = [IsAuthenticated]

    # hint-> Insecure Direct Object Reference (IDOR) -> we need to check the order is belong to the user or not
    def post(self, request, pk):
        is_staff = request.user.role in ("admin", "staff")

        order = (
            Order.objects.filter(pk=pk).first()
            if is_staff
            else Order.objects.filter(pk=pk, user=request.user).first()
        )

        if order is None:
            return Response(
                {"detail": "Order not found"}, status=status.HTTP_404_NOT_FOUND
            )

        if not is_staff and order.status not in (
            OrderStatus.PENDING_PAYMENT,
            OrderStatus.CONFIRMED,
        ):
            return Response(
                {
                    "detail": "This order can no longer be cancelled online. Please contact support."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = OrderStatusUpdateSerializer(
            data={"status": OrderStatus.CANCELLED}, context={"order": order}
        )
        serializer.is_valid(raise_exception=True)
        update_order = serializer.save()

        return Response(OrderSerializer(update_order).data)


class OrderFulfillmentUpdateView(APIView):
    """
    POST /api/v1/orders/<id>/status/
    Admin/staff only — moves an order through fulfillment
    (processing/shipped/delivered) or resolves payment
    (confirmed/payment_failed from pending_payment). This is the
    endpoint a real payment gateway webhook would eventually call
    for the confirmed/payment_failed transitions, once Stripe/Paymob
    is wired in — for now, triggered manually by an admin/staff user
    to simulate that gateway callback.
    """

    permission_classes = [IsAdminOrStaff]

    def post(self, request, pk):
        order = Order.objects.filter(pk=pk).first()
        if order is None:
            return Response(
                {"detail": "Order not found"}, status=status.HTTP_404_NOT_FOUND
            )
        serializer = OrderStatusUpdateSerializer(
            data={"status": request.data.get("status")}, context={"order": order}
        )
        serializer.is_valid(raise_exception=True)
        update_order = serializer.save()
        # hint -> add .data for convert order object to json to send to client (Response)
        return Response(OrderSerializer(update_order).data)
