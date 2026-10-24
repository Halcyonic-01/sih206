"""Draft demo configuration. Not an approved or automatically active policy."""
SOURCE = 'https://cdnbbsr.s3waas.gov.in/s35938b4d054136e5d59ada6ec9c295d7a/uploads/2025/03/2025031399.pdf'
LAKH_PAISE = 10_000_000

# Amounts transcribed from APH Table 1.4, printed page 10. Null means unsupported,
# never a zero deposit. The complete draft is returned as a fresh object.
_AMOUNTS_LAKH = {
    'ENGINEERING_TECHNOLOGY': [15, 35, 15],
    'PLANNING': [15, 15, 15],
    'APPLIED_ARTS_CRAFTS': [15, 15, 15],
    'DESIGN': [15, 15, 15],
    'HMCT': [15, 15, 15],
    'COMPUTER_APPLICATIONS': [None, 5, 15],
    'MANAGEMENT': [None, 5, 15],
}
LEVELS = ('DIPLOMA', 'UG', 'PG')
PATHS = ('TERM_COMPLETE', 'PROGRESSIVE_CLOSURE', 'MERGER',
         'CONVERSION_TO_UNIVERSITY', 'CLOSURE_BY_AICTE')


def draft_payload():
    return {
        'schema_version': 1,
        'label': 'DRAFT_DEMO_NOT_APPROVED',
        'amounts': {programme: dict(zip(LEVELS, [
            None if amount is None else amount * LAKH_PAISE for amount in amounts]))
            for programme, amounts in _AMOUNTS_LAKH.items()},
        'leased_multiplier': 2,
        'term_years': 10,
        'proof_days': 15,
        'penalties_bps': {'late_proof_may': 1000, 'late_proof_july': 2000,
                          'premature_encashment': 1000, 'closure_lapsed': 1000,
                          'closure_six_years': 5000},
        'clauses': {'amount': 'Table 1.4; 1.12', 'term': '1.12(iv); 2.25(g)',
                    'proof': '2.25(f)', 'late_proof': '2.25(f)',
                    'premature_encashment': '7.7', 'closure_lapsed': '2.21(h)',
                    'closure_six_years': '2.21(i)', 'release': '6.46'},
        'release': {
            'paths': list(PATHS),
            'common_documents': ['REQUEST_LETTER', 'AFFIDAVIT_6', 'LATEST_LOA_EOA'],
            'mode_documents': {'FDR': 'FDR', 'RTGS': 'PAYMENT_PROOF', 'RPGF': 'RPGF_PROOF'},
            'clearance_units': ['PGRC', 'VIGILANCE', 'GRANTS'],
            'conditional_documents': {
                'PROGRESSIVE_CLOSURE': {'document': 'NO_STUDENTS_CERTIFICATE', 'unless_matured': True},
                'MERGER': {'document': 'NO_STUDENTS_CERTIFICATE', 'unless_matured': False}},
            'external_noc_if_embezzlement': True,
            'conversion_requires_no_pending_proceedings': True,
        },
        # These are team-proposed operational thresholds, not statutory SLAs.
        'reminders': {'maturity_days': [90, 60, 30, 7], 'proof_days': [7, 12, 15]},
        'escalation': [
            {'trigger': 'MATURITY', 'days': -90, 'recipients': ['INSTITUTION'], 'clock': 'CALENDAR'},
            {'trigger': 'MATURITY', 'days': -60, 'recipients': ['INSTITUTION'], 'clock': 'CALENDAR'},
            {'trigger': 'MATURITY', 'days': -30, 'recipients': ['INSTITUTION', 'OFFICER'], 'clock': 'CALENDAR'},
            {'trigger': 'MATURITY', 'days': -7, 'recipients': ['INSTITUTION', 'OFFICER'], 'clock': 'CALENDAR'},
            {'trigger': 'RENEWAL_OVERDUE', 'days': 1, 'recipients': ['REGIONAL_HEAD'], 'clock': 'CALENDAR'},
            {'trigger': 'PENALTY_REVIEW', 'days': 30, 'recipients': ['OFFICER'], 'clock': 'CALENDAR'},
            {'trigger': 'SUBMISSION_SLA', 'days': 7, 'recipients': ['SUPERVISOR'], 'clock': 'WORKING'},
            {'trigger': 'CORRECTIONS_SLA', 'days': 15, 'recipients': ['INSTITUTION'], 'clock': 'CALENDAR'},
            {'trigger': 'CORRECTIONS_SLA', 'days': 30, 'recipients': ['OFFICER'], 'clock': 'CALENDAR'},
            {'trigger': 'CLEARANCE_SLA', 'days': 7, 'recipients': ['CLEARANCE_UNIT'], 'clock': 'WORKING'},
            {'trigger': 'CLEARANCE_SLA', 'days': 14, 'recipients': ['UNIT_HEAD'], 'clock': 'WORKING'},
        ],
    }
