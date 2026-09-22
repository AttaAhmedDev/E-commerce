from decimal import Decimal
from django.db import transaction
from rest_framework import serializers

from apps.accounts.models import Address
from apps.products.models import Inventory
from apps.cart.utils import get_or_create_cart
from .models import Order, OrderItem, OrderStatus, PaymentMethod


class OrderItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderItem
        fields = [
            "id",
            "product_name",
            "variant_sku",
            "size",
            "color",
            "price",
            "quantity",
            "subtotal",
        ]


class OrderSerializer(serializers.ModelSerializer):
    """Read representation — used for order history/detail, not checkout input."""

    items = OrderItemSerializer(many=True, read_only=True)

    class Meta:
        model = Order
        fields = [
            "id",
            "status",
            "payment_method",
            "subtotal",
            "shipping_cost",
            "total",
            "shipping_full_name",
            "shipping_phone_number",
            "shipping_address_line_1",
            "shipping_city",
            "shipping_country",
            "billing_full_name",
            "billing_city",
            "items",
            "created_at",
        ]
        read_only_fields = fields


class CheckoutSerializer(serializers.Serializer):
    """
    Input serializer for checkout. Takes address IDs (from the user's
    own address book) and a payment method — NOT cart items directly,
    since the cart itself is the source of truth for what's being
    ordered. This prevents a client from checking out with arbitrary
    items that were never actually in their cart.
    """

    shipping_address_id = serializers.PrimaryKeyRelatedField(
        queryset=Address.objects.all()
    )
    billing_address_id = serializers.PrimaryKeyRelatedField(
        queryset=Address.objects.all()
    )
    payment_method = serializers.ChoiceField(choices=PaymentMethod.choices)

    def validate_shipping_address_id(self, value: Address) -> Address:
        request = self.context["request"]
        if value.user != request.user:
            raise serializers.ValidationError("This address does not belong to you.")
        return value

    def validate_billing_address_id(self, value: Address) -> Address:
        request = self.context["request"]
        if value.user != request.user:
            raise serializers.ValidationError("This address does not belong to you.")
        return value

    def create(self, validated_data: dict) -> Order:
        request = self.context["request"]
        user = request.user
        cart = get_or_create_cart(request)

        cart_items = list(
            cart.items.select_related("variant", "variant__product").all()
        )
        if not cart_items:
            raise serializers.ValidationError("Your cart is empty.")

        shipping = validated_data["shipping_address_id"]
        billing = validated_data["billing_address_id"]
        payment_method = validated_data["payment_method"]

        with transaction.atomic():
            # Lock every relevant Inventory row up front, in a
            # consistent order (by variant id), before validating
            # anything. Locking in a consistent order across all
            # concurrent checkouts prevents deadlocks that could
            # otherwise occur if two transactions locked the same two
            # rows in opposite orders.
            variant_ids = sorted(item.variant_id for item in cart_items)
            inventories = {
                inv.variant_id: inv
                for inv in Inventory.objects.select_for_update().filter(
                    variant_id__in=variant_ids
                )
            }

            for item in cart_items:
                inventory = inventories.get(item.variant_id)
                available = inventory.available_quantity if inventory else 0
                if item.quantity > available:
                    raise serializers.ValidationError(
                        f"Only {available} units of {item.variant.sku} are available."
                    )

            subtotal = sum(item.variant.price * item.quantity for item in cart_items)
            shipping_cost = Decimal(
                "0.00"
            )  # flat/free for now — shipping cost calculation is a future feature
            total = subtotal + shipping_cost

            order = Order.objects.create(
                user=user,
                status=(
                    OrderStatus.PENDING_PAYMENT
                    if payment_method == PaymentMethod.ONLINE
                    else OrderStatus.CONFIRMED
                ),
                payment_method=payment_method,
                subtotal=subtotal,
                shipping_cost=shipping_cost,
                total=total,
                shipping_full_name=shipping.full_name,
                shipping_phone_number=shipping.phone_number,
                shipping_address_line_1=shipping.address_line_1,
                shipping_address_line_2=shipping.address_line_2,
                shipping_city=shipping.city,
                shipping_state=shipping.state,
                shipping_postal_code=shipping.postal_code,
                shipping_country=shipping.country,
                billing_full_name=billing.full_name,
                billing_phone_number=billing.phone_number,
                billing_address_line_1=billing.address_line_1,
                billing_address_line_2=billing.address_line_2,
                billing_city=billing.city,
                billing_state=billing.state,
                billing_postal_code=billing.postal_code,
                billing_country=billing.country,
            )

            for item in cart_items:
                variant = item.variant
                OrderItem.objects.create(
                    order=order,
                    variant=variant,
                    product_name=variant.product.name,
                    variant_sku=variant.sku,
                    size=variant.size,
                    color=variant.color,
                    price=variant.price,
                    quantity=item.quantity,
                    subtotal=variant.price * item.quantity,
                )

                inventory = inventories[item.variant_id]
                if payment_method == PaymentMethod.COD:
                    inventory.quantity -= item.quantity
                else:
                    inventory.reserved_quantity += item.quantity
                inventory.save()

            cart.items.all().delete()

        return order
