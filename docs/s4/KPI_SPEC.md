# S4 KPI definitions and pure snapshot calculations

Local demo calculation format `s4-kpi-snapshots-v1`, not an agreed API, audit-event
schema or production KPI contract. This covers the four KPI families in S4's
allocation and F7: turnaround, correction cycles, confirmed share and timely
renewal. All input/output is explicitly SIMULATED. No measured improvement,
regulatory correctness or bank authenticity is claimed.

## Explicit context and cohorts

`calculate_kpis` accepts typed tuples of `ProcessSnapshot` and `RenewalSnapshot`,
an explicit tuple of scoped institution IDs, aware `window_start`, `window_end`,
`as_of` timestamps and `simulation_label="SIMULATED"`. All arguments are required.
No model/queryset, actor, callback, file handle or database connection is accepted.
Empty tuples mean a deliberately known empty synthetic dataset. None, lazy data,
duplicate IDs/events, ambiguous sequencing and out-of-scope data fail with
`KpiInputError`, never an inferred zero or silent cross-tenant filter.
Successor self-links, reused successors, cycles and inconsistent institution
identities across supplied process/renewal/successor snapshots are rejected too.

Windows are inclusive UTC instants after normalization, start <= end <= as_of.
Durations are elapsed time, not working hours or officer handling time. Output
seconds are decimal strings rounded half-up to six places; median averages the
two middle durations for an even sample; p90 uses nearest rank `ceil(0.90*n)`.
Counts remain exact integers. Percentages use integer basis points of percent:
10,000 means 100.00%, rounded half-up. Zero denominators produce null, not 0%.

## Definitions

| Output | Cohort / calculation | Missing or incomplete data |
|---|---|---|
| `submission_to_acceptance` | Complete histories whose first ACCEPTED is inside the window; elapsed time from first SUBMITTED, including correction waits; median and p90 | Incomplete histories excluded and counted. Pending submissions are not zero-duration completions. First submission may precede window start |
| `declaration_to_confirmation` | Complete histories whose first INDEPENDENTLY_CONFIRMED is inside the window; elapsed since DECLARED; median and p90 | No declaration/confirmation means no sample. This is separate from administrative acceptance. Later discrepancy does not rewrite historical first-confirmation elapsed time |
| `correction_cycles` | Same accepted cohort as submission turnaround; count CHANGES_REQUESTED events before acceptance; total and mean per accepted record | Zero corrections in a complete accepted history is a real zero. No accepted samples produces null mean. Pending records are outside this completed-cohort metric |
| `confirmed_share` | Same accepted cohort, evaluated at as_of; numerator currently INDEPENDENTLY_CONFIRMED, denominator accepted sample count | No verification events = unknown. If any accepted record has unknown verification, overall percentage is null. `known_subset` reports its own numerator/denominator/percentage explicitly |
| `renewed_on_time` | Matured predecessor snapshots with explicit renewal eligibility=true and complete renewal history, maturity date inside the window's touched IST dates; accepted successor's IST date <= maturity date | Same-day maturity is still open and excluded until the following IST date. Unknown eligibility or incomplete relevant history makes overall percentage null; `known_subset` retains the observed eligible-cohort rate |

Confirmation states DECLARED/DISCREPANCY are known nonconfirmed states. Reconfirmation
after discrepancy changes the current confirmed share but not first-confirmation
turnaround. An accepted record without verification evidence never becomes
confirmed by default. Superseded/released accepted records remain in completed
process cohorts; these metrics are not the active monitoring register.

Renewal denominators include **all known eligible matured predecessors**, including
those with no accepted successor or a late successor, not just successful renewals.
`RenewalSnapshot.successor` is either an explicit `AcceptedSuccessor` value or None;
a draft/submitted successor cannot be converted to this type by the future adapter.
None with complete history means no known accepted successor as of the cutoff.
Future acceptance timestamps cannot qualify. No renewal eligibility is inferred
from maturity, profile type, release state, amount, or a missing predecessor.

Renewal exclusion counts are mutually exclusive in this order: outside date window,
not yet matured, eligibility unknown, explicitly not required, incomplete history.
They are not additive counts of every reason that might apply. The observed
denominator is retained even if unknown candidates make the overall rate null.
Do not present `known_subset` as the full-cohort success rate.

`data_quality` reports supplied process/renewal snapshot counts, incomplete process
histories, ignored future events and open submissions (first submitted in the
window, no acceptance by as_of). Histories omitted by the caller cannot be counted;
sample sizes/completeness are not proof that an adapter supplied every record.

## Snapshot event semantics

`KpiEvent(id, sequence, action, at)` has a positive globally unique event ID,
positive per-instrument sequence, known action and aware timestamp (microseconds
allowed). Input tuple order is irrelevant; sequence determines order and must not
reverse time. Equal timestamps need distinct sequences. Future events are ignored
for metrics and counted; their types, identity and temporal order still validate.

The local vocabulary is deliberately limited to SUBMITTED, CHANGES_REQUESTED,
ACCEPTED, DECLARED, INDEPENDENTLY_CONFIRMED and DISCREPANCY. A future adapter must
explicitly select/map relevant events; it must not relabel unrelated audit events.
The current app has the first three actions, not a confirmation integration.

For complete histories, review transitions are first submission -> corrections ->
resubmission (repeat as needed) -> acceptance. No second acceptance or correction
after acceptance is allowed. Verification starts with one declaration, then may
move between confirmed/discrepancy (no duplicate state event). Verification can
occur independently of administrative review; this is not a new business workflow.
Incomplete histories still validate types/identities/order, but state-machine
checks and metrics skip them rather than fabricating missing starts.

## Current source versus future integration

- Existing `AuditEvent` has an instrument, action and `created_at`; S4 does not
  modify or read it. Its eventual mapping needs complete ordered snapshots.
- Y1/Y6 must provide confirmation semantics and trustworthy histories. No bank
  statement matching or verification service is implemented here.
- Y3/S2 must supply a scoped, complete population, original maturity dates,
  accepted successor lineage, explicit eligibility and cutoff-correct snapshots.
  An API adapter must never use today's verification state for a past cutoff.
- K1 owns endpoint authorization and the agreed wire contract. The scope guard
  here checks fixture consistency; it is not real user authentication.

F7's discrepancy rate, intervention-age buckets, known-obligation coverage share,
notification/manual-follow-up counts and officer time are **defined backlog**,
not additional metrics implemented here. They need agreed discrepancy identities,
open/closed task snapshots, obligation applicability and delivery/work timestamps.
Never estimate them from these process durations or claim missing notifications
were sent. No before/after baseline or saved effort is measured in this slice.

## Acceptance

1. Labeled synthetic scenarios cover empty, mixed, pending/incomplete, unknown,
   discrepancy/reconfirmation, same-day IST renewal, future events and boundaries.
2. Independently written expected samples, denominators, median/p90, correction
   totals and rates match; zero and unavailable remain distinct.
3. Out-of-scope IDs, duplicates, malformed types, naive timestamps, reversed
   windows/order, invalid transitions and cross-institution successor links fail.
4. Inputs remain unchanged and outputs detached; equivalent UTC/IST instants and
   permuted snapshot/event input order produce the same results.
5. No DB query/write, Django setup, external call or frontend is used. Existing
   CSV slice, S1–S3, frozen S2 dataset and full regression suite still pass.
