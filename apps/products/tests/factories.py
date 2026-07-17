import factory
from apps.products.models import Category, Brand, Product, ProductVariant, Inventory


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
            Inventory.objects.create(variant=self, quantity=extracted or 10)
