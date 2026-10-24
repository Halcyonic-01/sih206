"""Pure synthetic KPI preparation; database access forbidden by SimpleTestCase."""
from copy import deepcopy
from dataclasses import FrozenInstanceError, replace
from datetime import date, datetime, timedelta, timezone
import json
import math
import os
from pathlib import Path
import statistics
import subprocess
import sys
from unittest.mock import patch
from zoneinfo import ZoneInfo

from django.test import SimpleTestCase

from evaluation.s4.kpis.run import DATASET, evaluate, inputs
from obligations.kpis import (AcceptedSuccessor, KpiEvent, KpiInputError,
    ProcessSnapshot, RenewalSnapshot, calculate_kpis)

START = datetime(2026, 4, 1, tzinfo=timezone.utc)
END = datetime(2026, 4, 30, 23, 59, 59, tzinfo=timezone.utc)
AS_OF = datetime(2026, 5, 1, tzinfo=timezone.utc)


def event(identity, sequence, action, seconds=0):
    return KpiEvent(identity, sequence, action, START + timedelta(seconds=seconds))


def process(identity=1, **changes):
    return replace(ProcessSnapshot(identity, 1, True, (
        event(identity * 10, 1, 'SUBMITTED'), event(identity * 10 + 1, 2, 'ACCEPTED', 60))), **changes)


def renewal(identity=1, **changes):
    return replace(RenewalSnapshot(identity, 1, date(2026, 4, 10), True, True), **changes)


def calculate(**changes):
    return calculate_kpis(**(dict(processes=(), renewals=(), scope_institution_ids=(1,),
        window_start=START, window_end=END, as_of=AS_OF, simulation_label='SIMULATED') | changes))


class KpiTests(SimpleTestCase):
    def test_all_ten_literal_labelled_scenarios_without_queries_or_label_changes(self):
        before = DATASET.read_bytes()
        result = evaluate()
        self.assertEqual((result['case_count'], result['passed'], result['failed']), (10, 10, 0), result)
        self.assertEqual(result['review_status'], 'AUTHOR_LABELLED_NOT_INDEPENDENTLY_ADJUDICATED')
        self.assertEqual(DATASET.read_bytes(), before)

    def test_evaluator_detects_false_confirmed_share(self):
        original = calculate_kpis
        def broken(**kwargs):
            result = original(**kwargs)
            result['confirmed_share']['numerator'] = 999
            return result
        with patch('evaluation.s4.kpis.run.calculate_kpis', side_effect=broken):
            self.assertGreater(evaluate()['failed'], 0)

    def test_empty_and_all_incomplete_histories_are_not_zero_duration_success(self):
        for records in [(), (process(history_complete=False),)]:
            result = calculate(processes=records)
            self.assertEqual(result['submission_to_acceptance'], {
                'sample_count':0, 'median_seconds':None, 'p90_seconds':None})
            self.assertIsNone(result['correction_cycles']['mean_per_accepted_record'])
            self.assertIsNone(result['confirmed_share']['percentage_bps'])

    def test_generated_distributions_match_independent_statistics_and_nearest_rank(self):
        for count in range(1, 21):
            durations = [(i * 37) % 101 for i in range(count)]
            records = tuple(process(i + 1, events=(event(i * 10 + 1, 1, 'SUBMITTED'),
                event(i * 10 + 2, 2, 'ACCEPTED', seconds))) for i, seconds in enumerate(durations))
            actual = calculate(processes=records)['submission_to_acceptance']
            self.assertEqual(actual['sample_count'], count)
            self.assertEqual(actual['median_seconds'], f'{statistics.median(durations):.6f}')
            self.assertEqual(actual['p90_seconds'], f'{sorted(durations)[math.ceil(.9 * count) - 1]:.6f}')

    def test_resubmission_does_not_reset_turnaround_start(self):
        record = process(events=(event(1,1,'SUBMITTED'), event(2,2,'CHANGES_REQUESTED',60),
            event(3,3,'SUBMITTED',120), event(4,4,'ACCEPTED',180)))
        result = calculate(processes=(record,))
        self.assertEqual(result['submission_to_acceptance']['median_seconds'], '180.000000')
        self.assertEqual(result['correction_cycles'], {'sample_count':1, 'total':1, 'mean_per_accepted_record':'1.00'})

    def test_submission_before_window_counts_if_completion_is_inside(self):
        record = process(events=(event(1,1,'SUBMITTED',-3600), event(2,2,'ACCEPTED',0)))
        self.assertEqual(calculate(processes=(record,))['submission_to_acceptance']['median_seconds'], '3600.000000')

    def test_pending_and_future_confirmation_do_not_create_zero_samples_or_confirmation(self):
        record = process(events=(event(1,1,'DECLARED'), event(2,2,'SUBMITTED'), event(3,3,'ACCEPTED',60),
            KpiEvent(4,4,'INDEPENDENTLY_CONFIRMED', AS_OF + timedelta(seconds=1))))
        result = calculate(processes=(record,))
        self.assertEqual(result['declaration_to_confirmation']['sample_count'], 0)
        self.assertEqual(result['confirmed_share']['percentage_bps'], 0)
        self.assertEqual(result['data_quality']['ignored_future_events'], 1)
        pending = calculate(processes=(process(events=(event(5,1,'SUBMITTED'),)),))
        self.assertEqual(pending['data_quality']['open_submissions'], 1)
        self.assertEqual(pending['submission_to_acceptance']['sample_count'], 0)

    def test_unknown_confirmation_is_not_counted_as_a_known_failure(self):
        result = calculate(processes=(process(),))['confirmed_share']
        self.assertEqual(result['denominator'], 1)
        self.assertEqual(result['unknown_count'], 1)
        self.assertIsNone(result['percentage_bps'])
        self.assertEqual(result['known_subset']['denominator'], 0)

    def test_renewal_includes_failed_eligible_predecessors_and_uses_ist(self):
        rows = (renewal(successor=AcceptedSuccessor(11,1,datetime(2026,4,10,18,29,59,tzinfo=timezone.utc))),
                renewal(2, successor=AcceptedSuccessor(12,1,datetime(2026,4,10,18,30,tzinfo=timezone.utc))),
                renewal(3))
        result = calculate(renewals=rows)['renewed_on_time']
        self.assertEqual((result['numerator'], result['denominator'], result['percentage_bps']), (1,3,3333))

    def test_future_successor_cannot_qualify_as_on_time(self):
        row = renewal(successor=AcceptedSuccessor(2,1,AS_OF + timedelta(seconds=1)))
        result = calculate(renewals=(row,))['renewed_on_time']
        self.assertEqual((result['numerator'], result['denominator'], result['percentage_bps']), (0,1,0))

    def test_unknown_renewal_context_makes_overall_rate_unavailable(self):
        for unknown in [renewal(2, eligible=None), renewal(2, history_complete=False)]:
            result = calculate(renewals=(renewal(), unknown))['renewed_on_time']
            self.assertIsNone(result['percentage_bps'])
            self.assertEqual(result['known_subset'], {'numerator':0,'denominator':1,'percentage_bps':0})

    def test_equivalent_instants_and_permuted_input_order_preserve_results(self):
        source = json.loads(DATASET.read_text(encoding='utf-8'))
        values = inputs(source['cases'][1], source['context'])
        baseline = calculate_kpis(**values)
        values['processes'] = tuple(replace(row, events=tuple(replace(e, at=e.at.astimezone(ZoneInfo('Asia/Kolkata')))
            for e in reversed(row.events))) for row in reversed(values['processes']))
        for key in ['window_start', 'window_end', 'as_of']:
            values[key] = values[key].astimezone(ZoneInfo('Asia/Kolkata'))
        self.assertEqual(calculate_kpis(**values), baseline)

    def test_inputs_are_frozen_and_results_detached(self):
        records = (process(),)
        before = deepcopy(records)
        first, second = calculate(processes=records), calculate(processes=records)
        first['confirmed_share']['known_subset']['denominator'] = 99
        self.assertEqual(calculate(processes=records), second)
        self.assertEqual(records, before)
        with self.assertRaises(FrozenInstanceError):
            records[0].history_complete = False

    def test_scope_missing_lazy_or_malformed_snapshot_context_fails_closed(self):
        class Lazy:
            def __iter__(self):
                raise AssertionError('Must not iterate lazy context')
        for patch_values in [dict(processes=None), dict(processes=Lazy()), dict(renewals=[]),
                dict(scope_institution_ids=None), dict(scope_institution_ids=(True,)),
                dict(scope_institution_ids=(1,1)), dict(processes=({},)),
                dict(processes=(process(institution_id=2),)), dict(renewals=(renewal(institution_id=2),)),
                dict(simulation_label='REAL'), dict(simulation_label=[]),
                dict(processes=(process(history_complete='true'),))]:
            with self.subTest(values=patch_values), self.assertRaises(KpiInputError):
                calculate(**patch_values)

    def test_duplicate_instruments_events_sequences_and_unknown_actions_rejected(self):
        for records in [(process(), process()),
                (process(), process(2, events=process().events)),
                (process(events=(event(1,1,'SUBMITTED'),event(2,1,'ACCEPTED',60))),),
                (process(events=(event(1,1,'OTHER'),)),),
                (process(events=(replace(event(1,1,'SUBMITTED'),action=[]),)),)]:
            with self.subTest(records=records), self.assertRaises(KpiInputError):
                calculate(processes=records)

    def test_complete_invalid_transitions_fail_instead_of_inventing_starts(self):
        for actions in [('ACCEPTED',), ('CHANGES_REQUESTED',), ('INDEPENDENTLY_CONFIRMED',),
                ('DECLARED','DECLARED'), ('SUBMITTED','SUBMITTED'),
                ('SUBMITTED','ACCEPTED','CHANGES_REQUESTED'),
                ('DECLARED','INDEPENDENTLY_CONFIRMED','INDEPENDENTLY_CONFIRMED')]:
            events = tuple(event(i+1,i+1,action,i) for i, action in enumerate(actions))
            with self.subTest(actions=actions), self.assertRaises(KpiInputError):
                calculate(processes=(process(events=events),))

    def test_naive_timestamps_reversed_windows_and_sequence_time_reversal_fail(self):
        for patch_values in [dict(as_of=AS_OF.replace(tzinfo=None)), dict(as_of='2026-05-01'),
                dict(window_start=AS_OF), dict(window_end=AS_OF + timedelta(seconds=1)),
                dict(processes=(process(events=(event(1,1,'SUBMITTED',60),event(2,2,'ACCEPTED',0))),)),
                dict(processes=(process(events=(replace(event(1,1,'SUBMITTED'),at=START.replace(tzinfo=None)),)),))]:
            with self.subTest(values=patch_values), self.assertRaises(KpiInputError):
                calculate(**patch_values)

    def test_duplicate_self_reused_cross_institution_and_cyclic_successors_fail(self):
        for rows in [(renewal(),renewal()),
                (renewal(successor=AcceptedSuccessor(1,1,START)),),
                (renewal(successor=AcceptedSuccessor(2,2,START)),),
                (renewal(successor=AcceptedSuccessor(3,1,START)),renewal(2,successor=AcceptedSuccessor(3,1,START))),
                (renewal(successor=AcceptedSuccessor(2,1,START)),renewal(2,successor=AcceptedSuccessor(1,1,START)))]:
            with self.subTest(rows=rows), self.assertRaises(KpiInputError):
                calculate(renewals=rows)

    def test_inconsistent_institution_across_renewal_and_successor_snapshots_fails(self):
        rows = (renewal(successor=AcceptedSuccessor(2,1,START)), renewal(2,institution_id=2))
        with self.assertRaises(KpiInputError):
            calculate(renewals=rows, scope_institution_ids=(1,2))

    def test_renewal_context_and_ids_reject_booleans_and_bad_dates(self):
        for row in [renewal(instrument_id=True), renewal(eligible=1), renewal(history_complete=0),
                renewal(maturity_date=START), renewal(maturity_date='2026-04-10'),
                renewal(successor={}), renewal(successor=AcceptedSuccessor(2,True,START))]:
            with self.subTest(row=row), self.assertRaises(KpiInputError):
                calculate(renewals=(row,))

    def test_calendar_extremes_are_controlled_and_long_elapsed_time_is_exact(self):
        first = datetime(1900,1,1,tzinfo=timezone.utc)
        record = process(events=(KpiEvent(1,1,'SUBMITTED',first), KpiEvent(2,2,'ACCEPTED',START)))
        result = calculate(processes=(record,))
        self.assertEqual(result['submission_to_acceptance']['median_seconds'], f'{(START-first).days*86400}.000000')
        with self.assertRaises(KpiInputError):
            calculate(window_end=datetime.max.replace(tzinfo=timezone.utc), as_of=datetime.max.replace(tzinfo=timezone.utc))

    def test_standalone_stdlib_only_no_django_or_database_import(self):
        env = os.environ.copy()
        env.pop('DJANGO_SETTINGS_MODULE', None)
        script = ("import sys; from evaluation.s4.kpis.run import evaluate; r=evaluate(); "
                  "assert r['failed']==0; assert 'django' not in sys.modules; print('pure KPI pass')")
        result = subprocess.run([sys.executable,'-c',script],env=env,
            cwd=Path(__file__).resolve().parents[2],capture_output=True,text=True,timeout=15)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(result.stdout.strip(),'pure KPI pass')
