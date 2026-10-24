"""Unsigned SIMULATED PDF generator; no digital signature or bank assertion."""
from io import BytesIO
from urllib.parse import urlparse
from xml.sax.saxutils import escape


def render_letter(*, serial, kind, institution_name, issue_date, verification_url):
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
    from reportlab.graphics.barcode.qr import QrCodeWidget
    from reportlab.graphics.shapes import Drawing
    if urlparse(verification_url).scheme not in {'https', 'http'}:
        raise ValueError('Supply the configured verification URL.')
    target = BytesIO()
    styles = getSampleStyleSheet()
    document = SimpleDocTemplate(target, pagesize=(210 * mm, 297 * mm),
        rightMargin=22 * mm, leftMargin=22 * mm, topMargin=22 * mm, bottomMargin=22 * mm)
    content = [Paragraph('SIMULATED — UNSIGNED DEMO DOCUMENT', styles['Title']), Spacer(1, 10 * mm)]
    for label, value in [('Letter kind', kind), ('Serial', serial), ('Institution', institution_name), ('Issue date', issue_date)]:
        content.append(Paragraph(escape(label + ': ' + str(value)), styles['Normal']))
        content.append(Spacer(1, 4 * mm))
    content += [Spacer(1, 8 * mm), Paragraph(
        'This records a synthetic portal authorization only. It is not independently bank-verified, '
        'digitally signed, evidence of settlement, or a real regulatory NOC or refund sanction.', styles['Normal']), Spacer(1, 8 * mm)]
    qr = QrCodeWidget(verification_url)
    x1, y1, x2, y2 = qr.getBounds()
    size = 42 * mm
    drawing = Drawing(size, size, transform=[size / (x2-x1), 0, 0, size / (y2-y1), 0, 0])
    drawing.add(qr)
    content.extend([drawing, Spacer(1, 4 * mm), Paragraph('QR identifies the demo portal record only.', styles['Normal'])])
    document.build(content)
    return target.getvalue()
