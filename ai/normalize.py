"""Normalise before comparing, so formatting alone never raises a mismatch (P2-8).

Advisory helpers for the AI and OCR comparisons: Indian digit grouping and currency marks in amounts, common bank-name
abbreviations and suffixes, several date layouts (with day/month ambiguity flagged, not guessed silently), and amounts written in
words using Indian numbering (lakh, crore). Anything that cannot be read with confidence returns None, which means
"cannot compare", never "different".
"""
import re
from datetime import date
from decimal import Decimal, InvalidOperation

# ---- amounts -------------------------------------------------------------------------------------------------------------
_CURRENCY = re.compile(r'(?i)(?:₹|\brs\.?|\binr\b|\brupees?\b|/-)')


def normalize_amount(text):
    """'₹ 5,00,000.25', 'INR 500000.25/-', '500,000.25' -> Decimal('500000.25'); None when it is not a plain figure."""
    if text is None:
        return None
    cleaned = _CURRENCY.sub(' ', str(text)).replace(',', '').strip().rstrip('.').strip()
    if not re.fullmatch(r'\d+(\.\d{1,2})?', cleaned):
        return None
    try:
        return Decimal(cleaned)
    except InvalidOperation:
        return None


def amounts_equal(a, b):
    left, right = normalize_amount(a), normalize_amount(b)
    return None if left is None or right is None else left == right


# ---- amounts in words (Indian numbering) ---------------------------------------------------------------------------------
_UNITS = {w: i for i, w in enumerate(
    'zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen'.split())}
_TENS = {w: 10 * i for i, w in enumerate('_ _ twenty thirty forty fifty sixty seventy eighty ninety'.split()) if w != '_'}
_SCALE = {'thousand': 1_000, 'lakh': 100_000, 'lakhs': 100_000, 'lac': 100_000, 'lacs': 100_000, 'crore': 10_000_000, 'crores': 10_000_000}
_IGNORED = {'rupees', 'rupee', 'rs', 'inr', 'only', 'and', 'the', 'of', 'indian'}


def _number(tokens):
    """Whole number from words, or None if any word is not understood."""
    if not tokens:
        return None
    total = current = 0
    for word in tokens:
        if word in _UNITS:
            current += _UNITS[word]
        elif word in _TENS:
            current += _TENS[word]
        elif word == 'hundred':
            current = (current or 1) * 100
        elif word in _SCALE:
            total += (current or 1) * _SCALE[word]
            current = 0
        else:
            return None
    return total + current


def words_to_paise(text):
    """'Rupees Five Lakh Twenty Five Thousand and Paise Twenty Five Only' -> 50025025; None when unsure."""
    if not text:
        return None
    tokens = re.sub(r'[^a-z\s-]', ' ', text.casefold().replace('-', ' ')).split()
    paise = 0
    for marker in ('paise', 'paisa'):
        if marker in tokens:
            at = tokens.index(marker)
            after = [t for t in tokens[at + 1:] if t not in _IGNORED]
            before = tokens[:at]
            if 'and' in before:                       # '... and twenty five paise'
                split = len(before) - 1 - before[::-1].index('and')
                part, tokens = before[split + 1:], before[:split]
            elif after:                               # '... paise twenty five'
                part, tokens = after, before
            else:
                return None
            part = [t for t in part if t not in _IGNORED]
            value = _number(part)
            if value is None or value >= 100:
                return None
            paise, tokens = value, [t for t in tokens]
            break
    rupees = _number([t for t in tokens if t not in _IGNORED])
    return None if rupees is None else rupees * 100 + paise


# ---- bank names ----------------------------------------------------------------------------------------------------------
_BANK_ALIASES = {
    'sbi': 'state bank of india', 'pnb': 'punjab national bank', 'boi': 'bank of india', 'bob': 'bank of baroda',
    'hdfc': 'hdfc', 'icici': 'icici', 'uco': 'uco', 'iob': 'indian overseas bank', 'cbi': 'central bank of india',
    'boi.': 'bank of india', 'ubi': 'union bank of india', 'canara': 'canara',
}
_BANK_NOISE = {'bank', 'ltd', 'limited', 'the', 'of', 'and', 'co', 'operative', 'coop', 'company', 'pvt', 'private', 'public', 'sector',
               'branch', 'india'}


def bank_tokens(name):
    text = ' '.join(_BANK_ALIASES.get(w, w) for w in re.findall(r"[a-z0-9.]+", (name or '').casefold()))
    return {w for w in re.findall(r'[a-z0-9]+', text) if w not in _BANK_NOISE}


def banks_equal(a, b):
    """Loose: the distinguishing words of one name are contained in the other. None when either has no distinguishing word."""
    left, right = bank_tokens(a), bank_tokens(b)
    if not left or not right:
        return None
    return left <= right or right <= left


# ---- dates ---------------------------------------------------------------------------------------------------------------
_MONTHS = {m: i for i, m in enumerate('jan feb mar apr may jun jul aug sep oct nov dec'.split(), 1)}


def normalize_date(text):
    """(date, ambiguous) or (None, False). Numeric day/month is read as DD/MM (Indian convention) and flagged when both are <= 12."""
    if text is None:
        return None, False
    value = str(text).strip()
    m = re.fullmatch(r'(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})', value)
    try:
        if m:
            return date(int(m[1]), int(m[2]), int(m[3])), False
        m = re.fullmatch(r'(\d{1,2})[-/.](\d{1,2})[-/.](\d{4})', value)
        if m:
            day, month = int(m[1]), int(m[2])
            return date(int(m[3]), month, day), bool(day <= 12 and month <= 12 and day != month)
        m = re.fullmatch(r'(\d{1,2})(?:st|nd|rd|th)?[\s-]+([A-Za-z]{3,9})\.?,?[\s-]+(\d{4})', value)
        if m and m[2][:3].casefold() in _MONTHS:
            return date(int(m[3]), _MONTHS[m[2][:3].casefold()], int(m[1])), False
        m = re.fullmatch(r'([A-Za-z]{3,9})\.?\s+(\d{1,2})(?:st|nd|rd|th)?,?\s+(\d{4})', value)
        if m and m[1][:3].casefold() in _MONTHS:
            return date(int(m[3]), _MONTHS[m[1][:3].casefold()], int(m[2])), False
    except ValueError:
        return None, False
    return None, False


# ---- one comparison entry point ------------------------------------------------------------------------------------------
def compare(name, actual, declared):
    """('same'|'different'|'unknown', note). 'unknown' when a value cannot be read; callers must not raise a mismatch for it."""
    if actual is None:
        return 'unknown', None
    actual, declared = str(actual).strip(), str(declared).strip()
    if name == 'amount':
        same = amounts_equal(actual, declared)
    elif name == 'bank':
        same = banks_equal(actual, declared)
    elif name in ('issue_date', 'maturity_date'):
        a, ambiguous = normalize_date(actual)
        b, _ = normalize_date(declared)
        if a is None or b is None:
            same = None
        else:
            same = a == b
            if ambiguous:  # both numbers are <= 12: say which reading was used
                if same:
                    return 'same', 'The document date could be read as day/month or month/day; it was read as DD/MM.'
                if date(a.year, a.day, a.month) == b:
                    return 'different', 'The document date is ambiguous: read as month/day it would match the record.'
    elif name == 'ifsc':
        same = re.sub(r'\s', '', actual).upper() == re.sub(r'\s', '', declared).upper()
    else:  # reference and anything else: ignore case and spacing only
        same = re.sub(r'\s+', '', actual).casefold() == re.sub(r'\s+', '', declared).casefold()
    if same is None:
        return 'unknown', None
    return ('same' if same else 'different'), None


def amount_words_finding(words, figures, declared):
    """AMOUNT_WORDS_MISMATCH when the amount written in words differs from the figures (extracted, else declared). None otherwise."""
    paise = words_to_paise(words)
    reference = normalize_amount(figures) if figures is not None else None
    source = 'the figures on the document'
    if reference is None:
        reference, source = normalize_amount(declared), 'the amount declared on the record'
    if paise is None or reference is None or Decimal(paise) == reference * 100:
        return None
    return {'code': 'AMOUNT_WORDS_MISMATCH', 'severity': 'advisory', 'field': 'amount',
            'declared': str(reference), 'suggested': f'{Decimal(paise) / 100:.2f}',
            'detail': f'The amount in words ("{words}") differs from {source}. Check the document.'}
