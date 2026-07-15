from rest_framework import viewsets
from apps.common.permissions import IsAdminOrReadOnly

from .models import Category, Brand
from .serializers import CategorySerializer, BrandSerializer


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
