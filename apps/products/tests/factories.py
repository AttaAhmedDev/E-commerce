import factory
import io
from PIL import Image
from django.core.files.uploadedfile import SimpleUploadedFile
from apps.products.models import (
    Category,
    Brand,
    Product,
    ProductVariant,
    Inventory,
    ProductImage,
)


class CategoryFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Category

    name = factory.Sequence(lambda n: f"Category {n}")


class BrandFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Brand

    name = factory.Sequence(lambda n: f"Brand {n}")


class ProductFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Product

    name = factory.Sequence(lambda n: f"Product {n}")
    category = factory.SubFactory(CategoryFactory)
    brand = factory.SubFactory(BrandFactory)


class ProductVariantFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = ProductVariant
        skip_postgeneration_save = True

    product = factory.SubFactory(ProductFactory)
    sku = factory.Sequence(lambda n: f"SKU-{n:05d}")
    size = "M"
    color = "Red"
    price = 20.00

    @factory.post_generation
    def inventory(self, create, extracted, **kwargs):
        if create:
            quantity = extracted if extracted is not None else 10
            Inventory.objects.create(variant=self, quantity=quantity)


def generate_test_image(name: str = "test.jpg") -> SimpleUploadedFile:
    """
    Creates a real, valid in-memory image file for tests. Django's
    ImageField validates actual image content (via Pillow), not just
    the filename — a plain text file renamed to .jpg would fail
    validation, so tests need genuinely valid image bytes.
    """
    file = io.BytesIO()
    image = Image.new("RGB", (100, 100), color="red")
    image.save(file, "JPEG")
    file.seek(0)
    return SimpleUploadedFile(name, file.read(), content_type="image/jpeg")
