from django.urls import path, include

urlpatterns = [
    path("auth/", include("apps.accounts.urls")),
    path("", include("apps.products.urls")),  # ← new
]
