from rest_framework.permissions import BasePermission, SAFE_METHODS


class IsAdminOrReadOnly(BasePermission):
    """
    Anyone (including anonymous users) can perform safe/read operations
    (GET, HEAD, OPTIONS). Only users with role='admin' can create,
    update, or delete. Used for catalog data (categories, brands,
    products) where browsing must be public but editing is restricted.
    """

    def has_permission(self, request, view) -> bool:
        if request.method in SAFE_METHODS:
            return True
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.role == "admin"
        )
