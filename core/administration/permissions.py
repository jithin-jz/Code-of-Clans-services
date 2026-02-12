from rest_framework.permissions import BasePermission


class IsAdminUser(BasePermission):
    """
    Permission class to restrict access to staff and superuser accounts only.
    
    This centralizes admin authorization checks instead of manually checking
    `is_staff` or `is_superuser` in each view.
    """
    
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated and (
            request.user.is_staff or request.user.is_superuser
        )
