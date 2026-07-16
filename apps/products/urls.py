from django.urls import path, include
from rest_framework_nested import routers
from rest_framework.routers import DefaultRouter

from .views import CategoryViewSet, BrandViewSet, ProductViewSet, ProductVariantViewSet

app_name = "products"

router = DefaultRouter()
router.register("categories", CategoryViewSet, basename="category")
router.register("brands", BrandViewSet, basename="brand")
router.register("products", ProductViewSet, basename="product")

products_router = routers.NestedDefaultRouter(router, "products", lookup="product")
products_router.register("variants", ProductVariantViewSet, basename="product-variant")

urlpatterns = router.urls + products_router.urls
