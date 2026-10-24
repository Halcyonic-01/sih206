from rest_framework import serializers

from .models import Notification


class NotificationSerializer(serializers.ModelSerializer):
    is_read = serializers.BooleanField(read_only=True)

    class Meta:
        model = Notification
        fields = ['id', 'template_id', 'subject', 'body', 'link', 'severity', 'created_at', 'read_at', 'is_read']
        read_only_fields = fields
