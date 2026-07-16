from rest_framework import viewsets, filters
from apps.common.permissions import IsAdminOrReadOnly
from django_filters.rest_framework import DjangoFilterBackend

from .models import Category, Brand, Product, ProductVariant
from .serializers import (
    CategorySerializer,
    BrandSerializer,
    ProductListSerializer,
    ProductDetailSerializer,
    ProductVariantSerializer,
)


class CategoryViewSet(viewsets.ModelViewSet):
    """
    Full CRUD for categories. Read access is public; write access is
    admin-only (enforced by IsAdminOrReadOnly).

    Only top-level categories (parent=None) are returned by default in
    the list view — subcategories are reached via the nested `children`
    field on each result. This keeps the main listing shallow and
    readable instead of dumping the entire tree flattened.
    """

    serializer_class = CategorySerializer
    permission_classes = [IsAdminOrReadOnly]
    lookup_field = "slug"

    def get_queryset(self):
        queryset = Category.objects.filter(is_active=True).select_related("parent")
        if self.action == "list":
            queryset = queryset.filter(parent__isnull=True)
        return queryset


class BrandViewSet(viewsets.ModelViewSet):
    """Full CRUD for brands. Read access public, write access admin-only."""

    serializer_class = BrandSerializer
    permission_classes = [IsAdminOrReadOnly]
    lookup_field = "slug"
    queryset = Brand.objects.filter(is_active=True)


class ProductViewSet(viewsets.ModelViewSet):
    """
    Full CRUD for products. Uses different serializers for list vs
    detail/write actions (see serializer docstrings for why). Search,
    filter, and ordering will be wired here properly in the dedicated
    Search/Filter sub-feature — this just establishes the queryset
    structure they'll attach to.
    """

    permission_classes = [IsAdminOrReadOnly]
    lookup_field = "slug"

    def get_queryset(self):
        queryset = Product.objects.select_related("category", "brand")
        if self.action == "list":
            queryset = queryset.filter(is_active=True)
            # Avoids N+1 on price_range/in_stock property access across
            # the whole list, since those hit `variants` per product.
            queryset = queryset.prefetch_related("variants", "variants__inventory")
        return queryset

    def get_serializer_class(self):
        if self.action == "list":
            return ProductListSerializer
        return ProductDetailSerializer


class ProductVariantViewSet(viewsets.ModelViewSet):
    """
    Manages variants for a SPECIFIC product, nested under it in the
    URL (/products/<product_slug>/variants/). A variant only makes
    sense in the context of its parent product, so this is never
    exposed as a flat top-level /variants/ endpoint.
    """

    serializer_class = ProductVariantSerializer
    permission_classes = [IsAdminOrReadOnly]

    def get_queryset(self):
        return ProductVariant.objects.filter(
            product__slug=self.kwargs["product_slug"]
        ).select_related("inventory")

    def perform_create(self, serializer):
        product = Product.objects.get(slug=self.kwargs["product_slug"])
        serializer.save(product=product)
