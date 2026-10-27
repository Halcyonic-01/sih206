from django.urls import path

from . import api, retention_api

urlpatterns = [
    path('retention/due/', retention_api.Due.as_view(), name='api-retention-due'),
    path('instruments/<int:pk>/archive/', retention_api.Archive.as_view(), name='api-archive'),
    path('instruments/<int:pk>/legal-hold/', retention_api.Hold.as_view(), name='api-legal-hold'),
    path('audit/events/', api.AuditEventList.as_view(), name='api-audit-events'),
    path('audit/events/facets/', api.AuditFacets.as_view(), name='api-audit-facets'),
    path('audit/events/export/', api.AuditEventExport.as_view(), name='api-audit-export'),
    path('audit/events/<int:pk>/', api.AuditEventDetail.as_view(), name='api-audit-event'),
    path('audit/chain/verify/', api.ChainVerify.as_view(), name='api-audit-chain-verify'),
    path('audit/access-log/', api.AccessLogList.as_view(), name='api-access-log'),
    path('audit/access-log/facets/', api.AccessLogFacets.as_view(), name='api-access-log-facets'),
    path('audit/access-log/export/', api.AccessLogExport.as_view(), name='api-access-log-export'),
]
