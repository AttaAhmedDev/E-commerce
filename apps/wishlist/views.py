from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.generics import ListAPIView

from .models import WishlistItem
from .serializers import WishlistItemSerializer


class WishlistView(ListAPIView):
    """
    GET /api/v1/wishlist/
    Returns only the current user's wishlist items — scoped via
    get_queryset filtering on request.user, same IDOR-safe pattern
    used throughout Cart.
    """

    serializer_class = WishlistItemSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return WishlistItem.objects.filter(user=self.request.user).select_related(
            "product"
        )


class WishlistAddView(APIView):
    """POST /api/v1/wishlist/items/ — add a product to the current user's wishlist."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = WishlistItemSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        product = serializer.validated_data["product_id"]
        item = WishlistItem.objects.create(user=request.user, product=product)
        return Response(
            WishlistItemSerializer(item).data, status=status.HTTP_201_CREATED
        )


class WishlistRemoveView(APIView):
    """
    DELETE /api/v1/wishlist/items/<id>/
    Scoped to WishlistItem.objects.filter(user=request.user, pk=...),
    never a bare .get(pk=...) — same IDOR protection as Cart, so a
    user can never delete another user's wishlist entry by guessing IDs.
    """

    permission_classes = [IsAuthenticated]

    def delete(self, request, item_id):
        item = WishlistItem.objects.filter(user=request.user, pk=item_id).first()
        if item is None:
            return Response(
                {"detail": "Item not found in your wishlist."},
                status=status.HTTP_404_NOT_FOUND,
            )

        item.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
