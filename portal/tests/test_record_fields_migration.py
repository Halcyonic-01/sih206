from datetime import date

from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase


class RecordFieldsMigrationTests(TransactionTestCase):
    def test_upgrade_preserves_legacy_records_documents_lineage_and_audit(self):
        executor = MigrationExecutor(connection)
        latest = executor.loader.graph.leaf_nodes()
        self.addCleanup(lambda: MigrationExecutor(connection).migrate(latest))
        old_target = [('portal', '0004_release_workflow'), ('obligations', '0001_initial')]
        executor.migrate(old_target)
        old = executor.loader.project_state(old_target).apps
        user = old.get_model('auth', 'User').objects.create(username='synthetic-y1-migration')
        institution = old.get_model('portal', 'Institution').objects.create(code='Y1-MIG', name='Synthetic')
        Instrument = old.get_model('portal', 'Instrument')
        common = dict(institution_id=institution.pk, created_by_id=user.pk, bank='Synthetic bank',
                      amount_paise=50000025, issue_date=date(2026, 1, 1), maturity_date=date(2027, 1, 1))
        parent = Instrument.objects.create(reference='SYNTHETIC-PARENT', status='ACCEPTED', **common)
        child = Instrument.objects.create(reference='SYNTHETIC-CHILD', predecessor_id=parent.pk, **common)
        old.get_model('portal', 'Document').objects.create(instrument_id=parent.pk, kind='FDR',
            file='synthetic/unchanged.pdf', original_name='synthetic.pdf', size_bytes=100,
            sha256='1' * 64, uploaded_by_id=user.pk)
        old.get_model('portal', 'AuditEvent').objects.create(instrument_id=parent.pk,
            actor_id=user.pk, action='ACCEPTED', before={}, after={'status': 'ACCEPTED'})
        tables = ['Instrument', 'Document', 'AuditEvent']
        before = {name: list(old.get_model('portal', name).objects.order_by('pk').values()) for name in tables}
        MigrationExecutor(connection).migrate(latest)
        new = MigrationExecutor(connection).loader.project_state(latest).apps
        for name in tables:
            columns = list(before[name][0])
            self.assertEqual(list(new.get_model('portal', name).objects.order_by('pk').values(*columns)),
                             before[name])
        instruments = new.get_model('portal', 'Instrument')
        self.assertEqual(instruments.objects.get(pk=child.pk).predecessor_id, parent.pk)
        for item in instruments.objects.all():
            self.assertIsNone(item.obligation_id)
            self.assertIsNone(item.lien_marked)
            self.assertEqual(item.mode, 'FDR')
            self.assertEqual(item.verification_level, 'DECLARED')
        self.assertIsNone(new.get_model('portal', 'Document').objects.get().page_count)
        self.assertEqual(new.get_model('obligations', 'DepositObligation').objects.count(), 0)
