"""Known synthetic, image-only fixture for local OCR/provider smoke checks."""
from io import BytesIO
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

EXPECTED = {'reference': 'SYNTHETIC-OCR-001', 'bank': 'Fictional Bank', 'amount': '500000.25',
            'issue_date': '2026-01-01', 'maturity_date': '2027-01-01', 'ifsc': 'ABCD0123456'}


def scanned_pdf():
    image = Image.new('RGB', (1800, 1000), 'white')
    font_path = Path('C:/Windows/Fonts/arial.ttf')
    font = ImageFont.truetype(str(font_path), 40) if font_path.exists() else ImageFont.load_default(size=40)
    draw = ImageDraw.Draw(image)
    lines = ['SYNTHETIC OCR TEST - NOT A BANK DOCUMENT'] + [f'{label}: {EXPECTED[key]}' for label, key in (
        ('Reference', 'reference'), ('Bank', 'bank'), ('Amount', 'amount'), ('Issue Date', 'issue_date'),
        ('Maturity Date', 'maturity_date'), ('IFSC', 'ifsc'))]
    for index, line in enumerate(lines):
        draw.text((60, 60+index*100), line, font=font, fill='black')
    stream = BytesIO()
    image.save(stream, format='PDF', resolution=150)
    return stream.getvalue()
