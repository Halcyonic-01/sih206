"""S2/S4 discovery extension; release casework remains a future slice."""
from django.urls import path
from .api import views
from .api import report_views

urlpatterns = [
    path('institutions', views.Institutions.as_view(), name='s2-institutions'),
    path('institutions/<int:pk>', views.InstitutionDetail.as_view(), name='s2-institution'),
    path('institutions/<int:pk>/programme-approvals', views.Children.as_view(), name='s2-approvals'),
    path('programme-approvals/<int:pk>', views.ChildDetail.as_view(), name='s2-approval'),
    path('institutions/<int:pk>/obligations', views.Obligations.as_view(), name='s2-obligations'),
    path('obligations/<int:pk>', views.ObligationDetail.as_view(), name='s2-obligation'),
    path('obligations/<int:pk>/proof-receipts', views.ProofReceipts.as_view(), name='s2-proof-receipts'),
    path('calculator', views.Calculator.as_view(), name='s2-calculator'),
    path('rules', views.Rules.as_view(), name='s2-rules'),
    path('imports/institutions/preview', report_views.CsvPreview.as_view(), name='s4-import-preview'),
    path('imports/institutions/<int:pk>/commit', report_views.CsvCommit.as_view(), name='s4-import-commit'),
    path('reports/<str:kind>', report_views.Report.as_view(), name='s4-report'),
    path('kpis', report_views.Kpis.as_view(), name='s4-kpis'),
]
