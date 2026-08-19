from django.urls import path
from .views import CartView, CartItemAddView, CartItemUpdateView

app_name = "cart"

urlpatterns = [
    path("", CartView.as_view(), name="cart-detail"),
    path("items/", CartItemAddView.as_view(), name="cart-item-add"),
    path("items/<int:item_id>/", CartItemUpdateView.as_view(), name="cart-item-update"),
]
