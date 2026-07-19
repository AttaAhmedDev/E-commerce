import pytest
from decimal import Decimal
from rest_framework.test import APIClient
from rest_framework import status

from .factories import (
    CategoryFactory,
    BrandFactory,
    ProductFactory,
    ProductVariantFactory,
)

pytestmark = pytest.mark.django_db


class TestProductSearch:
    url = "/api/v1/products/"

    def test_search_matches_product_name(self):
        ProductFactory(name="Nike Air Max 90")
        ProductFactory(name="Adidas Ultraboost")

        response = APIClient().get(self.url, {"search": "Air Max"})

        assert len(response.data["results"]) == 1
        assert response.data["results"][0]["name"] == "Nike Air Max 90"

    def test_search_matches_category_name(self):
        category = CategoryFactory(name="Running Shoes")
        ProductFactory(name="Random Product", category=category)
        ProductFactory(name="Other Product")

        response = APIClient().get(self.url, {"search": "Running"})

        assert len(response.data["results"]) == 1


class TestProductFilter:
    url = "/api/v1/products/"

    def test_filter_by_category_slug(self):
        cat_a = CategoryFactory(name="Laptops")
        cat_b = CategoryFactory(name="Phones")
        ProductFactory(category=cat_a)
        ProductFactory(category=cat_b)

        response = APIClient().get(self.url, {"category": cat_a.slug})

        assert len(response.data["results"]) == 1

    def test_filter_by_brand_slug(self):
        brand_a = BrandFactory(name="Nike")
        brand_b = BrandFactory(name="Adidas")
        ProductFactory(brand=brand_a)
        ProductFactory(brand=brand_b)

        response = APIClient().get(self.url, {"brand": brand_a.slug})

        assert len(response.data["results"]) == 1

    def test_filter_by_price_range(self):
        cheap = ProductFactory(name="Cheap Item")
        ProductVariantFactory(product=cheap, sku="SKU-CHEAP", price=Decimal("15.00"))

        expensive = ProductFactory(name="Expensive Item")
        ProductVariantFactory(product=expensive, sku="SKU-EXP", price=Decimal("500.00"))

        response = APIClient().get(self.url, {"min_price": 10, "max_price": 50})

        assert len(response.data["results"]) == 1
        assert response.data["results"][0]["name"] == "Cheap Item"

    def test_price_filter_does_not_duplicate_products_with_multiple_matching_variants(
        self,
    ):
        product = ProductFactory(name="Multi Variant")
        ProductVariantFactory(
            product=product, sku="SKU-A", size="M", color="Red", price=Decimal("20.00")
        )
        ProductVariantFactory(
            product=product, sku="SKU-B", size="L", color="Blue", price=Decimal("25.00")
        )

        response = APIClient().get(self.url, {"min_price": 10, "max_price": 30})

        # Both variants match the range, but the product should appear ONCE
        assert len(response.data["results"]) == 1

    def test_filter_in_stock_true(self):
        in_stock_product = ProductFactory(name="In Stock")
        ProductVariantFactory(product=in_stock_product, sku="SKU-STOCK", inventory=10)

        out_of_stock_product = ProductFactory(name="Out of Stock")
        ProductVariantFactory(
            product=out_of_stock_product, sku="SKU-NOSTOCK", inventory=0
        )

        response = APIClient().get(self.url, {"in_stock": "true"})

        assert len(response.data["results"]) == 1
        assert response.data["results"][0]["name"] == "In Stock"

    def test_combined_filters(self):
        category = CategoryFactory(name="Shoes")
        brand = BrandFactory(name="Nike")
        matching = ProductFactory(name="Nike Shoe", category=category, brand=brand)
        ProductVariantFactory(product=matching, sku="SKU-MATCH", price=Decimal("80.00"))

        non_matching_brand = ProductFactory(
            name="Other Shoe", category=category, brand=BrandFactory(name="Puma")
        )
        ProductVariantFactory(
            product=non_matching_brand, sku="SKU-OTHER", price=Decimal("80.00")
        )

        response = APIClient().get(
            self.url,
            {
                "category": category.slug,
                "brand": brand.slug,
                "min_price": 50,
            },
        )

        assert len(response.data["results"]) == 1
        assert response.data["results"][0]["name"] == "Nike Shoe"


class TestProductOrdering:
    url = "/api/v1/products/"

    def test_ordering_by_name_ascending(self):
        ProductFactory(name="Zebra Product")
        ProductFactory(name="Apple Product")

        response = APIClient().get(self.url, {"ordering": "name"})

        names = [p["name"] for p in response.data["results"]]
        assert names == ["Apple Product", "Zebra Product"]

    def test_ordering_by_price_ascending(self):
        cheap = ProductFactory(name="Cheap")
        ProductVariantFactory(product=cheap, sku="SKU-C1", price=Decimal("10.00"))

        expensive = ProductFactory(name="Expensive")
        ProductVariantFactory(product=expensive, sku="SKU-E1", price=Decimal("100.00"))

        response = APIClient().get(self.url, {"ordering": "price"})

        names = [p["name"] for p in response.data["results"]]
        assert names == ["Cheap", "Expensive"]

    def test_ordering_by_price_descending(self):
        cheap = ProductFactory(name="Cheap")
        ProductVariantFactory(product=cheap, sku="SKU-C2", price=Decimal("10.00"))

        expensive = ProductFactory(name="Expensive")
        ProductVariantFactory(product=expensive, sku="SKU-E2", price=Decimal("100.00"))

        response = APIClient().get(self.url, {"ordering": "-price"})

        names = [p["name"] for p in response.data["results"]]
        assert names == ["Expensive", "Cheap"]
