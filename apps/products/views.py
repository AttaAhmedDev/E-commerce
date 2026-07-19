from rest_framework import viewsets, filters
from apps.common.permissions import IsAdminOrReadOnly
from django_filters.rest_framework import DjangoFilterBackend
from .filters import ProductFilter, ProductOrderingFilter
from django.db import models
from django.db.models import Min
from .models import Category, Brand, Product, ProductVariant, ProductImage
from .serializers import (
    CategorySerializer,
    BrandSerializer,
    ProductListSerializer,
    ProductDetailSerializer,
    ProductVariantSerializer,
    ProductImageSerializer,
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
    permission_classes = [IsAdminOrReadOnly]
    lookup_field = "slug"
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, ProductOrderingFilter]

    filterset_class = ProductFilter
    search_fields = ["name", "description", "category__name", "brand__name"]
    ordering_fields = ["created_at", "name", "price"]
    ordering = ["-created_at"]

    def get_queryset(self):
        queryset = Product.objects.select_related("category", "brand")
        if self.action == "list":
            queryset = queryset.filter(is_active=True)

        # Annotate with the lowest active-variant price so `?ordering=price`
        # / `?ordering=-price` can sort on it. This is a computed value,
        # not a real column — Product itself still has no price field,
        # consistent with the Option A decision. Products with zero
        # variants get NULL here and sort last (or first, DB-dependent)
        # on ascending order — acceptable for a draft/incomplete product.
        queryset = queryset.annotate(
            min_variant_price=Min(
                "variants__price", filter=models.Q(variants__is_active=True)
            )
        )

        queryset = queryset.prefetch_related(
            "variants", "variants__inventory", "images"
        )
        return queryset

    def get_serializer_class(self):
        if self.action == "list":
            return ProductListSerializer
        return ProductDetailSerializer


class ProductVariantViewSet(viewsets.ModelViewSet):
    serializer_class = ProductVariantSerializer
    permission_classes = [IsAdminOrReadOnly]

    def get_queryset(self):
        return ProductVariant.objects.filter(
            product__slug=self.kwargs["product_slug"]
        ).select_related("inventory")

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["product"] = Product.objects.filter(
            slug=self.kwargs["product_slug"]
        ).first()
        return context

    def perform_create(self, serializer):
        product = Product.objects.get(slug=self.kwargs["product_slug"])
        serializer.save(product=product)


class ProductImageViewSet(viewsets.ModelViewSet):
    """
    Manages images for a specific product, nested under it
    (/products/<product_slug>/images/) — same pattern as variants,
    since an image has no independent meaning outside its product.
    """

    serializer_class = ProductImageSerializer
    permission_classes = [IsAdminOrReadOnly]

    def get_queryset(self):
        return ProductImage.objects.filter(product__slug=self.kwargs["product_slug"])

    def perform_create(self, serializer):
        product = Product.objects.get(slug=self.kwargs["product_slug"])
        serializer.save(product=product)
