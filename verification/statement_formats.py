"""Read bank statements: our CSV, SWIFT MT940 and ISO 20022 CAMT.053 (P2-6).

Each format becomes the same rows (`number, utr, amount_paise, value_date`, plus `alt_utrs` for other references on the line), so
matching and the SIMULATED labelling are unchanged. Only credits are read (money received); debits and reversals are listed as
ignored. A malformed MT940/CAMT entry is quarantined in `rejected` with the reason instead of failing the whole file; a file with
no usable credit is refused. XML with a DOCTYPE or entity declaration is refused outright.
"""
import csv
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, InvalidOperation
from io import StringIO

from django.core.exceptions import ValidationError

MAX_ROWS = 1000
MAX_AMOUNT = Decimal('999999999999.99')


@dataclass
class Parsed:
    format: str
    rows: list = field(default_factory=list)
    rejected: list = field(default_factory=list)   # [{'where': ..., 'reason': ...}] malformed entries, quarantined
    ignored: list = field(default_factory=list)    # [{'where': ..., 'reason': ...}] valid but not credits

    def summary(self):
        return {'format': self.format, 'rejected': self.rejected, 'ignored': self.ignored}


def _amount(text, comma_decimal=False):
    try:
        value = Decimal(text.replace(',', '.') if comma_decimal else text)
    except InvalidOperation:
        raise ValueError('amount is not a number') from None
    if not value.is_finite() or value <= 0 or value.as_tuple().exponent < -2 or value > MAX_AMOUNT:
        raise ValueError('amount must be positive with at most two decimals')
    return int(value * 100)


def _row(number, utr, amount_paise, value_date, alternatives=()):
    seen, alt = {utr.upper()}, []
    for item in alternatives:
        item = item.strip().upper()
        if item and item not in seen and len(item) <= 100:
            seen.add(item)
            alt.append(item)
    return {'number': number, 'utr': utr.strip().upper(), 'amount_paise': amount_paise, 'value_date': value_date, 'alt_utrs': alt[:5]}


def detect(text):
    head = text.lstrip('\ufeff \r\n\t')
    if head.startswith('<'):
        return 'CAMT053'
    if re.search(r'^:(20|25|28C?|60[FM]|61):', head, re.M) or head.startswith('{1:'):
        return 'MT940'
    return 'CSV'


def parse_csv(text):
    try:
        reader = csv.DictReader(StringIO(text), strict=True)
        if reader.fieldnames != ['utr', 'amount', 'value_date']:
            raise ValueError('headers')
        rows = []
        for number, row in enumerate(reader, 1):
            if number > MAX_ROWS or None in row or any(v is None for v in row.values()):
                raise ValueError('rows')
            utr = row['utr'].strip().upper()
            day = date.fromisoformat(row['value_date'])
            if not utr or len(utr) > 100 or day.isoformat() != row['value_date']:
                raise ValueError('values')
            rows.append(_row(number, utr, _amount(row['amount']), day))
        if not rows:
            raise ValueError('empty')
    except (ValueError, csv.Error):
        raise ValidationError('Use UTF-8 CSV headers utr,amount,value_date and positive two-decimal amounts.') from None
    return Parsed('CSV', rows)


_FIELD = re.compile(r'^:(\d{2}[A-Z]?):', re.M)
_ENTRY = re.compile(r'^(?P<vd>\d{6})(?:\d{4})?(?P<dc>R?[CD])[A-Z]?(?P<amt>\d+,\d{0,2})N(?P<type>[A-Z0-9]{3})'
                    r'(?P<ref>[^/\r\n]*)(?://(?P<bank>[^\r\n]*))?', re.S)
_TOKEN = re.compile(r'\b(?=[A-Z0-9]*\d)[A-Z0-9]{10,35}\b')


def parse_mt940(text):
    parsed = Parsed('MT940')
    text = text.replace('\r\n', '\n').replace('\r', '\n')
    matches = list(_FIELD.finditer(text))
    entries = []   # [(tag, value)]
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        value = text[match.end():end].rstrip('-}\n ').strip('\n')
        entries.append((match.group(1), value))
    line = 0
    for position, (tag, value) in enumerate(entries):
        if tag != '61':
            continue
        line += 1
        where = f'entry {line}'
        entry = _ENTRY.match(value.split('\n')[0])
        if entry is None:
            parsed.rejected.append({'where': where, 'reason': 'not a valid :61: statement line'})
            continue
        info = ''
        if position + 1 < len(entries) and entries[position + 1][0] == '86':
            info = entries[position + 1][1].replace('\n', ' ')
        try:
            stamp = entry.group('vd')
            day = date(2000 + int(stamp[:2]), int(stamp[2:4]), int(stamp[4:6]))
            paise = _amount(entry.group('amt'), comma_decimal=True)
        except ValueError as error:
            parsed.rejected.append({'where': where, 'reason': str(error) if 'amount' in str(error) else 'invalid value date'})
            continue
        if entry.group('dc') != 'C':
            parsed.ignored.append({'where': where, 'reason': 'debit or reversal, not a receipt'})
            continue
        references = [entry.group('ref').strip(), (entry.group('bank') or '').strip()]
        references = [r for r in references if r and r.upper() != 'NONREF']
        references += _TOKEN.findall(info.upper())
        if not references:
            parsed.rejected.append({'where': where, 'reason': 'no payment reference (UTR) on the line'})
            continue
        parsed.rows.append(_row(len(parsed.rows) + 1, references[0], paise, day, references[1:]))
    return parsed


def _local(tag):
    return tag.rsplit('}', 1)[-1]


def _child(node, *path):
    for name in path:
        node = next((c for c in node if _local(c.tag) == name), None)
        if node is None:
            return None
    return node


def _text(node, *path):
    found = _child(node, *path)
    return (found.text or '').strip() if found is not None and found.text else ''


def parse_camt053(text):
    if re.search(r'<!(DOCTYPE|ENTITY)', text, re.I):
        raise ValidationError('This XML statement uses a document type declaration, which is not accepted.')
    try:
        root = ET.fromstring(text.encode('utf-8'))
    except ET.ParseError:
        raise ValidationError('The XML statement could not be read.') from None
    if not any(_local(el.tag) == 'BkToCstmrStmt' for el in root.iter()):
        raise ValidationError('This XML is not a CAMT.053 bank-to-customer statement.')
    parsed = Parsed('CAMT053')
    number = 0
    for entry in (el for el in root.iter() if _local(el.tag) == 'Ntry'):
        number += 1
        where = f'entry {number}'
        amount_node = _child(entry, 'Amt')
        if amount_node is None:
            parsed.rejected.append({'where': where, 'reason': 'entry has no amount'})
            continue
        direction = _text(entry, 'CdtDbtInd')
        if direction != 'CRDT':
            parsed.ignored.append({'where': where, 'reason': 'debit or reversal, not a receipt'})
            continue
        if amount_node.get('Ccy', 'INR') != 'INR':
            parsed.rejected.append({'where': where, 'reason': 'currency is not INR'})
            continue
        day_text = (_text(entry, 'ValDt', 'Dt') or _text(entry, 'ValDt', 'DtTm')[:10] or _text(entry, 'BookgDt', 'Dt')
                    or _text(entry, 'BookgDt', 'DtTm')[:10])
        try:
            day = date.fromisoformat(day_text)
            total = _amount(amount_node.text or '')
        except ValueError as error:
            parsed.rejected.append({'where': where, 'reason': str(error) if 'amount' in str(error) else 'invalid or missing value date'})
            continue
        details = [el for el in entry.iter() if _local(el.tag) == 'TxDtls'] or [entry]
        for detail in details:
            references = [_text(detail, 'Refs', name) for name in ('EndToEndId', 'TxId', 'UETR', 'AcctSvcrRef', 'InstrId')]
            references += [_text(entry, 'AcctSvcrRef'), _text(entry, 'NtryRef')]
            references = [r for r in references if r and r.upper() not in {'NOTPROVIDED', 'NONREF'}]
            try:
                paise = _amount(_text(detail, 'AmtDtls', 'TxAmt', 'Amt') or '') if len(details) > 1 else total
            except ValueError:
                parsed.rejected.append({'where': where, 'reason': 'transaction amount is missing or invalid'})
                continue
            if not references:
                parsed.rejected.append({'where': where, 'reason': 'no payment reference (UTR) on the entry'})
                continue
            parsed.rows.append(_row(len(parsed.rows) + 1, references[0], paise, day, references[1:]))
    return parsed


def parse(content):
    """Detect the format and read it. Raises ValidationError when nothing usable is found."""
    if len(content) > 1024 * 1024:
        raise ValidationError('Statement must be at most 1 MB.')
    try:
        text = content.decode('utf-8-sig')
    except UnicodeError:
        raise ValidationError('The statement must be UTF-8 text.') from None
    kind = detect(text)
    parsed = {'CSV': parse_csv, 'MT940': parse_mt940, 'CAMT053': parse_camt053}[kind](text)
    if not parsed.rows:
        raise ValidationError('No credit entries with a payment reference were found in this ' + kind + ' statement.')
    if len(parsed.rows) > MAX_ROWS:
        raise ValidationError(f'At most {MAX_ROWS} entries are accepted in one statement.')
    return parsed
