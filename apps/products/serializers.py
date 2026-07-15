from rest_framework import serializers
from .models import Category, Brand


class CategorySerializer(serializers.ModelSerializer):
    """
    Full representation used for detail views and write operations.
    `children` exposes immediate subcategories (not deeply nested) to
    avoid recursive serialization cost — the frontend can request
    subcategories separately if it needs deeper trees.
    """

    children = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = [
            "id",
            "name",
            "slug",
            "parent",
            "description",
            "image",
            "is_active",
            "children",
            "created_at",
        ]
        read_only_fields = ["id", "slug", "created_at"]

    def get_children(self, obj: Category) -> list:
        return CategoryMinimalSerializer(
            obj.children.filter(is_active=True), many=True
        ).data

    def validate_parent(self, value: Category | None) -> Category | None:
        # Prevent setting a category as its own parent directly at the
        # serializer level too — model.clean() also catches deeper
        # cycles, but this gives an immediate, cheap check first.
        if value and self.instance and value.pk == self.instance.pk:
            raise serializers.ValidationError("A category cannot be its own parent.")
        return value


class CategoryMinimalSerializer(serializers.ModelSerializer):
    """Lightweight representation used for nesting (children list, product listings)."""

    class Meta:
        model = Category
        fields = ["id", "name", "slug"]


class BrandSerializer(serializers.ModelSerializer):
    class Meta:
        model = Brand
        fields = [
            "id",
            "name",
            "slug",
            "logo",
            "description",
            "is_active",
            "created_at",
        ]
        read_only_fields = ["id", "slug", "created_at"]
