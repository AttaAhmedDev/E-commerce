import django_filters
from .models import Product
from rest_framework.filters import OrderingFilter


class ProductFilter(django_filters.FilterSet):
    """
    Custom filter for products. Price filtering is the non-trivial
    part: since Product has no price field of its own (price lives on
    ProductVariant), min_price/max_price filter products that have AT
    LEAST ONE active variant within that range — not a direct field
    lookup on Product.
    """

    category = django_filters.CharFilter(field_name="category__slug")
    brand = django_filters.CharFilter(field_name="brand__slug")
    min_price = django_filters.NumberFilter(method="filter_min_price")
    max_price = django_filters.NumberFilter(method="filter_max_price")
    in_stock = django_filters.BooleanFilter(method="filter_in_stock")

    class Meta:
        model = Product
        fields = ["category", "brand"]

    def filter_min_price(self, queryset, name, value):
        return queryset.filter(
            variants__price__gte=value, variants__is_active=True
        ).distinct()

    def filter_max_price(self, queryset, name, value):
        return queryset.filter(
            variants__price__lte=value, variants__is_active=True
        ).distinct()

    def filter_in_stock(self, queryset, name, value):
        if value:
            return queryset.filter(
                variants__is_active=True, variants__inventory__quantity__gt=0
            ).distinct()
        return queryset


class ProductOrderingFilter(OrderingFilter):
    """
    Maps the public-facing `price` ordering param to the internal
    `min_variant_price` annotation, since Product itself has no real
    price field — keeps the API surface clean while the underlying
    implementation detail (annotation name) stays internal.
    """

    def get_ordering(self, request, queryset, view):
        ordering = super().get_ordering(request, queryset, view)
        if ordering:
            ordering = [
                field.replace("price", "min_variant_price") for field in ordering
            ]
        return ordering
