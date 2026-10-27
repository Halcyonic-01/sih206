"""Advisory local OCR. Ambiguous/invalid values stay unknown; no record writes."""
from datetime import datetime
from decimal import Decimal, InvalidOperation
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
from time import monotonic

from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.utils import timezone
from datetime import timedelta

from portal.permissions import role, scoped_instruments
from .comparison import build_findings
from .models import AiRun
from .services import FIELD_NAMES, validate_output

LABELS = {'reference': r'(?:FDR\s*(?:No\.?|Number)|Reference)', 'bank': r'Bank(?: Name)?',
    'amount': r'(?:Deposit Amount|Amount)(?:\s*\(INR\))?', 'issue_date': r'Issue Date',
    'maturity_date': r'Maturity Date', 'ifsc': r'IFSC(?: Code)?'}


def parse_fields(pages):
    candidates = {name: set() for name in FIELD_NAMES}
    for page in pages:
        if page['confidence'] < 65:
            continue
        for name, label in LABELS.items():
            for match in re.finditer(r'^\s*' + label + r'\s*[:=]\s*(.+?)\s*$', page['text'], re.I | re.M):
                value = match[1].strip()
                try:
                    if name == 'amount':
                        value = re.sub(r'^(?:INR|Rs\.?)\s*', '', value, flags=re.I).replace(',', '')
                        amount = Decimal(value)
                        if not amount.is_finite() or amount.as_tuple().exponent < -2:
                            raise ValueError('Ambiguous amount')
                        value = str(amount)
                    elif name.endswith('_date'):
                        formats = ('%Y-%m-%d', '%d/%m/%Y', '%d-%m-%Y')
                        value = next(datetime.strptime(value, fmt).date().isoformat() for fmt in formats
                                     if _matches_date(value, fmt))
                    elif name == 'ifsc':
                        value = value.upper().replace(' ', '')
                    test = {'fields': {key: {'value': value if key == name else None,
                                            'page': page['page'] if key == name else None} for key in FIELD_NAMES}}
                    validate_output(test, len(pages))
                    candidates[name].add((value, page['page']))
                except (ValueError, InvalidOperation, StopIteration):
                    continue
    fields = {}
    for name, values in candidates.items():
        # Repeated identical values are fine; conflicting pages/values require manual review.
        distinct = {value for value, _ in values}
        value, page = min(values, key=lambda pair: pair[1]) if len(distinct) == 1 else (None, None)
        fields[name] = {'value': value, 'page': page}
    return {'fields': fields}


def _matches_date(value, fmt):
    try:
        datetime.strptime(value, fmt)
        return True
    except ValueError:
        return False


def tool_path(setting, executable):
    configured = getattr(settings, setting, '')
    if configured:
        return str(Path(configured).resolve()) if Path(configured).is_file() else None
    located = shutil.which(executable)
    if not located and executable == 'tesseract':
        candidate = Path('C:/Program Files/Tesseract-OCR/tesseract.exe')
        located = str(candidate) if sys.platform == 'win32' and candidate.is_file() else None
    return located


def extract_local(actor, document):
    if role(actor) not in ('institution', 'officer') or not scoped_instruments(actor).filter(pk=document.instrument_id).exists():
        raise PermissionDenied('This document is not available for OCR.')
    result = {'advisory': True, 'label': 'OCR suggestions: verify against the document', 'fields': {}, 'findings': []}
    run = AiRun.objects.create(actor=actor, document=document, operation='LOCAL_OCR', model='tesseract-eng',
                               status='STARTED', input_sha256=document.sha256)
    start = monotonic()
    try:
        if not settings.OCR_ENABLED:
            run.status, run.error_code = 'DISABLED', 'OCR_DISABLED'
            return result | {'status': 'disabled', 'detail': 'Local OCR is disabled. Continue manual entry.'}
        renderer, engine = tool_path('OCR_PDFTOPPM', 'pdftoppm'), tool_path('OCR_TESSERACT', 'tesseract')
        if not renderer or not engine:
            raise ValueError('OCR_NOT_CONFIGURED')
        if document.page_count is None or not 1 <= document.page_count <= 5 or document.size_bytes > 10 * 1024 * 1024:
            raise ValueError('DOCUMENT_LIMIT')
        from portal.scanning import downloadable
        if not downloadable(document):
            raise ValueError('DOCUMENT_NOT_SCANNED')
        if AiRun.objects.filter(actor=actor, operation='LOCAL_OCR', created_at__gte=timezone.now()-timedelta(hours=1)).count() > 10:
            raise ValueError('RATE_LIMIT')
        with document.file.open('rb') as source:
            content = source.read(10 * 1024 * 1024 + 1)
        if len(content) > 10 * 1024 * 1024 or hashlib.sha256(content).hexdigest() != document.sha256:
            raise ValueError('DOCUMENT_INTEGRITY')
        with tempfile.TemporaryDirectory(prefix='fdr-local-') as directory:
            pdf = Path(directory) / 'input.pdf'
            pdf.write_bytes(content)
            completed = subprocess.run([sys.executable, '-I', str(Path(__file__).with_name('ocr_worker.py'))],
                input=json.dumps({'pdf': str(pdf), 'renderer': renderer, 'tesseract': engine, 'pages': document.page_count}),
                text=True, capture_output=True, timeout=45, check=True,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0)
        pages = json.loads(completed.stdout)
        output = validate_output(parse_fields(pages), document.page_count)
        run.status, run.output = 'SUCCESS', output
        return result | output | {'status': 'success', 'pages': pages, 'findings': build_findings(document.instrument, output),
            'detail': 'Processed locally. Low-confidence, missing and conflicting fields require manual entry.'}
    except Exception as exc:
        run.status = 'FAILED'
        run.error_code = ('TIMEOUT' if isinstance(exc, subprocess.TimeoutExpired) else
                          str(exc) if isinstance(exc, ValueError) and str(exc) in
                          ('OCR_NOT_CONFIGURED', 'DOCUMENT_LIMIT', 'RATE_LIMIT', 'DOCUMENT_INTEGRITY', 'DOCUMENT_NOT_SCANNED') else 'OCR_FAILED')
        return result | {'status': 'unavailable', 'detail': 'Local OCR unavailable. Continue manual entry.', 'code': run.error_code}
    finally:
        run.duration_ms = int((monotonic()-start)*1000)
        run.save(update_fields=['status', 'output', 'error_code', 'duration_ms'])
