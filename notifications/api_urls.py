from django.urls import path

from . import views

urlpatterns = [
    path('notifications/', views.InboxView.as_view(), name='api-notifications'),
    path('notifications/unread-count/', views.UnreadCountView.as_view(), name='api-notifications-unread'),
    path('notifications/read-all/', views.MarkAllReadView.as_view(), name='api-notifications-read-all'),
    path('notifications/delivery-status/', views.DeliveryStatusView.as_view(), name='api-notifications-delivery'),
    path('notifications/<int:pk>/read/', views.MarkReadView.as_view(), name='api-notifications-read'),
]
