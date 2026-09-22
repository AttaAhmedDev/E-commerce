from django.db import models

from apps.common.models import TimeStampedModel
from apps.accounts.models import User
from apps.products.models import ProductVariant


class OrderStatus(models.TextChoices):
    PENDING_PAYMENT = "pending_payment", "Pending Payment"
    CONFIRMED = "confirmed", "Confirmed"
    PROCESSING = "processing", "Processing"
    SHIPPED = "shipped", "Shipped"
    DELIVERED = "delivered", "Delivered"
    CANCELLED = "cancelled", "Cancelled"
    PAYMENT_FAILED = "payment_failed", "Payment Failed"


class PaymentMethod(models.TextChoices):
    COD = "cod", "Cash on Delivery"
    ONLINE = "online", "Online Payment"


class Order(TimeStampedModel):
    """
    Represents a placed order. Address fields are SNAPSHOTTED (copied)
    from the user's chosen Address at checkout time, not held as a
    live FK — editing or deleting a saved address must never alter
    the record of where a past order was actually shipped.

    user uses PROTECT (not CASCADE) deliberately: deleting a user
    account must never silently delete order history, which may have
    legal/accounting retention requirements. Account deletion flows
    must handle orders explicitly, not as a cascade side effect.
    """

    user = models.ForeignKey(User, on_delete=models.PROTECT, related_name="orders")

    status = models.CharField(
        max_length=20, choices=OrderStatus.choices, default=OrderStatus.PENDING_PAYMENT
    )
    payment_method = models.CharField(max_length=10, choices=PaymentMethod.choices)

    subtotal = models.DecimalField(max_digits=10, decimal_places=2)
    shipping_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=10, decimal_places=2)

    # Shipping address snapshot
    shipping_full_name = models.CharField(max_length=150)
    shipping_phone_number = models.CharField(max_length=20)
    shipping_address_line_1 = models.CharField(max_length=255)
    shipping_address_line_2 = models.CharField(max_length=255, blank=True)
    shipping_city = models.CharField(max_length=100)
    shipping_state = models.CharField(max_length=100, blank=True)
    shipping_postal_code = models.CharField(max_length=20)
    shipping_country = models.CharField(max_length=100)

    # Billing address snapshot
    billing_full_name = models.CharField(max_length=150)
    billing_phone_number = models.CharField(max_length=20)
    billing_address_line_1 = models.CharField(max_length=255)
    billing_address_line_2 = models.CharField(max_length=255, blank=True)
    billing_city = models.CharField(max_length=100)
    billing_state = models.CharField(max_length=100, blank=True)
    billing_postal_code = models.CharField(max_length=20)
    billing_country = models.CharField(max_length=100)

    class Meta:
        db_table = "orders"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "status"]),
        ]

    def __str__(self) -> str:
        return f"Order #{self.id} — {self.user.email} ({self.status})"


class OrderItem(models.Model):
    """
    Snapshots product_name/variant_sku/size/color/price as plain
    values at time of order — NOT computed from the live variant —
    so a price change or product rename next month never rewrites
    what a historical order actually showed the customer.

    variant uses PROTECT: a ProductVariant referenced by any order
    history must never be deletable, since the FK needs to keep
    resolving (e.g. for a future "reorder" feature), even though the
    snapshot fields above already protect against data loss if it
    somehow became unreachable.
    """

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    variant = models.ForeignKey(
        ProductVariant, on_delete=models.PROTECT, related_name="order_items"
    )

    product_name = models.CharField(max_length=200)
    variant_sku = models.CharField(max_length=50)
    size = models.CharField(max_length=30, blank=True)
    color = models.CharField(max_length=30, blank=True)

    price = models.DecimalField(max_digits=10, decimal_places=2)
    quantity = models.PositiveIntegerField()
    subtotal = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        db_table = "order_items"

    def __str__(self) -> str:
        return f"{self.quantity} x {self.variant_sku} (Order #{self.order_id})"
