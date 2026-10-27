"""Advisory differences between extracted values and the record, shared by AI extraction and local OCR (P2-8)."""
from . import normalize


def build_findings(instrument, output):
    """AI_MISMATCH / AMOUNT_WORDS_MISMATCH findings. A value that cannot be read with confidence is never reported as a mismatch."""
    findings = []
    for name, field in output['fields'].items():
        actual = field['value']
        declared = str(getattr(instrument, name))
        verdict, note = normalize.compare(name, actual, declared)
        if verdict == 'different':
            finding = {'code': 'AI_MISMATCH', 'severity': 'advisory', 'field': name, 'declared': declared,
                       'suggested': actual, 'page': field['page']}
            if note:
                finding['detail'] = note
            findings.append(finding)
        elif verdict == 'same' and note:   # equal once read as DD/MM, but the document is ambiguous: say so
            findings.append({'code': 'AI_DATE_AMBIGUOUS', 'severity': 'advisory', 'field': name, 'declared': declared,
                             'suggested': actual, 'page': field['page'], 'detail': note})
    words = output.get('amount_in_words')
    if words:
        finding = normalize.amount_words_finding(words, output['fields']['amount']['value'], str(instrument.amount))
        if finding:
            findings.append(finding)
    return findings
