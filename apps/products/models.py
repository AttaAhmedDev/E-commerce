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
