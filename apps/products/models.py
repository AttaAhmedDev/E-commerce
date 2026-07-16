from django.db import models
from django.utils.text import slugify
from django.core.exceptions import ValidationError

from apps.common.models import TimeStampedModel


class Category(TimeStampedModel):
    """
    Hierarchical product classification. Supports unlimited nesting via
    self-referencing parent FK (e.g. Electronics > Laptops > Gaming).
    """

    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=120, unique=True, db_index=True)
    parent = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="children",
        help_text="Leave empty for a top-level category.",
    )
    description = models.TextField(blank=True)
    image = models.ImageField(upload_to="categories/", blank=True, null=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "categories"
        verbose_name_plural = "categories"
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["name", "parent"],
                name="unique_category_name_per_parent",
            )
        ]

    def __str__(self) -> str:
        return self.name

    def clean(self) -> None:
        """Prevents a category from being its own ancestor (infinite loop)."""
        if self.parent:
            ancestor = self.parent
            while ancestor is not None:
                if ancestor.pk == self.pk:
                    raise ValidationError("A category cannot be its own ancestor.")
                ancestor = ancestor.parent

    def save(self, *args, **kwargs) -> None:
        if not self.slug:
            self.slug = slugify(self.name)
        self.full_clean()
        super().save(*args, **kwargs)


class Brand(TimeStampedModel):
    """Flat list of product manufacturers/brands — no hierarchy needed."""

    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=120, unique=True, db_index=True)
    logo = models.ImageField(upload_to="brands/", blank=True, null=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "brands"
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs) -> None:
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


class Product(TimeStampedModel):
    """
    Represents the abstract product concept (e.g. "Nike Air Max 90").
    Deliberately has NO price or stock fields — those belong exclusively
    to ProductVariant, the actual sellable unit. This keeps pricing
    logic in exactly one place throughout the whole system.
    """

    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, unique=True, db_index=True)
    description = models.TextField(blank=True)

    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        related_name="products",
    )
    brand = models.ForeignKey(
        Brand,
        on_delete=models.PROTECT,
        related_name="products",
        null=True,
        blank=True,
    )

    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "products"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["category", "is_active"]),
            models.Index(fields=["brand", "is_active"]),
        ]

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs) -> None:
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    @property
    def in_stock(self) -> bool:
        """True if at least one active variant has available inventory."""
        return self.variants.filter(is_active=True, inventory__quantity__gt=0).exists()

    @property
    def price_range(self) -> dict | None:
        """
        Returns {min, max} across active variant prices, so listings
        can show "From $20" or "$20–$45" without loading all variants.
        Returns None if the product has no active variants yet (draft state).
        """
        prices = self.variants.filter(is_active=True).values_list("price", flat=True)
        if not prices:
            return None
        return {"min": min(prices), "max": max(prices)}


class ProductVariant(TimeStampedModel):
    """
    The actual sellable unit — a specific size/color combination of a
    Product, with its own price and SKU. Cart items and Order items
    reference THIS model, never Product directly.
    """

    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="variants",
    )
    sku = models.CharField(max_length=50, unique=True, db_index=True)
    size = models.CharField(max_length=30, blank=True)
    color = models.CharField(max_length=30, blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "product_variants"
        ordering = ["id"]
        constraints = [
            models.UniqueConstraint(
                fields=["product", "size", "color"],
                name="unique_variant_per_product",
            ),
            models.CheckConstraint(
                condition=models.Q(price__gt=0),
                name="variant_price_positive",
            ),
        ]

    def __str__(self) -> str:
        attrs = " / ".join(filter(None, [self.size, self.color]))
        return f"{self.product.name} ({attrs})" if attrs else self.product.name


class Inventory(TimeStampedModel):
    """
    Tracks stock separately from variant metadata, since quantity
    changes far more frequently (every order/restock) than price or
    attributes do. Kept in its own table so future row-level locking
    during checkout only locks stock data, not the whole variant.
    """

    variant = models.OneToOneField(
        ProductVariant,
        on_delete=models.CASCADE,
        related_name="inventory",
    )
    quantity = models.PositiveIntegerField(default=0)
    low_stock_threshold = models.PositiveIntegerField(default=5)

    class Meta:
        db_table = "inventory"
        verbose_name_plural = "inventory"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(quantity__gte=0),
                name="inventory_quantity_non_negative",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.variant.sku}: {self.quantity} in stock"

    @property
    def is_low_stock(self) -> bool:
        return 0 < self.quantity <= self.low_stock_threshold

    @property
    def is_out_of_stock(self) -> bool:
        return self.quantity == 0
