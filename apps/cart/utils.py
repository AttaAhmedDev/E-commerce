from django.http import HttpRequest
from .models import Cart


def get_or_create_cart(request: HttpRequest) -> Cart:
    """
    Single source of truth for "which cart applies to this request."
    Logged-in users always get their permanent user cart. Anonymous
    users get a cart tied to their Django session — created on first
    use via request.session.session_key.

    This is the function every cart view calls; callers never touch
    Cart.objects directly, so this logic only needs to be correct
    in one place.
    """
    if request.user.is_authenticated:
        cart, _ = Cart.objects.get_or_create(user=request.user)
        return cart

    if not request.session.session_key:
        request.session.create()

    cart, _ = Cart.objects.get_or_create(session_key=request.session.session_key)
    return cart


def merge_session_cart_into_user_cart(request: HttpRequest, user) -> None:
    """
    Called right after login/register. Moves items from the anonymous
    session cart into the user's permanent cart. If the user's cart
    already has the same variant, quantities are ADDED together (not
    overwritten) — e.g. they had 2 in their account from a previous
    session and just added 1 more as a guest, they should end up
    with 3, not 1.

    The session cart is deleted after merging — a cart should never
    exist in an orphaned, already-merged state.
    """
    session_key = request.session.session_key
    if not session_key:
        return

    try:
        session_cart = Cart.objects.get(session_key=session_key)
    except Cart.DoesNotExist:
        return

    user_cart, _ = Cart.objects.get_or_create(user=user)

    for session_item in session_cart.items.select_related("variant"):
        user_item = user_cart.items.filter(variant=session_item.variant).first()
        if user_item:
            user_item.quantity += session_item.quantity
            user_item.save()
        else:
            session_item.cart = user_cart
            session_item.save()

    session_cart.delete()
