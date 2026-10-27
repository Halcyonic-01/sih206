"""Near-duplicate scan detection (P3-2): compare the first page of a document with other institutions' and released ones.

The first page is rendered by Poppler (`pdftoppm`, the same optional tool as local OCR, in a child process with a timeout) and
reduced to a 1024-bit difference hash (32 x 32 grid) with Pillow. A copy of the same file or image, re-saved, resized or lightly
recompressed, differs by a handful of bits; a different document, even on the same bank's template, differs by more. The match
threshold is deliberately tight (3 bits), so a physical re-scan of paper will usually *not* match: this finds recycled files, not
every kind of fraud. It is an officer-only hint on top of the bank-and-reference duplicate check: it proves nothing about
authenticity and a document is never refused because of it. Without `pdftoppm` nothing is computed and no finding appears.
"""
import logging
import subprocess
import tempfile
from pathlib import Path

from django.conf import settings

from .models import DocumentFingerprint

logger = logging.getLogger(__name__)
SIZE = 32
MAX_DISTANCE = 3          # of SIZE * SIZE = 1024 bits
CANDIDATE_LIMIT = 20000


def available():
    from ai.ocr import tool_path
    return bool(getattr(settings, 'NEAR_DUPLICATE_SCAN', True)) and tool_path('OCR_PDFTOPPM', 'pdftoppm')


def dhash(png_path):
    from PIL import Image
    with Image.open(png_path) as image:
        small = image.convert('L').resize((SIZE + 1, SIZE), Image.Resampling.LANCZOS)
    pixels = list(small.tobytes())
    bits = 0
    for row in range(SIZE):
        for column in range(SIZE):
            bits = (bits << 1) | (pixels[row * (SIZE + 1) + column] > pixels[row * (SIZE + 1) + column + 1])
    return f'{bits:0{SIZE * SIZE // 4}x}'


def compute(document):
    """The dHash of page 1 as 256 hex characters, or None when it cannot be computed."""
    renderer = available()
    if not renderer:
        return None
    try:
        with document.file.open('rb') as stored:
            content = stored.read(10 * 1024 * 1024 + 1)
        if len(content) > 10 * 1024 * 1024:
            return None
        with tempfile.TemporaryDirectory(prefix='fdr-fp-') as folder:
            pdf, target = Path(folder) / 'in.pdf', Path(folder) / 'page'
            pdf.write_bytes(content)
            subprocess.run([renderer, '-f', '1', '-l', '1', '-singlefile', '-scale-to', '512', '-png', str(pdf), str(target)],
                           capture_output=True, timeout=10, check=True)
            return dhash(str(target) + '.png')
    except Exception:   # a document that will not render simply has no fingerprint
        logger.info('No fingerprint for document %s', document.pk, exc_info=True)
        return None


def ensure(document):
    """The stored fingerprint, computing it now if needed (None when unavailable)."""
    row = DocumentFingerprint.objects.filter(document=document).first()
    if row is not None:
        return row
    if document.scan_status == 'REJECTED':
        return None
    value = compute(document)
    if value is None:
        return None
    row, _ = DocumentFingerprint.objects.get_or_create(document=document, defaults={'phash': value})
    return row


def distance(a, b):
    return (int(a, 16) ^ int(b, 16)).bit_count()


def near_duplicates(instrument, visible_instruments):
    """[(other instrument, distance)] whose first page looks like one of this record's: other institutions, or released ones."""
    from django.db.models import Q
    from portal.models import Document
    mine = [row.phash for row in (ensure(d) for d in Document.objects.filter(instrument=instrument)) if row]
    if not mine:
        return []
    candidates = (DocumentFingerprint.objects.filter(document__instrument__in=visible_instruments)
                  .exclude(document__instrument=instrument)
                  .filter(~Q(document__instrument__institution_id=instrument.institution_id) | Q(document__instrument__released_at__isnull=False))
                  .select_related('document__instrument')[:CANDIDATE_LIMIT])
    best = {}
    for row in candidates:
        gap = min(distance(own, row.phash) for own in mine)
        if gap <= MAX_DISTANCE:
            other = row.document.instrument
            if other.pk not in best or gap < best[other.pk][1]:
                best[other.pk] = (other, gap)
    return sorted(best.values(), key=lambda pair: (pair[1], pair[0].pk))[:5]
