from django.contrib.auth import views as auth_views
from django.urls import include, path
from portal.workspace import workspace

urlpatterns = [
    path('workspace/', workspace, name='records_workspace'),
    path('api/', include('portal.api.records_urls')),
    path('api/', include('verification.urls')),
    path('api/', include('ai.api')),
    path('accounts/login/', auth_views.LoginView.as_view(), name='login'),
    path('accounts/logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('', include('portal.urls')),
]
