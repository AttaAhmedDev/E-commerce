from django.db import transaction
from collections import defaultdict

from .models import Order, OrderStatus

# for updating the inventory in database directly
from django.db.models import F
from apps.cart.models import Cart, CartItem

COMMIT = "commit"
RELEASE = "release"
RESTOCK = "restock"


class InvalidTransition(Exception):
    def __init__(self, old_status: str, new_status: str):
        self.old_status = old_status
        self.new_status = new_status
        super().__init__(
            f"Cannot transition order from '{old_status}' to '{new_status}'."
        )


class InventoryMismatch(Exception):
    def __init__(self, missing_variant_ids):
        self.missing_variant_ids = missing_variant_ids

        super().__init__(f"Missing inventory for variants: {missing_variant_ids}")


def _inventory_effect(old: str, new: str) -> str | None:
    if old == OrderStatus.PENDING_PAYMENT:
        if new == OrderStatus.CONFIRMED:
            return COMMIT
        if new in (OrderStatus.PAYMENT_FAILED, OrderStatus.CANCELLED):
            return RELEASE
    elif new == OrderStatus.CANCELLED and old in (
        OrderStatus.CONFIRMED,
        OrderStatus.PROCESSING,
        OrderStatus.SHIPPED,
    ):
        return RESTOCK
    return None


# for restoring the cart from the order
def _restore_cart_from_order(order: Order) -> None:
    # retrieve the cart for the user and boolean to check if the cart was created (tuple)
    cart, _ = Cart.objects.get_or_create(user=order.user)
    existing = {item.variant_id: item for item in cart.items.all()}

    new_items = []
    for line in order.items.all():
        if line.variant_id in existing:
            CartItem.objects.filter(pk=existing[line.variant_id].pk).update(
                quantity=F("quantity") + line.quantity
            )
        else:
            new_items.append(
                CartItem(cart=cart, variant_id=line.variant_id, quantity=line.quantity)
            )

    CartItem.objects.bulk_create(new_items)


def transition_order_status(order: Order, new_status: str) -> Order:
    from apps.products.models import Inventory

    with transaction.atomic():

        order = Order.objects.select_for_update().get(pk=order.pk)
        if not order.can_transition_to(new_status):
            raise InvalidTransition(order.status, new_status)

        effect = _inventory_effect(order.status, new_status)

        if effect:
            # Get the inventory needed for this transition
            # defaultdict is a dictionary that will return 0 if the key is not found
            needed = defaultdict(int)
            for item in order.items.all():
                needed[item.variant_id] += item.quantity

            inventories = {
                inv.variant_id: inv
                for inv in Inventory.objects.select_for_update()
                .filter(variant_id__in=needed.keys())
                .order_by("variant_id")
            }

            missing = needed.keys() - inventories.keys()

            if missing:
                raise InventoryMismatch(sorted(missing))

            for variant_id, qty in needed.items():
                inv = inventories[variant_id]
                if effect == COMMIT:
                    inv.reserved_quantity -= qty
                    inv.quantity -= qty
                elif effect == RELEASE:
                    inv.reserved_quantity -= qty
                else:  # RESTOCK
                    inv.quantity += qty
                inv.save(update_fields=["quantity", "reserved_quantity", "updated_at"])

        order.status = new_status
        order.save(update_fields=["status", "updated_at"])

        if new_status == OrderStatus.PAYMENT_FAILED:
            _restore_cart_from_order(order)

    return order
