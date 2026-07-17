import pytest
from rest_framework.test import APIClient
from rest_framework import status

from apps.accounts.tests.factories import UserFactory
from apps.products.models import ProductImage
from .factories import ProductFactory, generate_test_image

pytestmark = pytest.mark.django_db


@pytest.fixture
def admin_client():
    admin = UserFactory(
        email="admin4@example.com", password="AdminPass123", role="admin"
    )
    client = APIClient()
    client.force_authenticate(user=admin)
    return client


class TestProductImage:
    def test_admin_can_upload_image(self, admin_client):
        product = ProductFactory()
        url = f"/api/v1/products/{product.slug}/images/"

        response = admin_client.post(
            url,
            {
                "image": generate_test_image(),
                "alt_text": "Front view",
                "is_primary": True,
            },
            format="multipart",
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["is_primary"] is True

    def test_setting_new_primary_unsets_previous_primary(self, admin_client):
        product = ProductFactory()
        url = f"/api/v1/products/{product.slug}/images/"

        first = admin_client.post(
            url,
            {
                "image": generate_test_image("first.jpg"),
                "is_primary": True,
            },
            format="multipart",
        )
        assert first.data["is_primary"] is True

        second = admin_client.post(
            url,
            {
                "image": generate_test_image("second.jpg"),
                "is_primary": True,
            },
            format="multipart",
        )
        assert second.data["is_primary"] is True

        # The real proof: the FIRST image should no longer be primary
        first_image = ProductImage.objects.get(pk=first.data["id"])
        assert first_image.is_primary is False

    def test_non_image_file_rejected(self, admin_client):
        from django.core.files.uploadedfile import SimpleUploadedFile

        product = ProductFactory()
        url = f"/api/v1/products/{product.slug}/images/"
        fake_file = SimpleUploadedFile(
            "not_an_image.txt", b"just some text", content_type="text/plain"
        )

        response = admin_client.post(url, {"image": fake_file}, format="multipart")

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_customer_cannot_upload_image(self):
        customer = UserFactory(
            email="cust3@example.com", password="Pass123", role="customer"
        )
        client = APIClient()
        client.force_authenticate(user=customer)

        product = ProductFactory()
        response = client.post(
            f"/api/v1/products/{product.slug}/images/",
            {
                "image": generate_test_image(),
            },
            format="multipart",
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_product_detail_shows_primary_image_in_list(self, admin_client):
        product = ProductFactory()
        admin_client.post(
            f"/api/v1/products/{product.slug}/images/",
            {
                "image": generate_test_image(),
                "is_primary": True,
            },
            format="multipart",
        )

        response = APIClient().get("/api/v1/products/")

        assert response.data["results"][0]["primary_image"] is not None
