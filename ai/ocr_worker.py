"""Local-only, bounded PDF rasterization and Tesseract OCR. No Django or network."""
import csv
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile


def recognize(pdf, renderer, tesseract, pages):
    result = []
    with tempfile.TemporaryDirectory(prefix='fdr-ocr-') as folder:
        for number in range(1, pages + 1):
            target = str(Path(folder) / 'page')
            subprocess.run([renderer, '-f', str(number), '-l', str(number), '-singlefile',
                '-scale-to', '2500', '-png', pdf, target], capture_output=True, timeout=8, check=True)
            response = subprocess.run([tesseract, target + '.png', 'stdout', '-l', 'eng',
                '--psm', '6', 'tsv'], capture_output=True, timeout=8, check=True)
            if len(response.stdout) > 2_000_000:
                raise ValueError('OCR_OUTPUT_LIMIT')
            rows = csv.DictReader(io.StringIO(response.stdout.decode('utf-8')), delimiter='\t')
            lines, confidence = {}, []
            for row in rows:
                word = row.get('text', '').strip()
                if word:
                    key = tuple(row.get(k) for k in ('block_num', 'par_num', 'line_num'))
                    lines.setdefault(key, []).append(word)
                    confidence.append(max(0.0, float(row['conf'])))
            text = '\n'.join(' '.join(words) for words in lines.values())
            if len(text) > 30_000:
                raise ValueError('OCR_OUTPUT_LIMIT')
            result.append({'page': number, 'text': text,
                'confidence': round(sum(confidence)/len(confidence), 1) if confidence else 0})
    return result


if __name__ == '__main__':
    try:
        args = json.loads(sys.stdin.read(20_000))
        print(json.dumps(recognize(args['pdf'], args['renderer'], args['tesseract'], args['pages'])))
    except Exception:
        sys.exit(1)
