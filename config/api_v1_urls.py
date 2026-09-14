from django.urls import path, include

urlpatterns = [
    path("auth/", include("apps.accounts.urls")),
    path("cart/", include("apps.cart.urls")),
    path("", include("apps.products.urls")),
    path("wishlist/", include("apps.wishlist.urls")),
]
