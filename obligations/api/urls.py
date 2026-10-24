"""TODO(K1): include beneath /api only after shared routing agreement."""
from django.urls import path
from . import views
from . import report_views
from casework import api as case_api

urlpatterns = [
    path('institutions', views.Institutions.as_view()),
    path('institutions/<int:pk>', views.InstitutionDetail.as_view()),
    path('institutions/<int:pk>/programme-approvals', views.Children.as_view()),
    path('programme-approvals/<int:pk>', views.ChildDetail.as_view()),
    path('institutions/<int:pk>/obligations', views.Obligations.as_view()),
    path('obligations/<int:pk>', views.ObligationDetail.as_view()),
    path('calculator', views.Calculator.as_view()),
    path('rules', views.Rules.as_view()),
    path('imports/institutions/preview', report_views.CsvPreview.as_view()),
    path('imports/institutions/<int:pk>/commit', report_views.CsvCommit.as_view()),
    path('reports/<str:kind>', report_views.Report.as_view()),
    path('kpis', report_views.Kpis.as_view()),
    path('releases', case_api.Cases.as_view()),
    path('releases/<int:pk>', case_api.CaseDetail.as_view()),
    path('releases/<int:pk>/letter', case_api.LetterDownload.as_view()),
    path('releases/<int:pk>/clearances/<str:unit>', case_api.Clearance.as_view()),
    path('releases/<int:pk>/<str:action>', case_api.CaseAction.as_view()),
    path('clearance-tasks', case_api.ClearanceQueue.as_view()),
    path('public/verify/<str:token>', case_api.PublicVerify.as_view()),
]
