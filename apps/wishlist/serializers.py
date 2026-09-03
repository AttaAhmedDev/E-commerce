from rest_framework import serializers

from apps.products.models import Product
from apps.products.serializers import ProductListSerializer
from .models import WishlistItem


class WishlistItemSerializer(serializers.ModelSerializer):
    """
    Avoids the `source=` field-aliasing trick entirely — product_detail
    is built manually via SerializerMethodField, and product_id is a
    plain field with its own name. No two fields point at the same
    model attribute, so there's no ambiguity in validated_data.
    """

    product_detail = serializers.SerializerMethodField()
    product_id = serializers.PrimaryKeyRelatedField(
        queryset=Product.objects.filter(is_active=True), write_only=True
    )

    class Meta:
        model = WishlistItem
        fields = ["id", "product_detail", "product_id", "created_at"]
        read_only_fields = ["id", "created_at"]

    def get_product_detail(self, obj: WishlistItem) -> dict:
        return ProductListSerializer(obj.product).data

    def validate_product_id(self, value: Product) -> Product:
        user = self.context["request"].user
        if WishlistItem.objects.filter(user=user, product=value).exists():
            raise serializers.ValidationError(
                "This product is already in your wishlist."
            )
        return value
