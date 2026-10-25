import re
from datetime import timedelta
from django.core import mail
from django.core.exceptions import ValidationError
from django.test import Client, override_settings
from django.utils import timezone
from portal import services
from portal.tests.common import PortalTestCase
from verification.bank import deliver_requests, request_confirmation, respond, token_for
from verification.models import BankConfirmation

CONTACTS = {'ABCD0123456': {'email': 'synthetic-branch@example.invalid', 'source': 'Synthetic test directory', 'approved': True}}


@override_settings(ROOT_URLCONF='config.urls', BANK_CONTACTS=CONTACTS, BANK_CONFIRMATION_SIMULATED=True,
                   EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class BankConfirmationTests(PortalTestCase):
    def record(self):
        item = self.submitted()
        item.ifsc, item.holder_names = 'ABCD0123456', 'Synthetic Trust and Council'
        item.save()
        return item

    def fields(self, item):
        return {'authentic': 'yes', 'reference': item.reference, 'amount': str(item.amount),
            'issue_date': str(item.issue_date), 'maturity_date': str(item.maturity_date), 'ifsc': item.ifsc,
            'holder_names': item.holder_names, 'lien_marked': 'yes', 'loans_or_mortgage': 'no'}

    def challenge(self, item):
        row = request_confirmation(self.officer, item.pk, item.version)
        self.assertEqual(deliver_requests(), 1)
        message = mail.outbox[-1].body
        token = re.search(r'/bank/confirm/([^\s/]+)/', message)[1]
        otp = re.search(r'One-time code: (\d{6})', message)[1]
        row.refresh_from_db()
        self.assertNotIn(otp, row.otp_hash)
        return row, token, otp

    def test_signed_otp_single_use_simulation_never_confirms_or_accepts(self):
        item = self.record()
        row, token, otp = self.challenge(item)
        self.assertTrue(respond(token, otp, self.fields(item)))
        item.refresh_from_db()
        self.assertEqual((item.status, item.verification_level), ('SUBMITTED', 'DECLARED'))
        evidence = item.verification_evidence.get()
        self.assertEqual((evidence.method, evidence.result), ('SIMULATED_BANK', 'SIMULATED_MATCH'))
        with self.assertRaises(ValidationError):
            respond(token, otp, self.fields(item))

    def test_negative_response_discrepancy_with_retained_evidence_and_notice(self):
        item = self.record()
        row, token, otp = self.challenge(item)
        self.assertTrue(respond(token, otp, self.fields(item) | {'authentic': 'no'}))
        item.refresh_from_db()
        self.assertEqual(item.verification_level, 'DISCREPANCY')
        self.assertEqual(item.status, 'SUBMITTED')
        self.assertTrue(item.audit_events.filter(action='BANK_CONFIRMATION_RECEIVED').exists())

    def test_unknown_contacts_role_stale_and_missing_version(self):
        item = self.record()
        url = f'/api/instruments/{item.pk}/bank-requests/'
        self.assertEqual(self.client.post(url, {'version': item.version}, content_type='application/json').status_code, 403)
        self.client.force_login(self.officer)
        self.assertEqual(self.client.post(url, {}, content_type='application/json').status_code, 400)
        with override_settings(BANK_CONTACTS={}):
            self.assertEqual(self.client.post(url, {'version': item.version}, content_type='application/json').status_code, 400)
        self.assertEqual(self.client.post(url, {'version': 999}, content_type='application/json').status_code, 409)
        result = self.client.post(url, {'version': item.version}, content_type='application/json')
        self.assertEqual(result.status_code, 201, result.content)
        self.assertNotIn('token', result.content.decode())
        self.assertNotIn('synthetic-branch', result.content.decode())
        self.client.force_login(self.b)
        self.assertEqual(self.client.get(url).status_code, 404)

    def test_five_wrong_codes_expiry_tampering_and_stale_snapshot(self):
        item = self.record()
        row, token, otp = self.challenge(item)
        wrong = '000000' if otp != '000000' else '999999'
        for _ in range(5):
            self.assertFalse(respond(token, wrong, self.fields(item)))
        self.assertEqual(self.client.get('/bank/confirm/'+token+'tamper/').status_code, 400)
        with self.assertRaises(ValidationError):
            respond(token, otp, self.fields(item))
        BankConfirmation.objects.filter(pk=row.pk).update(otp_attempts=0, status='SENT')
        item.refresh_from_db()
        services._compare_and_update(item, item.version, branch='Changed')
        with self.assertRaises(services.WorkflowError):
            respond(token, otp, self.fields(item))
        BankConfirmation.objects.filter(pk=row.pk).update(expires_at=timezone.now()-timedelta(seconds=1))
        with self.assertRaises(ValidationError):
            respond(token, otp, self.fields(item))

    def test_public_form_has_csrf_no_declared_values_and_invalid_fields_are_rejected(self):
        item = self.record()
        row, token, otp = self.challenge(item)
        client = Client(enforce_csrf_checks=True)
        url = '/bank/confirm/'+token+'/'
        response = client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertNotIn(item.reference, response.content.decode())
        self.assertEqual(response['Referrer-Policy'], 'no-referrer')
        self.assertEqual(client.post(url, self.fields(item) | {'otp': otp}).status_code, 403)
        csrf = client.cookies['csrftoken'].value
        result = client.post(url, self.fields(item) | {'otp': otp, 'amount': 'NaN'}, HTTP_X_CSRFTOKEN=csrf)
        self.assertEqual(result.status_code, 400)
        self.assertEqual(client.post(url, self.fields(item) | {'otp': otp}, HTTP_X_CSRFTOKEN=csrf).status_code, 200)

    @override_settings(BANK_CONFIRMATION_SIMULATED=False, DEBUG=False, BANK_PUBLIC_BASE_URL='https://portal.example.invalid',
                       NOTIFICATION_EMAIL_ENABLED=True, EMAIL_BACKEND='django.core.mail.backends.smtp.EmailBackend')
    def test_live_path_requires_verified_mailbox_challenge_and_preserves_approval_workflow(self):
        from unittest.mock import patch
        item = self.record()
        row = request_confirmation(self.officer, item.pk, item.version)
        with patch('verification.bank.send_mail', return_value=1) as sender:
            self.assertEqual(deliver_requests(), 1)
        message = sender.call_args.args[1]
        token = re.search(r'/bank/confirm/([^\s/]+)/', message)[1]
        otp = re.search(r'One-time code: (\d{6})', message)[1]
        self.assertTrue(respond(token, otp, self.fields(item)))
        item.refresh_from_db()
        self.assertEqual((item.status, item.verification_level), ('SUBMITTED', 'CONFIRMED'))
        services.review(self.officer, item.pk, item.version, 'accept', 'Synthetic mocked live-path review')
        item.refresh_from_db()
        self.assertEqual(item.verification_level, 'CONFIRMED')


@override_settings(ROOT_URLCONF='config.urls', BANK_CONTACTS=CONTACTS, BANK_CONFIRMATION_SIMULATED=True)
class SimulatedDeliveryTargets(PortalTestCase):
    """A running demo prints or catches simulated requests locally; it never sends them to an outside server."""

    def deliver(self, **email):
        item = self.submitted()
        item.ifsc = 'ABCD0123456'
        item.save()
        row = request_confirmation(self.officer, item.pk, item.version)
        with override_settings(**email):
            delivered = deliver_requests()
        row.refresh_from_db()
        return delivered, row

    def test_console_and_local_catcher_deliver(self):
        delivered, row = self.deliver(EMAIL_BACKEND='django.core.mail.backends.console.EmailBackend')
        self.assertEqual((delivered, row.status), (1, 'SENT'))

    def test_outside_smtp_server_is_refused(self):
        delivered, row = self.deliver(EMAIL_BACKEND='django.core.mail.backends.smtp.EmailBackend',
                                      EMAIL_HOST='smtp.example.org')
        self.assertEqual((delivered, row.status, row.last_error), (0, 'PENDING', 'DELIVERY_FAILED'))
