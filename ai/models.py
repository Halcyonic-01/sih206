from django.conf import settings
from django.db import models


class AiRun(models.Model):
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    document = models.ForeignKey('portal.Document', on_delete=models.PROTECT, null=True)
    operation = models.CharField(max_length=40, default='DOCUMENT_EXTRACTION')
    model = models.CharField(max_length=100)
    input_sha256 = models.CharField(max_length=64, blank=True)
    status = models.CharField(max_length=30)
    error_code = models.CharField(max_length=40, blank=True)
    duration_ms = models.PositiveIntegerField(default=0)
    output = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
