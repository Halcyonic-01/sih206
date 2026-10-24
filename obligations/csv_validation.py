"""Pure S4 demo CSV validation. No models, queries, files, network or writes."""
import csv
from dataclasses import dataclass
import hashlib
from io import StringIO
import re
import unicodedata

from django.core.exceptions import ValidationError
from django.core.validators import validate_email

FORMAT = 'institution-csv-v1'
MAX_BYTES = 1024 * 1024
MAX_ROWS = 1000
LIMITS = {
    'aicte_id': 50, 'institution_code': 30, 'institution_name': 200,
    'trust_name': 250, 'institution_type': 20, 'region': 100, 'state': 100,
    'contact_email': 254, 'status': 10, 'data_classification': 9,
}
COLUMNS = tuple(LIMITS)
IDENTITIES = ('aicte_id', 'institution_code')
TOKEN = re.compile(r'[A-Za-z0-9][A-Za-z0-9_-]*', re.ASCII)
CHOICES = {'institution_type': {'GOVERNMENT', 'AIDED', 'PRIVATE', 'UNIVERSITY'},
           'status': {'ACTIVE', 'INACTIVE'}}


class CsvInputError(ValueError):
    """Invalid caller contract, not a malformed CSV file."""


@dataclass(frozen=True)
class ExistingIdentity:
    aicte_id: str | None
    institution_code: str


def _context(identities):
    if type(identities) is not tuple:
        raise CsvInputError('Supply an explicit tuple of existing identity snapshots.')
    result = {key: set() for key in IDENTITIES}
    for identity in identities:
        if type(identity) is not ExistingIdentity:
            raise CsvInputError('Existing identities must be typed value snapshots.')
        for key in IDENTITIES:
            value = getattr(identity, key)
            if value is None and key == 'aicte_id':
                continue
            if not isinstance(value, str) or not value.strip() or len(value.strip()) > LIMITS[key]:
                raise CsvInputError('Existing identity context contains an invalid value.')
            if any(unicodedata.category(c).startswith('C') for c in value):
                raise CsvInputError('Existing identity context contains control characters.')
            result[key].add(value.strip().upper())
    return result


def _field_error(field, raw):
    if any(unicodedata.category(c).startswith('C') for c in raw):
        return 'CONTROL_CHARACTER'
    value = raw.strip()
    if not value:
        return 'REQUIRED'
    if value[0] in '=+-@':
        return 'FORMULA_PREFIX'
    if len(value) > LIMITS[field]:
        return 'TOO_LONG'
    if field in IDENTITIES and not TOKEN.fullmatch(value):
        return 'INVALID_TOKEN'
    if field in CHOICES and value not in CHOICES[field]:
        return 'INVALID_CHOICE'
    if field == 'data_classification' and value != 'SIMULATED':
        return 'NOT_SIMULATED'
    if field == 'contact_email':
        try:
            validate_email(value)
        except ValidationError:
            return 'INVALID_EMAIL'
    return None


def validate_institution_csv(content, *, existing_identities):
    """Return detached validation data; caller supplies complete conflict context.

    INVALID is never permission to commit the valid subset. VALID is not source
    authentication, bank verification, regulatory compliance or authorization.
    """
    if type(content) is not bytes:
        raise CsvInputError('CSV content must be bytes.')
    known = _context(existing_identities)
    base = {'format': FORMAT, 'simulation_label': 'SIMULATED',
            'source_sha256': hashlib.sha256(content).hexdigest()}

    def file_failure(errors):
        return {**base, 'status': 'INVALID', 'row_count': None, 'valid_count': 0,
                'invalid_count': None, 'valid_rows': [], 'errors': errors}

    def file_error(code):
        return file_failure([{'row': None, 'field': '__file__', 'code': code}])

    if len(content) > MAX_BYTES:
        return file_error('FILE_TOO_LARGE')
    try:
        text = content.decode('utf-8-sig')
    except UnicodeDecodeError:
        return file_error('INVALID_UTF8')
    reader = csv.reader(StringIO(text, newline=''), strict=True)
    try:
        header = next(reader, None)
        if header is None:
            return file_error('EMPTY_FILE')
        errors = []
        for field in COLUMNS:
            if field not in header:
                errors.append({'row': None, 'field': field, 'code': 'HEADER_MISSING'})
        if any(field not in COLUMNS for field in header):
            errors.append({'row': None, 'field': '__header__', 'code': 'HEADER_UNKNOWN'})
        if len(header) != len(set(header)):
            errors.append({'row': None, 'field': '__header__', 'code': 'HEADER_DUPLICATE'})
        if errors:
            return file_failure(errors)
        parsed = []
        for row in reader:
            parsed.append(row)
            if len(parsed) > MAX_ROWS:
                return file_error('ROW_LIMIT')
    except csv.Error:
        return file_error('CSV_SYNTAX')
    if not parsed:
        return file_error('NO_DATA')
    errors, candidates = [], []
    seen = {key: {} for key in IDENTITIES}
    for number, row in enumerate(parsed, start=2):
        if len(row) != len(header):
            errors.append({'row': number, 'field': '__row__',
                           'code': 'EMPTY_ROW' if not row else 'COLUMN_COUNT'})
            continue
        raw = dict(zip(header, row))
        values = {}
        for field in COLUMNS:
            code = _field_error(field, raw[field])
            if code:
                errors.append({'row': number, 'field': field, 'code': code})
                continue
            value = raw[field].strip()
            values[field] = value.upper() if field in IDENTITIES else value
            if field in IDENTITIES:
                seen[field].setdefault(values[field], []).append(number)
                if values[field] in known[field]:
                    errors.append({'row': number, 'field': field, 'code': 'EXISTING_IDENTITY'})
        candidates.append({'row': number, 'values': values})
    for field in IDENTITIES:
        for numbers in seen[field].values():
            if len(numbers) > 1:
                errors.extend({'row': number, 'field': field, 'code': 'DUPLICATE_IDENTITY'}
                              for number in numbers)
    errors.sort(key=lambda error: (error['row'], error['field'], error['code']))
    bad_rows = {error['row'] for error in errors}
    valid = [row for row in candidates if row['row'] not in bad_rows]
    return {**base, 'status': 'INVALID' if errors else 'VALID', 'row_count': len(parsed),
            'valid_count': len(valid), 'invalid_count': len(bad_rows),
            'valid_rows': valid, 'errors': errors}
