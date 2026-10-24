"""DRF permission classes built on the existing fail-closed role helpers."""
from django.conf import settings
from rest_framework.permissions import BasePermission

from portal.permissions import role


def has_role(*allowed):
    """Permission class factory: has_role('officer', 'authority')."""

    class HasRole(BasePermission):
        message = 'Your account role cannot use this endpoint.'

        def has_permission(self, request, view):
            return role(request.user) in allowed

    HasRole.__name__ = 'HasRole_' + '_'.join(allowed)
    return HasRole


class DocsPermission(BasePermission):
    """API docs are open in local DEBUG mode (or API_DOCS_PUBLIC=true); otherwise sign-in is required."""

    def has_permission(self, request, view):
        return settings.API_DOCS_PUBLIC or request.user.is_authenticated
