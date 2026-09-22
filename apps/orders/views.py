from rest_framework import status, generics
from rest_framework.decorators import permission_classes
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from .models import Order
from .serializers import OrderSerializer, CheckoutSerializer


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
