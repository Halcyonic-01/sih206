"""What a release returns, as a quote (P2-11). No money moves and no interest is computed.

Net = amount held - penalties a human has CONFIRMED. Proposed penalties are listed but not deducted, because they are not
decided yet. Interest is out of scope until a rule for it is approved, and the quote says so.
"""


def quote(held_paise, penalties):
    """`penalties`: objects or dicts with kind, amount_paise, status. Returns integers in paise."""
    def field(item, name):
        return item[name] if isinstance(item, dict) else getattr(item, name)
    confirmed = sum(field(p, 'amount_paise') for p in penalties if field(p, 'status') == 'CONFIRMED')
    proposed = sum(field(p, 'amount_paise') for p in penalties if field(p, 'status') == 'PROPOSED')
    net = max(held_paise - confirmed, 0)
    return {'held_paise': held_paise, 'confirmed_penalties_paise': confirmed, 'proposed_penalties_paise': proposed,
            'net_paise': net, 'penalties_exceed_held': confirmed > held_paise,
            'interest': 'NOT_COMPUTED',
            'note': 'Quote for information. Interest is not included and no payment is made by this portal.'}
