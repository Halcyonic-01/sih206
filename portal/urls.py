from django.urls import path
from . import views

urlpatterns = [
    path('', views.instrument_list, name='instrument_list'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('releases/', views.release_queue, name='release_queue'),
    path('instruments/new/', views.instrument_create, name='instrument_create'),
    path('instruments/export.csv', views.instrument_export, name='instrument_export'),
    path('instruments/<int:pk>/', views.instrument_detail, name='instrument_detail'),
    path('instruments/<int:pk>/edit/', views.instrument_edit, name='instrument_edit'),
    path('instruments/<int:pk>/renew/', views.instrument_renew, name='instrument_renew'),
    path('instruments/<int:pk>/release-requests/', views.release_request, name='release_request'),
    path('instruments/<int:pk>/release-requests/<int:release_pk>/decision/',
         views.release_decision, name='release_decision'),
    path('instruments/<int:pk>/release-requests/<int:release_pk>/completion/',
         views.release_completion, name='release_completion'),
    path('instruments/<int:pk>/submit/', views.instrument_submit, name='instrument_submit'),
    path('instruments/<int:pk>/review/', views.instrument_review, name='instrument_review'),
    path('instruments/<int:pk>/observations/', views.observation_add, name='observation_add'),
    path('instruments/<int:pk>/observations/<int:observation_pk>/resolve/',
         views.observation_resolve, name='observation_resolve'),
    path('documents/<int:pk>/download/', views.document_download, name='document_download'),
]
