"""/api/auth/mfa/*: second step of sign-in, step-up, enrolment and removal of an authenticator app (P1-3)."""
import time

from django.conf import settings
from django.contrib.auth import get_user_model, login
from django.db import transaction
from django.utils import timezone
from drf_spectacular.utils import OpenApiResponse, extend_schema, inline_serializer
from rest_framework import serializers, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from access import mfa, totp
from access.logging import log_access
from access.models import MfaDevice

from .auth_views import CurrentUserSerializer, current_user_payload
from .authentication import ApiSessionAuthentication
from .exceptions import envelope

PENDING_SECONDS = 300
MAX_PENDING_TRIES = 5


class CodeSerializer(serializers.Serializer):
    code = serializers.CharField(max_length=20, trim_whitespace=True)


def _code(request):
    serializer = CodeSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    return serializer.validated_data['code']


def _invalid_code():
    return envelope(status.HTTP_400_BAD_REQUEST, 'That code is not right. Check the code in your authenticator app and try again.',
                    code='invalid_mfa_code')


class VerifyLoginView(APIView):
    """Completes a sign-in that the password step left pending. No session user exists yet, so CSRF is checked here."""
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'login'

    @extend_schema(request=CodeSerializer, responses={200: CurrentUserSerializer,
                   400: OpenApiResponse(description='Wrong code, or no sign-in is waiting for one'),
                   429: OpenApiResponse(description='Device locked after repeated wrong codes')})
    def post(self, request):
        ApiSessionAuthentication().enforce_csrf(request)
        code = _code(request)
        pending = request.session.get(mfa.PENDING)
        if (not isinstance(pending, dict) or time.time() - pending.get('at', 0) > PENDING_SECONDS
                or pending.get('tries', 0) >= MAX_PENDING_TRIES):
            request.session.pop(mfa.PENDING, None)
            return envelope(status.HTTP_400_BAD_REQUEST, 'Your sign-in expired. Enter your password again.',
                            code='mfa_pending_expired')
        user = get_user_model().objects.filter(pk=pending['user_id'], is_active=True).first()
        if user is None:
            request.session.pop(mfa.PENDING, None)
            return envelope(status.HTTP_400_BAD_REQUEST, 'Your sign-in expired. Enter your password again.',
                            code='mfa_pending_expired')
        try:
            ok = mfa.check_code(user, code)
        except mfa.MfaLocked as exc:
            return envelope(status.HTTP_429_TOO_MANY_REQUESTS, exc, code='mfa_locked')
        if not ok:
            pending['tries'] = pending.get('tries', 0) + 1
            request.session[mfa.PENDING] = pending
            log_access(request, 'MFA_FAILED', object_type='user', object_id=user.pk, detail=f'username={user.get_username()}')
            return _invalid_code()
        backend = pending.get('backend')
        request.session.pop(mfa.PENDING, None)
        login(request._request, user, backend=backend)
        mfa.mark_verified(request)
        log_access(request, 'MFA_LOGIN', object_type='user', object_id=user.pk)
        return Response(current_user_payload(user, request))


class StepUpView(APIView):
    @extend_schema(request=CodeSerializer, responses={200: inline_serializer('StepUp', {'verified_recently': serializers.BooleanField()}),
                   400: OpenApiResponse(description='Wrong code'), 429: OpenApiResponse(description='Device locked')})
    def post(self, request):
        code = _code(request)
        if not mfa.has_device(request.user):
            return envelope(status.HTTP_400_BAD_REQUEST, 'Two-factor sign-in is not set up for this account.', code='mfa_not_enrolled')
        try:
            ok = mfa.check_code(request.user, code)
        except mfa.MfaLocked as exc:
            return envelope(status.HTTP_429_TOO_MANY_REQUESTS, exc, code='mfa_locked')
        if not ok:
            log_access(request, 'MFA_FAILED', object_type='user', object_id=request.user.pk, detail='step-up')
            return _invalid_code()
        mfa.mark_verified(request)
        log_access(request, 'MFA_STEP_UP', object_type='user', object_id=request.user.pk)
        return Response({'verified_recently': True})


class SetupView(APIView):
    """Start (or restart) enrolment. The secret is shown once here; the device only counts after a first valid code."""

    @extend_schema(request=None, responses={200: inline_serializer('MfaSetup', {
        'secret': serializers.CharField(), 'otpauth_uri': serializers.CharField(), 'issuer': serializers.CharField()})})
    def post(self, request):
        if not mfa.in_scope(request.user):
            return envelope(status.HTTP_403_FORBIDDEN, 'Two-factor sign-in is for staff accounts.')
        if mfa.has_device(request.user):
            mfa.require_recent_mfa(request)  # replacing a working device needs a fresh code
        issuer = getattr(settings, 'MFA_ISSUER', 'Pramaan')
        secret = totp.new_secret()
        with transaction.atomic():
            MfaDevice.objects.filter(user=request.user, confirmed_at__isnull=True).delete()
            if not MfaDevice.objects.filter(user=request.user).exists():
                MfaDevice.objects.create(user=request.user, secret=secret)
            else:  # replacing a confirmed device: the old one stays valid until the new secret is confirmed
                request.session['mfa_replacement_secret'] = secret
        return Response({'secret': secret, 'issuer': issuer,
                         'otpauth_uri': totp.provisioning_uri(secret, request.user.get_username(), issuer)})


class ConfirmView(APIView):
    @extend_schema(request=CodeSerializer, responses={200: CurrentUserSerializer, 400: OpenApiResponse(description='Wrong code')})
    def post(self, request):
        code = _code(request)
        replacement = request.session.get('mfa_replacement_secret')
        with transaction.atomic():
            device = MfaDevice.objects.select_for_update().filter(user=request.user).first()
            if device is None:
                return envelope(status.HTTP_400_BAD_REQUEST, 'Start setup first.', code='mfa_setup_required')
            secret = replacement if device.confirmed_at and replacement else device.secret
            if device.confirmed_at and not replacement:
                return envelope(status.HTTP_400_BAD_REQUEST, 'Two-factor sign-in is already set up.', code='mfa_already_enrolled')
            step = totp.verify(secret, code, last_step=device.last_step)
            if step is None:
                return _invalid_code()
            device.secret, device.confirmed_at, device.last_step = secret, timezone.now(), step
            device.failures, device.locked_until = 0, None
            device.save()
        request.session.pop('mfa_replacement_secret', None)
        mfa.mark_verified(request)
        log_access(request, 'MFA_ENROLLED', object_type='user', object_id=request.user.pk)
        return Response(current_user_payload(request.user, request))


class DisableView(APIView):
    @extend_schema(request=CodeSerializer, responses={204: None, 400: OpenApiResponse(description='Wrong code')})
    def post(self, request):
        code = _code(request)
        if mfa.required(request.user):
            return envelope(status.HTTP_403_FORBIDDEN, 'Two-factor sign-in is required for your role and cannot be turned off.')
        try:
            ok = mfa.check_code(request.user, code)
        except mfa.MfaLocked as exc:
            return envelope(status.HTTP_429_TOO_MANY_REQUESTS, exc, code='mfa_locked')
        if not ok:
            return _invalid_code()
        MfaDevice.objects.filter(user=request.user).delete()
        request.session.pop(mfa.VERIFIED_AT, None)
        log_access(request, 'MFA_DISABLED', object_type='user', object_id=request.user.pk)
        return Response(status=status.HTTP_204_NO_CONTENT)
