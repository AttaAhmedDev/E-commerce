import pytest
from decimal import Decimal
from rest_framework.test import APIClient
from rest_framework import status

from apps.accounts.tests.factories import UserFactory
from .factories import (
    CategoryFactory,
    BrandFactory,
    ProductFactory,
    ProductVariantFactory,
)

pytestmark = pytest.mark.django_db


@pytest.fixture
def admin_client():
    admin = UserFactory(
        email="admin3@example.com", password="AdminPass123", role="admin"
    )
    client = APIClient()
    client.force_authenticate(user=admin)
    return client


class TestProductRead:
    url = "/api/v1/products/"

    def test_anonymous_can_list_products(self):
        ProductFactory.create_batch(3)
        response = APIClient().get(self.url)

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["results"]) == 3

    def test_list_excludes_inactive_products(self):
        ProductFactory(is_active=True)
        ProductFactory(is_active=False)

        response = APIClient().get(self.url)

        assert len(response.data["results"]) == 1

    def test_list_uses_lightweight_serializer(self):
        product = ProductFactory()
        ProductVariantFactory(product=product)

        response = APIClient().get(self.url)

        # variants should NOT be nested in list view (ProductListSerializer)
        assert "variants" not in response.data["results"][0]
        assert "price_range" in response.data["results"][0]

    def test_detail_includes_variants(self):
        product = ProductFactory()
        ProductVariantFactory(product=product, sku="SKU-DETAIL-1")

        response = APIClient().get(f"{self.url}{product.slug}/")

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["variants"]) == 1
        assert response.data["variants"][0]["sku"] == "SKU-DETAIL-1"

    def test_price_range_reflects_variants(self):
        product = ProductFactory()
        ProductVariantFactory(product=product, sku="SKU-A", price=Decimal("20.00"))
        ProductVariantFactory(product=product, sku="SKU-B", price=Decimal("45.00"))

        response = APIClient().get(f"{self.url}{product.slug}/")

        assert response.data["price_range"] == {
            "min": Decimal("20.00"),
            "max": Decimal("45.00"),
        }

    def test_product_with_no_variants_has_null_price_range(self):
        product = ProductFactory()

        response = APIClient().get(f"{self.url}{product.slug}/")

        assert response.data["price_range"] is None
        assert response.data["in_stock"] is False


class TestProductWrite:
    url = "/api/v1/products/"

    def test_anonymous_cannot_create_product(self):
        category = CategoryFactory()
        response = APIClient().post(
            self.url, {"name": "New Product", "category_id": category.id}
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_admin_can_create_product(self, admin_client):
        category = CategoryFactory()
        brand = BrandFactory()

        response = admin_client.post(
            self.url,
            {
                "name": "Air Max 90",
                "category_id": category.id,
                "brand_id": brand.id,
                "description": "A classic sneaker.",
            },
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["slug"] == "air-max-90"

    def test_product_can_be_created_without_brand(self, admin_client):
        category = CategoryFactory()

        response = admin_client.post(
            self.url,
            {
                "name": "Generic Item",
                "category_id": category.id,
            },
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["brand"] is None


class TestProductVariant:
    def test_admin_can_create_variant_with_inventory(self, admin_client):
        product = ProductFactory()
        url = f"/api/v1/products/{product.slug}/variants/"

        response = admin_client.post(
            url,
            {
                "sku": "SKU-NEW-001",
                "size": "L",
                "color": "Blue",
                "price": "29.99",
                "inventory": {"quantity": 15, "low_stock_threshold": 3},
            },
            format="json",
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["inventory"]["quantity"] == 15

    def test_duplicate_sku_rejected(self, admin_client):
        ProductVariantFactory(sku="SKU-DUP-001")
        product = ProductFactory()
        url = f"/api/v1/products/{product.slug}/variants/"

        response = admin_client.post(
            url,
            {
                "sku": "SKU-DUP-001",
                "price": "10.00",
            },
            format="json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_duplicate_size_color_for_same_product_rejected(self, admin_client):
        product = ProductFactory()
        ProductVariantFactory(product=product, size="M", color="Red")

        # This hits the model-level UniqueConstraint, not serializer
        # validation, since size+color combos aren't checked in the
        # serializer directly.
        from apps.products.models import ProductVariant
        from django.db import IntegrityError

        with pytest.raises(IntegrityError):
            ProductVariant.objects.create(
                product=product,
                sku="SKU-DUP-COMBO",
                size="M",
                color="Red",
                price=15,
            )

    def test_variant_negative_price_rejected_at_db_level(self):
        from apps.products.models import ProductVariant
        from django.db import IntegrityError

        product = ProductFactory()
        with pytest.raises(IntegrityError):
            ProductVariant.objects.create(
                product=product,
                sku="SKU-NEG-001",
                price=-5,
            )

    def test_customer_cannot_create_variant(self):
        customer = UserFactory(
            email="cust2@example.com", password="Pass123", role="customer"
        )
        client = APIClient()
        client.force_authenticate(user=customer)

        product = ProductFactory()
        response = client.post(
            f"/api/v1/products/{product.slug}/variants/",
            {
                "sku": "SKU-BLOCKED",
                "price": "10.00",
            },
            format="json",
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN
