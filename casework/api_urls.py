"""Release-case routes discovered by ``portal.api.urls``.

Routes have no trailing slash to match the published S2/S4 API contract.  The
module is intentionally separate from ``obligations.api_urls`` so a release
failure cannot shadow institution, reporting or import routes.
"""
from django.urls import path

from . import api


urlpatterns = [
    path('releases', api.Cases.as_view(), name='release-cases'),
    path('releases/requirements', api.Requirements.as_view(), name='release-requirements'),
    path('releases/<int:pk>', api.CaseDetail.as_view(), name='release-case-detail'),
    path('releases/<int:pk>/letter', api.LetterDownload.as_view(), name='release-letter'),
    path('releases/<int:pk>/ai-summary', api.AiSummary.as_view(), name='release-ai-summary'),
    path('releases/<int:pk>/clearances/<str:unit>', api.Clearance.as_view(), name='release-clearance'),
    path('releases/<int:pk>/<str:action>', api.CaseAction.as_view(), name='release-case-action'),
    path('clearance-tasks', api.ClearanceQueue.as_view(), name='release-clearance-queue'),
    path('public/verify/<str:token>', api.PublicVerify.as_view(), name='release-public-verify'),
]
