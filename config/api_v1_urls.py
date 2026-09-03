from django.urls import path, include

urlpatterns = [
    path("auth/", include("apps.accounts.urls")),
    path("cart/", include("apps.cart.urls")),  # ← new
    path("", include("apps.products.urls")),
    path("wishlist/", include("apps.wishlist.urls")),
]
