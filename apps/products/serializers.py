from rest_framework import serializers
from .models import Category, Brand, Product, ProductVariant, Inventory


class CategorySerializer(serializers.ModelSerializer):
    """
    Full representation used for detail views and write operations.
    children exposes immediate subcategories (not deeply nested) to
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


class InventorySerializer(serializers.ModelSerializer):
    is_low_stock = serializers.BooleanField(read_only=True)
    is_out_of_stock = serializers.BooleanField(read_only=True)

    class Meta:
        model = Inventory
        fields = ["quantity", "low_stock_threshold", "is_low_stock", "is_out_of_stock"]


class ProductVariantSerializer(serializers.ModelSerializer):
    """
    Nests Inventory directly since a variant without stock data is
    incomplete — every variant read should show its current stock
    alongside price/attributes in one response.
    """

    inventory = InventorySerializer(required=False)

    class Meta:
        model = ProductVariant
        fields = [
            "id",
            "sku",
            "size",
            "color",
            "price",
            "is_active",
            "inventory",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]

    def validate_sku(self, value: str) -> str:
        qs = ProductVariant.objects.filter(sku=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("A variant with this SKU already exists.")
        return value

    def validate_price(self, value) -> "Decimal":
        if value <= 0:
            raise serializers.ValidationError("Price must be greater than zero.")
        return value

    def validate(self, attrs: dict) -> dict:
        # Determine the product this variant belongs to. On create, it's
        # passed via context (set in the view's perform_create); on
        # update, it's already on self.instance.
        product = attrs.get("product") or (
            self.instance.product if self.instance else None
        )
        if product is None:
            product = self.context.get("product")

        size = attrs.get("size", self.instance.size if self.instance else "")
        color = attrs.get("color", self.instance.color if self.instance else "")

        if product is not None:
            qs = ProductVariant.objects.filter(product=product, size=size, color=color)
            if self.instance:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise serializers.ValidationError(
                    "A variant with this size/color combination already exists for this product."
                )
        return attrs

    def create(self, validated_data: dict) -> ProductVariant:
        inventory_data = validated_data.pop("inventory", {"quantity": 0})
        variant = ProductVariant.objects.create(**validated_data)
        Inventory.objects.create(variant=variant, **inventory_data)
        return variant

    def update(self, instance: ProductVariant, validated_data: dict) -> ProductVariant:
        inventory_data = validated_data.pop("inventory", None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if inventory_data is not None:
            Inventory.objects.update_or_create(
                variant=instance, defaults=inventory_data
            )

        return instance


class ProductListSerializer(serializers.ModelSerializer):
    """
    Lightweight serializer for product LIST views. Deliberately avoids
    nesting the full variants list — a catalog page showing 50 products
    shouldn't pull every variant+inventory row for each one. Uses the
    price_range/in_stock properties instead, which are cheap aggregate
    queries rather than full row hydration.
    """

    category = CategoryMinimalSerializer(read_only=True)
    brand = serializers.SlugRelatedField(slug_field="name", read_only=True)
    price_range = serializers.SerializerMethodField()
    in_stock = serializers.BooleanField(read_only=True)

    class Meta:
        model = Product
        fields = [
            "id",
            "name",
            "slug",
            "category",
            "brand",
            "price_range",
            "in_stock",
            "is_active",
        ]

    def get_price_range(self, obj: Product) -> dict | None:
        return obj.price_range


class ProductDetailSerializer(serializers.ModelSerializer):
    """
    Full representation for a single product page — includes all
    active variants with their inventory. This is the expensive
    serializer, intentionally reserved for detail views only.
    """

    category = CategoryMinimalSerializer(read_only=True)
    category_id = serializers.PrimaryKeyRelatedField(
        source="category", queryset=Category.objects.all(), write_only=True
    )
    brand = BrandSerializer(read_only=True)
    brand_id = serializers.PrimaryKeyRelatedField(
        source="brand",
        queryset=Brand.objects.all(),
        write_only=True,
        required=False,
        allow_null=True,
    )
    variants = ProductVariantSerializer(many=True, read_only=True)
    price_range = serializers.SerializerMethodField()
    in_stock = serializers.BooleanField(read_only=True)

    class Meta:
        model = Product
        fields = [
            "id",
            "name",
            "slug",
            "description",
            "category",
            "category_id",
            "brand",
            "brand_id",
            "variants",
            "price_range",
            "in_stock",
            "is_active",
            "created_at",
        ]
        read_only_fields = ["id", "slug", "created_at"]

    def get_price_range(self, obj: Product) -> dict | None:
        return obj.price_range
