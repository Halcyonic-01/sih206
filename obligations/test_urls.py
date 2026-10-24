"""Isolated owned integration harness; never selected by the existing app."""
from django.urls import include, path

urlpatterns = [path('api/', include('obligations.api.urls')), path('', include('config.urls'))]
