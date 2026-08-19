from rest_framework import serializers
from apps.products.models import ProductVariant
from .models import Cart, CartItem


class CartItemVariantSerializer(serializers.ModelSerializer):
    """
    Lightweight variant representation nested inside cart items — just
    enough for the frontend to render a cart line (name, sku, price,
    stock) without a separate product lookup.
    """

    product_name = serializers.CharField(source="product.name", read_only=True)

    class Meta:
        model = ProductVariant
        fields = ["id", "sku", "product_name", "size", "color", "price"]


class CartItemSerializer(serializers.ModelSerializer):
    variant_detail = CartItemVariantSerializer(source="variant", read_only=True)
    variant_id = serializers.PrimaryKeyRelatedField(
        source="variant",
        queryset=ProductVariant.objects.filter(is_active=True),
        write_only=True,
    )
    subtotal = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)

    class Meta:
        model = CartItem
        fields = ["id", "variant_detail", "variant_id", "quantity", "subtotal"]
        read_only_fields = ["id"]

    def validate(self, attrs: dict) -> dict:
        variant = attrs.get("variant") or (
            self.instance.variant if self.instance else None
        )
        quantity = attrs.get(
            "quantity", self.instance.quantity if self.instance else None
        )

        inventory = getattr(variant, "inventory", None)
        if inventory and quantity and quantity > inventory.quantity:
            raise serializers.ValidationError(
                {"quantity": f"Only {inventory.quantity} units available."}
            )
        return attrs


class CartSerializer(serializers.ModelSerializer):
    items = CartItemSerializer(many=True, read_only=True)
    total_items = serializers.IntegerField(read_only=True)
    total_price = serializers.DecimalField(
        max_digits=10, decimal_places=2, read_only=True
    )

    class Meta:
        model = Cart
        fields = ["id", "items", "total_items", "total_price"]
