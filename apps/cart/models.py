from django.db import models
from django.core.exceptions import ValidationError
from apps.common.models import TimeStampedModel
from apps.accounts.models import User
from apps.products.models import ProductVariant


class Cart(TimeStampedModel):
    """
    Belongs to EITHER a logged-in user OR an anonymous session — never
    both, never neither. Enforced by a DB-level CheckConstraint, not
    just application logic, since this is a genuine data-integrity
    rule (a cart with no owner at all, or two owners, is invalid data
    regardless of how it was created).
    """

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="cart",
    )

    # NOTE: Implement session-based cart support
    session_key = models.CharField(
        max_length=40,
        null=True,
        blank=True,
        unique=True,
        db_index=True,
        help_text="Session key for anonymous cart",
    )

    class Meta:
        db_table = "carts"
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(user__isnull=False, session_key__isnull=True)
                    | models.Q(user__isnull=True, session_key__isnull=False)
                ),
                name="cart_has_exactly_one_owner",
            ),
        ]

    def __str__(self) -> str:
        return (
            f"Cart for {self.user}"
            if self.user
            else f"Guest cart ({self.session_key})"
        )

    @property
    def total_items(self) -> int:
        return sum(item.quantity for item in self.items.all())

    @property
    def total_price(self):
        return sum(item.subtotal for item in self.items.all())


class CartItem(TimeStampedModel):
    """
    References ProductVariant (the sellable unit), never Product
    directly — consistent with the rest of the catalog design.
    Deliberately does NOT store price — always reads variant.price
    live, since a cart isn't a commitment yet (unlike an Order, which
    will snapshot price at checkout time).
    """

    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name="items")
    variant = models.ForeignKey(
        ProductVariant, on_delete=models.CASCADE, related_name="cart_items"
    )
    quantity = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "cart_items"
        constraints = [
            models.UniqueConstraint(
                fields=["cart", "variant"], name="unique_variant_per_cart"
            ),
            models.CheckConstraint(
                condition=models.Q(quantity__gt=0),
                name="cart_item_quantity_positive",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.quantity} x {self.variant.sku}"

    @property
    def subtotal(self):
        return self.variant.price * self.quantity

    def clean(self) -> None:
        """
        Prevents adding more than what's actually in stock. Runs on
        save so this holds regardless of entry point (API, admin,
        script) — not just serializer-level validation.
        """
        available = getattr(self.variant, "inventory", None)
        if available and self.quantity > available.quantity:
            raise ValidationError(
                f"Only {available.quantity} units of {self.variant.sku} are available."
            )

    def save(self, *args, **kwargs) -> None:
        self.full_clean()
        super().save(*args, **kwargs)
