"""API route table.

Other owners add endpoints without editing this file: create the module listed in EXTENSION_MODULES
and expose `urlpatterns` (paths relative to /api/). Missing modules are skipped; a module that exists
but fails to import raises, so mistakes are never hidden.
"""
from importlib import import_module

from django.urls import path, re_path
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView

from . import auth_views
from .permissions import DocsPermission

EXTENSION_MODULES = (
    'portal.api.instrument_urls',   # Y3 records, documents, review, renewal
    'portal.api.dashboard_urls',    # Y5 dashboard and search
    'verification.api_urls',        # Y6 verification and reconciliation
    'obligations.api_urls',         # S2 institutions, obligations, calculator, S4 reports and KPIs
    'casework.api_urls',            # S5 release case, clearances, public verification
    'notifications.api_urls',       # K5 inbox
    'ai.api_urls',                  # Y8 / S7 advisory AI
    'audit.api_urls',               # K7 auditor screens
)

urlpatterns = [
    path('auth/csrf/', auth_views.CsrfView.as_view(), name='api-csrf'),
    path('auth/login/', auth_views.LoginView.as_view(), name='api-login'),
    path('auth/logout/', auth_views.LogoutView.as_view(), name='api-logout'),
    path('auth/me/', auth_views.MeView.as_view(), name='api-me'),
    path('health/', auth_views.HealthView.as_view(), name='api-health'),
    path('schema/', SpectacularAPIView.as_view(permission_classes=[DocsPermission]), name='api-schema'),
    path('docs/', SpectacularSwaggerView.as_view(url_name='api-schema', permission_classes=[DocsPermission]),
         name='api-docs'),
    path('redoc/', SpectacularRedocView.as_view(url_name='api-schema', permission_classes=[DocsPermission]),
         name='api-redoc'),
]


def _load_extensions():
    routes = []
    for name in EXTENSION_MODULES:
        try:
            module = import_module(name)
        except ModuleNotFoundError as exc:
            # Only skip when the extension module (or its parent app) itself is absent.
            if exc.name and (name == exc.name or name.startswith(exc.name + '.')):
                continue
            raise
        routes.extend(module.urlpatterns)
    return routes


urlpatterns += _load_extensions()
# Unknown API paths answer in the JSON envelope, never with the React shell or an HTML page.
urlpatterns.append(re_path(r'^.*$', auth_views.NotFoundView.as_view(), name='api-not-found'))
