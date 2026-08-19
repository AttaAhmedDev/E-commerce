from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny

from .models import CartItem
from .serializers import CartSerializer, CartItemSerializer
from .utils import get_or_create_cart


class CartView(APIView):
    """
    GET /api/v1/cart/
    Returns the current cart — resolved transparently to either the
    logged-in user's cart or the anonymous session's cart via
    get_or_create_cart(). The client never needs to know which mode
    it's in; the same endpoint works both ways.
    """

    permission_classes = [AllowAny]

    def get(self, request):
        cart = get_or_create_cart(request)
        return Response(CartSerializer(cart).data)


class CartItemAddView(APIView):
    """
    POST /api/v1/cart/items/
    Adds a variant to the cart. If it's already in the cart, quantity
    is ADDED to the existing line (not replaced) — consistent with the
    same additive behavior used in the login-merge logic.
    """

    permission_classes = [AllowAny]

    def post(self, request):
        cart = get_or_create_cart(request)
        serializer = CartItemSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)

        variant = serializer.validated_data["variant"]
        quantity = serializer.validated_data["quantity"]

        existing = cart.items.filter(variant=variant).first()
        if existing:
            existing.quantity += quantity
            existing.full_clean()
            existing.save()
            return Response(
                CartItemSerializer(existing).data, status=status.HTTP_200_OK
            )

        item = CartItem.objects.create(cart=cart, variant=variant, quantity=quantity)
        return Response(CartItemSerializer(item).data, status=status.HTTP_201_CREATED)


class CartItemUpdateView(APIView):
    """
    PATCH /api/v1/cart/items/<id>/  -> update quantity
    DELETE /api/v1/cart/items/<id>/ -> remove item
    Scoped to the current cart only — a request can never touch
    another cart's item, since get_object() filters by cart=cart, not
    just CartItem.objects.get(pk=...).
    """

    permission_classes = [AllowAny]

    def get_object(self, request, item_id):
        cart = get_or_create_cart(request)
        return cart.items.filter(pk=item_id).first()

    def patch(self, request, item_id):
        item = self.get_object(request, item_id)
        if item is None:
            return Response(
                {"detail": "Item not found in cart."}, status=status.HTTP_404_NOT_FOUND
            )

        serializer = CartItemSerializer(
            item, data=request.data, partial=True, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    def delete(self, request, item_id):
        item = self.get_object(request, item_id)
        if item is None:
            return Response(
                {"detail": "Item not found in cart."}, status=status.HTTP_404_NOT_FOUND
            )

        item.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
