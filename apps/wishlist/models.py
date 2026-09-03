from django.db import models

from apps.accounts.models import User
from apps.products.models import Product


class WishlistItem(models.Model):
    """
    A saved product for a user. Tied to Product, not ProductVariant —
    wishlisting is a general "I want this" signal, not a commitment to
    a specific size/color the way adding to Cart is.

    No container 'Wishlist' model needed (unlike Cart) since this
    always belongs to exactly one user — no guest/session variant to
    support, so we go straight to the item-level table.
    """

    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="wishlist_items"
    )
    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name="wishlist_by"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "wishlist_items"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "product"], name="unique_product_per_user_wishlist"
            ),
        ]

    # string method to return the user and product name in django admin
    def __str__(self) -> str:
        return f"{self.user} -> {self.product.name}"
