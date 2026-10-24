"""S2 platform discovery extension; S4/S5 routes remain separate future slices."""
from django.urls import path
from .api import views

urlpatterns = [
    path('institutions', views.Institutions.as_view(), name='s2-institutions'),
    path('institutions/<int:pk>', views.InstitutionDetail.as_view(), name='s2-institution'),
    path('institutions/<int:pk>/programme-approvals', views.Children.as_view(), name='s2-approvals'),
    path('programme-approvals/<int:pk>', views.ChildDetail.as_view(), name='s2-approval'),
    path('institutions/<int:pk>/obligations', views.Obligations.as_view(), name='s2-obligations'),
    path('obligations/<int:pk>', views.ObligationDetail.as_view(), name='s2-obligation'),
    path('calculator', views.Calculator.as_view(), name='s2-calculator'),
    path('rules', views.Rules.as_view(), name='s2-rules'),
]
