"""Synthetic prerequisite checks only; Django SimpleTestCase forbids DB access."""
from copy import deepcopy
from datetime import date, datetime
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from unittest.mock import patch

from django.test import SimpleTestCase

from evaluation.s5.run import DATASET, context, evaluate, merge
from obligations.release_prerequisites import PrerequisiteInputError, evaluate_prerequisites

LABELS_SHA256 = '3946a123b0caf345c6c82346b152b1f9de2810be29ab291092c20a9e2ab2927b'


class PrerequisiteTests(SimpleTestCase):
    def setUp(self):
        self.dataset = json.loads(DATASET.read_text(encoding='utf-8'))
        self.rule, self.when = context(self.dataset)

    def run_check(self, changes=None, operation='ASSESS', **kwargs):
        values = dict(operation=operation, rules=self.rule, as_of=self.when, simulation_label='SIMULATED') | kwargs
        return evaluate_prerequisites(merge(self.dataset['defaults'], changes or {}), **values)

    def scenario(self, identifier):
        return next(s for s in self.dataset['scenarios'] if s['id'] == identifier)

    def test_all_forty_original_expected_labels_and_invariants_match_without_queries(self):
        raw = DATASET.read_bytes()
        result = evaluate()
        self.assertEqual((result['case_count'], result['passed'], result['failed']), (40,40,0), result)
        self.assertEqual(result['labels_sha256'], LABELS_SHA256)
        self.assertEqual(DATASET.read_bytes(), raw)
        for row in result['cases']:
            self.assertFalse(row['actual']['effects_applied'])
            self.assertFalse(row['actual']['automatic_approval'])
            self.assertFalse(row['actual']['bank_verified'])

    def test_evaluator_detects_missing_gate_without_changing_labels(self):
        original = evaluate_prerequisites
        def broken(*args, **kwargs):
            result = original(*args, **kwargs)
            if result['reason_codes'] == ['CLEARANCE_OPEN']:
                result['outcome'], result['reason_codes'] = 'READY_FOR_AUTHORITY_REVIEW', []
            return result
        with patch('evaluation.s5.run.evaluate_prerequisites', side_effect=broken):
            result = evaluate()
        self.assertEqual([r['id'] for r in result['cases'] if not r['passed']], ['S5-17'])
        self.assertEqual(result['labels_sha256'], LABELS_SHA256)

    def test_projection_and_input_are_detached_and_no_action_is_applied(self):
        item = self.scenario('S5-34')
        snapshot = merge(self.dataset['defaults'], item['input_patch'])
        before = deepcopy(snapshot)
        first = evaluate_prerequisites(snapshot, operation=item['operation'], rules=self.rule,
            as_of=self.when, simulation_label='SIMULATED')
        self.assertEqual(snapshot, before)
        self.assertEqual(snapshot['case']['status'], 'APPROVED')
        self.assertTrue(snapshot['monitoring_active'])
        self.assertEqual(first['case_status_after_action'], 'COMPLETED')
        self.assertFalse(first['monitoring_after_action'])
        self.assertFalse(first['effects_applied'])
        first['reason_codes'].append('CHANGED')
        second = evaluate_prerequisites(snapshot, operation=item['operation'], rules=self.rule,
            as_of=self.when, simulation_label='SIMULATED')
        self.assertEqual(second['reason_codes'], [])

    def test_approval_never_projects_issued_letter_or_completed_monitoring(self):
        result = self.run_check(operation='APPROVE')
        self.assertEqual(result['case_status_after_action'], 'APPROVED')
        self.assertTrue(result['monitoring_after_action'])
        self.assertNotIn('issued_letter', result)
        self.assertFalse(result['software_moves_money'])

    def test_success_and_findings_carry_explicit_rule_context(self):
        ready = self.run_check()
        self.assertEqual(ready['assessment_context']['rule_sha256'], self.rule.sha256)
        self.assertEqual(ready['assessment_context']['as_of'], self.when.isoformat())
        failed = self.run_check({'clearances':{'GRANTS':{'status':'HOLD'}}})
        finding = failed['findings'][0]
        self.assertEqual(finding['code'], 'CLEARANCE_HOLD')
        self.assertEqual(finding['field'], 'clearances.GRANTS')
        self.assertEqual(finding['rule_sha256'], self.rule.sha256)
        self.assertEqual(finding['source_clause'], '6.46')

    def test_scope_denial_is_generic_and_does_not_echo_foreign_evidence(self):
        for changes in [
            {'actor':{'scope_institution_ids':[102]}},
            {'documents':{'FDR':{'institution_id':999,'ref':'PRIVATE-FOREIGN-DOC'}}},
            {'instrument':{'institution_id':102}},
            {'basis':{'child_institution_ids':[999]}}]:
            result = self.run_check(changes)
            self.assertEqual(result['outcome'], 'DENIED')
            self.assertEqual(result['findings'], [])
            rendered = json.dumps(result)
            self.assertNotIn('PRIVATE-FOREIGN-DOC', rendered)
            self.assertNotIn(self.rule.sha256, rendered)

    def test_request_requires_institution_requester_but_not_completed_clearances(self):
        self.assertEqual(self.run_check(operation='REQUEST')['outcome'], 'DENIED')
        changes = {'actor':{'id':1001,'role_label':'INSTITUTION','scope_institution_ids':[101]},
                   'clearance_context_complete':False,'penalty_review':{'status':'UNAVAILABLE','assessments':None}}
        result = self.run_check(changes, operation='REQUEST')
        self.assertEqual(result['outcome'], 'REQUEST_PREREQUISITES_MET_IN_DEMO')
        self.assertTrue(result['monitoring_after_action'])

    def test_wrong_role_requester_and_clearance_decider_cannot_decide(self):
        for actor in [{'role_label':'OFFICER'}, {'role_label':'INSTITUTION'}, {'role_label':'UNKNOWN'},
                      {'id':1001}, {'id':2002}]:
            with self.subTest(actor=actor):
                self.assertEqual(self.run_check({'actor':actor}, operation='APPROVE')['outcome'], 'DENIED')

    def test_stale_version_and_stale_assessment_are_distinct(self):
        first = self.run_check({'case':{'version':4}})
        second = self.run_check({'case':{'version':4,'expected_version':4}})
        self.assertEqual(first['reason_codes'], ['STALE_VERSION'])
        self.assertEqual(second['reason_codes'], ['STALE_ASSESSMENT'])
        self.assertNotIn('case_status_after_action', first)

    def test_replayed_decision_completion_and_issuance_fail(self):
        for operation, changes in [
            ('APPROVE',{'case':{'status':'APPROVED'}}),
            ('COMPLETE',{'case':{'status':'COMPLETED'},'instrument':{'released':True},'monitoring_active':False}),
            ('ISSUE_LETTER',{'case':{'status':'APPROVED'},'letter':{'state':'ISSUED','kind':'NOC','ref':'SYNTH-ISSUED'}})]:
            result = self.run_check(changes, operation=operation)
            self.assertEqual(result['outcome'], 'CONFLICT')
            self.assertFalse(result['effects_applied'])

    def test_noncurrent_unknown_and_monitoring_inconsistent_snapshots_fail_closed(self):
        for field in ['released','superseded']:
            self.assertEqual(self.run_check({'instrument':{field:True}})['outcome'], 'CONFLICT')
            self.assertEqual(self.run_check({'instrument':{field:None}})['outcome'], 'CONTEXT_UNAVAILABLE')
        self.assertNotEqual(self.run_check({'monitoring_active':False})['outcome'], 'READY_FOR_AUTHORITY_REVIEW')

    def test_unknown_competing_state_is_not_a_known_conflict_or_no_conflict(self):
        for changes in [{'case':{'other_active_release':None}}, {'instrument':{'successor_proposal_exists':None}}]:
            self.assertEqual(self.run_check(changes)['outcome'], 'CONTEXT_UNAVAILABLE')

    def test_null_missing_unreviewed_and_unusable_documents_never_satisfy_gate(self):
        for changes in [{'document_context_complete':False}, {'documents':{'AFFIDAVIT_6':None}},
                {'documents':{'FDR':{'parse_status':'UNREADABLE'}}},
                {'documents':{'FDR':{'parse_status':'ACTIVE_CONTENT'}}},
                {'documents':{'FDR':{'parse_status':'INVALID_PAGE'}}},
                {'documents':{'FDR':{'review_status':None}}}]:
            result = self.run_check(changes)
            self.assertIn(result['outcome'], ['BLOCKED','CONTEXT_UNAVAILABLE'])
            self.assertTrue(result['reason_codes'])

    def test_required_clearance_set_cannot_be_shrunk_and_extra_units_must_clear(self):
        self.assertEqual(self.run_check({'required_units':[]})['reason_codes'], ['CLEARANCE_SCOPE_UNKNOWN'])
        for changes in [{'clearances':{'GRANTS':None}}, {'clearances':{'GRANTS':{'reason':''}}},
                {'required_units':['PGRC','VIGILANCE','GRANTS','OTHER_BUREAU']}]:
            self.assertEqual(self.run_check(changes)['outcome'], 'CONTEXT_UNAVAILABLE')

    def test_all_unmet_prerequisites_are_reported_with_unknown_priority(self):
        result = self.run_check({'clearances':{'GRANTS':{'status':'OPEN'}},
            'holds':{'trustee_dispute':True},'penalty_review':{'status':'UNAVAILABLE','assessments':None}})
        self.assertEqual(result['outcome'], 'CONTEXT_UNAVAILABLE')
        self.assertEqual(set(result['reason_codes']), {'CLEARANCE_OPEN','DISPUTE_HOLD','PENALTY_REVIEW_UNAVAILABLE'})
        self.assertEqual({f['code'] for f in result['findings']}, set(result['reason_codes']))

    def test_term_end_boundary_and_maturity_exception_are_not_inferred(self):
        result = self.run_check({'obligation':{'term_end':self.when.isoformat()}})
        self.assertEqual(result['outcome'], 'CONTEXT_UNAVAILABLE')
        self.assertEqual(result['reason_codes'], ['TERM_END_BOUNDARY_UNRESOLVED'])
        case = self.scenario('S5-06')
        changes = merge(case['input_patch'], {'basis':{'certificate_exception_reviewed':False}})
        self.assertEqual(self.run_check(changes)['reason_codes'], ['NO_STUDENTS_CERTIFICATE_REQUIRED'])

    def test_empty_merger_children_and_incomplete_declarations_remain_unavailable(self):
        self.assertIn('CHILD_SCOPE_UNKNOWN', self.run_check({'case':{'path':'MERGER'},
            'basis':{'merger_order_ref':'SYNTH-MERGER'}})['reason_codes'])
        for changes in [{'affidavit_review':{'all_required_answers_recorded':None}},
                        {'affidavit_review':{'reviewed':False}}]:
            self.assertEqual(self.run_check(changes)['outcome'], 'CONTEXT_UNAVAILABLE')

    def test_penalty_arithmetic_disposition_and_waiver_authority_do_not_default(self):
        changes = self.scenario('S5-14')['input_patch']
        for values, code in [({'amount_paise':1},'PENALTY_ARITHMETIC_MISMATCH'),
                             ({'actor_id':None},'PENALTY_DISPOSITION_PENDING'),
                             ({'reason':''},'PENALTY_DISPOSITION_PENDING'),
                             ({'status':'WAIVED'},'WAIVER_AUTHORITY_UNESTABLISHED')]:
            candidate = deepcopy(changes)
            candidate['penalty_review']['assessments'][0].update(values)
            self.assertIn(code, self.run_check(candidate)['reason_codes'])
        candidate = deepcopy(changes)
        candidate['penalty_review']['status'] = 'COMPLETE_NO_PENALTY'
        self.assertIn('PENALTY_CONTEXT_INCONSISTENT', self.run_check(candidate)['reason_codes'])

    def test_penalty_findings_use_the_actual_draft_penalty_clause(self):
        result = self.run_check(self.scenario('S5-13')['input_patch'])
        self.assertEqual(result['findings'][0]['source_clause'], '2.21(h)')

    def test_new_completion_evidence_cannot_reuse_existing_document_or_letter(self):
        changes = self.scenario('S5-34')['input_patch']
        for ref in ['SYNTH-DOC-FDR','SYNTH-LETTER-NOC']:
            candidate = merge(changes, {'completion':{'new_evidence_ref':ref,'evidence_is_new':True}})
            self.assertIn('NEW_COMPLETION_EVIDENCE_REQUIRED', self.run_check(candidate,operation='COMPLETE')['reason_codes'])
        candidate = merge(changes, {'completion':{'parse_status':'UNREADABLE'}})
        self.assertIn('DOCUMENT_UNUSABLE', self.run_check(candidate,operation='COMPLETE')['reason_codes'])

    def test_letter_kind_revocation_and_missing_notes_block_completion(self):
        changes = self.scenario('S5-34')['input_patch']
        for patch_values in [{'letter':{'kind':'SANCTION_ORDER'}}, {'letter':{'state':'REVOKED'}},
                             {'completion':{'notes':''}}]:
            result = self.run_check(merge(changes,patch_values),operation='COMPLETE')
            self.assertEqual(result['outcome'], 'BLOCKED')
            self.assertTrue(result['monitoring_after_action'])

    def test_public_classification_returns_no_case_or_document_payload(self):
        for state, expected in [('NOT_ISSUED','PUBLIC_NOT_FOUND'), ('REVOKED','PUBLIC_REVOKED_RECORD_ONLY')]:
            result = self.run_check({'letter':{'state':state,'ref':'SYNTH-LETTER','kind':'NOC'}},operation='PUBLIC_VERIFY')
            self.assertEqual(result['outcome'], expected)
            for field in ['documents','actor','case','completion','public_url','issued_letter']:
                self.assertNotIn(field,result)
            self.assertNotIn('SYNTH-DOC-FDR',json.dumps(result))
        result = self.run_check({'letter':{'state':'ISSUED','ref':'SYNTH-LETTER','kind':None}},operation='PUBLIC_VERIFY')
        self.assertNotEqual(result['outcome'],'PUBLIC_ISSUED_RECORD_ONLY')

    def test_materialized_types_missing_fields_and_bad_scalars_raise_controlled_errors(self):
        snapshot = deepcopy(self.dataset['defaults'])
        for field, value in [('version',True),('expected_version',1.5),('mode',[]),('path',{}),('id',0)]:
            with self.subTest(field=field), self.assertRaises(PrerequisiteInputError):
                self.run_check({'case':{field:value}})
        del snapshot['holds']
        with self.assertRaises(PrerequisiteInputError):
            evaluate_prerequisites(snapshot,operation='ASSESS',rules=self.rule,as_of=self.when,simulation_label='SIMULATED')
        for changes in [{'instrument':{'maturity_date':'bad-date'}}, {'holds':{'trustee_dispute':'false'}},
                {'required_units':['GRANTS','GRANTS']}, {'basis':{'child_certificates':{'9'*5000:'bad'}}}]:
            with self.subTest(changes=changes), self.assertRaises(PrerequisiteInputError):
                self.run_check(changes)
        for value in [None, [], iter([])]:
            with self.assertRaises(PrerequisiteInputError):
                evaluate_prerequisites(value,operation='ASSESS',rules=self.rule,as_of=self.when,simulation_label='SIMULATED')

    def test_operation_policy_date_and_rule_selection_are_explicit(self):
        for values in [dict(operation='PAY'),dict(simulation_label='REAL'),dict(rules=None),
                       dict(as_of=datetime(2026,10,24)),dict(as_of=date(2027,1,1))]:
            with self.subTest(values=values), self.assertRaises(PrerequisiteInputError):
                self.run_check(**values)

    def test_no_hardcoded_fixture_ids_and_standalone_without_django(self):
        changes = {'instrument':{'id':9999},'case':{'id':9998,'instrument_id':9999}}
        changes['documents'] = {k:dict(v,instrument_id=9999) for k,v in self.dataset['defaults']['documents'].items()}
        self.assertEqual(self.run_check(changes)['outcome'],'READY_FOR_AUTHORITY_REVIEW')
        env=os.environ.copy(); env.pop('DJANGO_SETTINGS_MODULE',None)
        script="import sys; from evaluation.s5.run import evaluate; assert evaluate()['failed']==0; assert 'django' not in sys.modules; print('pure S5 pass')"
        result=subprocess.run([sys.executable,'-c',script],cwd=Path(__file__).resolve().parents[2],
            env=env,capture_output=True,text=True,timeout=15)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(result.stdout.strip(),'pure S5 pass')
