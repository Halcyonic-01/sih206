from rest_framework.authentication import SessionAuthentication


class ApiSessionAuthentication(SessionAuthentication):
    """Session + CSRF, answering 401 (not 403) when nobody is signed in so React can redirect to /login."""

    def authenticate_header(self, request):
        return 'Session'

    def authenticate(self, request):
        result = super().authenticate(request)
        if result is not None:
            from access import mfa
            user = result[0]
            # MFA_REQUIRED: staff who have not enrolled can only reach /api/auth/* (to enrol) until they do.
            if mfa.required(user) and not request.path.startswith('/api/auth/') and mfa.device_for(user) is None:
                raise mfa.MfaEnrolmentRequired('Set up two-factor sign-in before using the portal.')
        return result


try:
    from drf_spectacular.extensions import OpenApiAuthenticationExtension

    class ApiSessionScheme(OpenApiAuthenticationExtension):
        target_class = 'portal.api.authentication.ApiSessionAuthentication'
        name = 'sessionAuth'

        def get_security_definition(self, auto_schema):
            return {'type': 'apiKey', 'in': 'cookie', 'name': 'sessionid',
                    'description': 'Django session cookie. Writes also need the X-CSRFToken header.'}
except ImportError:  # pragma: no cover - documentation helper only
    pass
