"""/api/auth/*: CSRF bootstrap, sign-in with lockout, sign-out and the current user."""
from axes.handlers.proxy import AxesProxyHandler
from django.contrib.auth import authenticate, login, logout
from django.core.exceptions import PermissionDenied
from django.db import connection
from django.http import Http404
from django.middleware.csrf import get_token
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import ensure_csrf_cookie
from drf_spectacular.utils import OpenApiResponse, extend_schema, inline_serializer
from rest_framework import serializers, status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from portal.models import UserProfile
from portal.permissions import clearance_unit, role

from .authentication import ApiSessionAuthentication
from .exceptions import envelope


class InstitutionSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    code = serializers.CharField()
    name = serializers.CharField()


class CurrentUserSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    username = serializers.CharField()
    display_name = serializers.CharField()
    role = serializers.CharField(allow_null=True, help_text='institution, officer, authority, clearance, auditor or null when no role is assigned')
    institution = InstitutionSerializer(allow_null=True)
    unit = serializers.CharField(allow_null=True, help_text='PGRC, VIGILANCE or GRANTS for a clearance-unit account')


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150, trim_whitespace=True)
    password = serializers.CharField(max_length=256, trim_whitespace=False, write_only=True)


def current_user_payload(user):
    institution = None
    profile = UserProfile.objects.select_related('institution').filter(user=user).first()
    if profile:
        institution = {'id': profile.institution_id, 'code': profile.institution.code,
                       'name': profile.institution.name}
    current_role = role(user)
    try:
        unit = clearance_unit(user) if current_role == 'clearance' else None
    except PermissionDenied:
        unit = None
    return {'id': user.pk, 'username': user.get_username(),
            'display_name': user.get_full_name() or user.get_username(),
            'role': current_role, 'institution': institution, 'unit': unit}


class CsrfView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(responses=inline_serializer('CsrfToken', {'csrfToken': serializers.CharField()}))
    @method_decorator(ensure_csrf_cookie)
    def get(self, request):
        return Response({'csrfToken': get_token(request)})


class LoginView(APIView):
    permission_classes = [AllowAny]
    # No session authentication here: the CSRF check is enforced explicitly so login CSRF is blocked too.
    authentication_classes = []
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'login'

    @extend_schema(
        request=LoginSerializer, responses={
            200: CurrentUserSerializer,
            400: OpenApiResponse(description='Invalid credentials or missing fields'),
            429: OpenApiResponse(description='Locked out after repeated failures'),
        })
    def post(self, request):
        ApiSessionAuthentication().enforce_csrf(request)
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        credentials = serializer.validated_data
        user = authenticate(request=request._request, **credentials)
        if user is None:
            if not AxesProxyHandler.is_allowed(request._request, {'username': credentials['username']}):
                return envelope(status.HTTP_429_TOO_MANY_REQUESTS,
                                'Too many failed sign-in attempts. Wait before trying again.', code='locked_out')
            return envelope(status.HTTP_400_BAD_REQUEST, 'Enter a correct username and password.',
                            code='invalid_credentials')
        if not user.is_active:
            return envelope(status.HTTP_400_BAD_REQUEST, 'Enter a correct username and password.',
                            code='invalid_credentials')
        login(request._request, user)
        return Response(current_user_payload(user))


class LogoutView(APIView):
    permission_classes = [AllowAny]
    # Session authentication keeps request.user intact so the sign-out is attributed to the right person.
    authentication_classes = [ApiSessionAuthentication]

    @extend_schema(request=None, responses={204: None})
    def post(self, request):
        ApiSessionAuthentication().enforce_csrf(request)
        logout(request._request)
        return Response(status=status.HTTP_204_NO_CONTENT)


class MeView(APIView):
    @extend_schema(responses={200: CurrentUserSerializer, 401: OpenApiResponse(description='Not signed in')})
    def get(self, request):
        return Response(current_user_payload(request.user))


class HealthView(APIView):
    """Liveness/readiness for run scripts, CI and Docker. Reveals nothing beyond up/down."""
    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(responses={200: inline_serializer('Health', {'status': serializers.CharField(),
                                                                 'time': serializers.DateTimeField()}),
                              503: OpenApiResponse(description='Database unavailable')})
    def get(self, request):
        try:
            with connection.cursor() as cursor:
                cursor.execute('SELECT 1')
        except Exception:
            return envelope(status.HTTP_503_SERVICE_UNAVAILABLE, 'Database unavailable.')
        return Response({'status': 'ok', 'time': timezone.now().isoformat()})


class NotFoundView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(exclude=True)
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        raise Http404
