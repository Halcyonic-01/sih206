from django.contrib.auth import views as auth_views
from django.urls import include, path, re_path

from access.legacy import LegacyLoginView
from portal.spa import spa
from verification.bank_views import confirmation

urlpatterns = [
    path('bank/confirm/<str:token>/', confirmation, name='bank_confirmation'),
    path('api/', include('portal.api.urls')),
    # The previous Django-template interface, kept until 28 Oct 2026. Route names are unchanged.
    path('legacy/accounts/login/', LegacyLoginView.as_view(), name='login'),
    path('legacy/accounts/logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('legacy/', include('portal.urls')),
    # Everything else belongs to the React router.
    re_path(r'^(?!api/|legacy/|static/)(?P<path>.*)$', spa, name='spa'),
]
