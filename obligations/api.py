from django.urls import path
from rest_framework.response import Response
from portal.api.records import RecordEndpoint
from portal.deadlines import business_today
from .coverage import coverage, scoped_obligations


class Obligations(RecordEndpoint):
    def get(self, request):
        return Response([coverage(item, business_today()) for item in scoped_obligations(request.user).order_by('pk')[:200]])


urlpatterns = [path('obligations/', Obligations.as_view())]
