"""Isolated PDF inspection worker. No Django, network calls or document execution."""
import json
import sys

import pikepdf


def inspect(path):
    with pikepdf.open(path, attempt_recovery=False) as pdf:
        if pdf.is_encrypted:
            raise ValueError('Encrypted PDFs are not supported.')
        count = len(pdf.pages)
        if not 1 <= count <= 1000:
            raise ValueError('PDF must contain between 1 and 1000 pages.')
        if pdf.check_pdf_syntax():
            raise ValueError('PDF structure is invalid or requires repair.')
        seen = set()
        budget = 100000

        def visit(obj):
            nonlocal budget
            budget -= 1
            if budget < 0:
                raise ValueError('PDF structure exceeds the inspection limit.')
            if isinstance(obj, (pikepdf.Dictionary, pikepdf.Array, pikepdf.Stream)):
                key = obj.objgen
                if key != (0, 0):
                    if key in seen:
                        return
                    seen.add(key)
            if isinstance(obj, (pikepdf.Dictionary, pikepdf.Stream)):
                forbidden = {'/JS', '/JavaScript', '/EmbeddedFiles', '/EF', '/AA', '/OpenAction'}
                if forbidden.intersection(str(k) for k in obj.keys()):
                    raise ValueError('PDF active content or embedded files are not supported.')
                if str(obj.get('/S', '')) in {'/JavaScript', '/Launch', '/GoToR', '/SubmitForm', '/ImportData'}:
                    raise ValueError('PDF executable or external actions are not supported.')
                for value in obj.values():
                    visit(value)
            elif isinstance(obj, pikepdf.Array):
                for value in obj:
                    visit(value)

        for obj in pdf.objects:
            visit(obj)
        return count


if __name__ == '__main__':
    try:
        print(json.dumps({'page_count': inspect(sys.argv[1])}))
    except Exception:
        # Never return parser messages, paths or embedded content to the caller.
        print(json.dumps({'error': 'PDF is encrypted, malformed, unsupported or contains active content.'}))
        raise SystemExit(1)
