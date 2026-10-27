"""The old template UI has no second step, so it must not be a way around two-factor sign-in."""
from django.contrib.auth import views as auth_views

from . import mfa


class LegacyLoginView(auth_views.LoginView):
    def form_valid(self, form):
        user = form.get_user()
        if mfa.has_device(user) or mfa.required(user):
            form.add_error(None, 'This account uses two-factor sign-in. Sign in through the main portal instead.')
            return self.form_invalid(form)
        return super().form_valid(form)
