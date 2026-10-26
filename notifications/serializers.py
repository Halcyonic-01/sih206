from rest_framework import serializers
from drf_spectacular.utils import extend_schema_field

from .models import Notification
from .i18n import display_translations


class LocalizedMessageSerializer(serializers.Serializer):
    subject = serializers.CharField()
    body = serializers.CharField()


class NotificationTranslationsSerializer(serializers.Serializer):
    hi = LocalizedMessageSerializer(required=False)


class NotificationSerializer(serializers.ModelSerializer):
    is_read = serializers.BooleanField(read_only=True)
    translations = serializers.SerializerMethodField()

    @extend_schema_field(NotificationTranslationsSerializer)
    def get_translations(self, obj):
        return display_translations(obj)

    class Meta:
        model = Notification
        fields = ['id', 'template_id', 'subject', 'body', 'link', 'severity', 'created_at', 'read_at', 'is_read', 'translations']
        read_only_fields = fields
