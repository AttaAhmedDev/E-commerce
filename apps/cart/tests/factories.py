import factory
from apps.cart.models import Cart, CartItem


class CartFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Cart


class CartItemFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = CartItem
