"""Live check of the Gemini set-up with synthetic data only: python manage.py check_ai"""
import base64
import subprocess
from time import monotonic

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from ai.services import (EXTRACTION_SCHEMA, FIELD_NAMES, SYSTEM, ProviderUnavailable, ai_configured, ai_model, call_model,
                         gemini_request, validate_output)

HELP = {
    'NOT_CONFIGURED': 'GEMINI_API_KEY is empty. Paste the key from https://aistudio.google.com/apikey into .env.',
    'KEY_REJECTED': 'Google rejected the key. Copy it again from AI Studio (no quotes or spaces).',
    'MODEL_NOT_FOUND': 'This key cannot use AI_MODEL. Leave AI_MODEL empty for the default (gemini-3.8-flash).',
    'RATE_LIMITED': 'Free-tier limit reached. Wait a minute and run the check again.',
    'NETWORK': 'generativelanguage.googleapis.com could not be reached. Check the internet connection or proxy.',
    'BAD_REQUEST': 'Gemini refused the request format. Report this with the model name.',
}


class Command(BaseCommand):
    help = 'Send one synthetic text request and one synthetic PDF to Gemini and report whether AI assistance works.'

    def handle(self, *args, **options):
        model = ai_model()
        self.stdout.write(f'Model: {model} · AI_ENABLED={getattr(settings, "AI_ENABLED", False)}')
        if not ai_configured():
            raise CommandError(HELP['NOT_CONFIGURED'])
        text_schema = {'type': 'object', 'additionalProperties': False, 'required': ['status', 'count'],
                       'properties': {'status': {'type': 'string', 'enum': ['ok']}, 'count': {'type': 'integer'}}}
        self.step('Structured JSON', lambda: call_model(gemini_request(model,
            'Reply only with JSON matching the schema.', [{'text': 'Return status ok and count 3.'}], text_schema)),
            lambda output: output == {'status': 'ok', 'count': 3})
        pdf = (settings.BASE_DIR / 'fixtures' / 'sample-fdr.pdf').read_bytes()  # synthetic demo document
        self.step('PDF field extraction', lambda: validate_output(call_model(gemini_request(model, SYSTEM,
            [{'pdf': base64.b64encode(pdf).decode('ascii')},
             {'text': 'Extract the fields using the supplied schema. Unknown values must be null.'}],
            EXTRACTION_SCHEMA)), 1), lambda output: set(output['fields']) == set(FIELD_NAMES))
        if not getattr(settings, 'AI_ENABLED', False):
            self.stdout.write(self.style.WARNING('Gemini works, but AI_ENABLED=false: set it to true to use it in the portal.'))
        self.stdout.write(self.style.SUCCESS('Gemini AI assistance is working.'))

    def step(self, label, call, valid):
        started = monotonic()
        try:
            output = call()
        except ProviderUnavailable as failure:
            raise CommandError(f'{label}: failed ({failure.code}). {HELP.get(failure.code, "")}'.strip())
        except subprocess.TimeoutExpired:
            raise CommandError(f'{label}: no answer within 30 seconds. Try again; the free tier can be slow.')
        except ValueError:
            raise CommandError(f'{label}: the answer did not pass validation.')
        if not valid(output):
            raise CommandError(f'{label}: unexpected answer {str(output)[:200]}')
        self.stdout.write(f'{label}: OK ({monotonic() - started:.1f} s)')
