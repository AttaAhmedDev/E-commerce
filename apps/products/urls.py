from rest_framework_nested import routers
from rest_framework.routers import DefaultRouter

from .views import (
    CategoryViewSet,
    BrandViewSet,
    ProductViewSet,
    ProductVariantViewSet,
    ProductImageViewSet,
)

router = DefaultRouter()
router.register("categories", CategoryViewSet, basename="category")
router.register("brands", BrandViewSet, basename="brand")
router.register("products", ProductViewSet, basename="product")

products_router = routers.NestedDefaultRouter(router, "products", lookup="product")
products_router.register("variants", ProductVariantViewSet, basename="product-variant")
products_router.register("images", ProductImageViewSet, basename="product-image")

urlpatterns = router.urls + products_router.urls
