from django.urls import path
from .views import WishlistView, WishlistAddView, WishlistRemoveView

app_name = "wishlist"

urlpatterns = [
    path("", WishlistView.as_view(), name="wishlist-list"),
    path("items/", WishlistAddView.as_view(), name="wishlist-add"),
    path("items/<int:item_id>/", WishlistRemoveView.as_view(), name="wishlist-remove"),
]
