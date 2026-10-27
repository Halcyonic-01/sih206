"""Bank and branch master: IFSC directory lookup, merger awareness and name comparison (P2-7). No network access."""
import re

from .models import BankBranch, BankSuccession

_STOP = {'bank', 'ltd', 'limited', 'of', 'the', 'and', 'co', 'operative', 'coop', 'company', 'pvt', 'private', 'public', 'sector'}


def tokens(name):
    return {word for word in re.findall(r'[a-z0-9]+', (name or '').casefold()) if word not in _STOP}


def same_name(declared, listed):
    """Loose, advisory comparison: every distinguishing word of one name appears in the other. Empty names never compare equal."""
    a, b = tokens(declared), tokens(listed)
    return bool(a and b) and (a <= b or b <= a)


def directory_loaded():
    return BankBranch.objects.exists()


def issuer_findings(item):
    """IFSC-based findings for one record; falls back to None when no directory has been loaded."""
    ifsc = (item.ifsc or '').strip().upper()
    if not ifsc:
        return [{'code': 'ISSUER_UNKNOWN', 'severity': 'warning', 'explanation': 'No IFSC is recorded, so the issuing bank cannot be identified.'}]
    row = BankBranch.objects.filter(ifsc=ifsc).first()
    succession = BankSuccession.objects.filter(verified=True, old_code=ifsc[:4]).first()
    if row is not None:
        findings = [{'code': 'ISSUER_UNCONFIRMED', 'severity': 'warning',
                     'explanation': f'IFSC {ifsc} is listed as {row.bank_name}, {row.branch or "branch not named"}'
                                    f'{", " + row.city if row.city else ""} (directory {row.directory_version}). '
                                    'A listing does not confirm that this deposit exists.'}]
        names = [row.bank_name]
        newer = BankSuccession.objects.filter(verified=True, old_code=row.bank_code).first()
        if newer is not None:
            names.append(newer.new_name)
            findings.append({'code': 'ISSUER_MERGED', 'severity': 'info', 'explanation':
                f'{newer.old_name} merged into {newer.new_name}{" on " + newer.effective_date.isoformat() if newer.effective_date else ""}. '
                'This IFSC may still appear on older deposits; a renewal is expected under the new bank.'})
        if item.bank and not any(same_name(item.bank, name) for name in names):
            findings.append({'code': 'ISSUER_NAME_MISMATCH', 'severity': 'warning', 'explanation':
                f'The declared bank "{item.bank}" does not look like the listed bank "{row.bank_name}". Check the document.'})
        if item.branch and row.branch and not (tokens(item.branch) <= tokens(row.branch) or tokens(row.branch) <= tokens(item.branch)):
            findings.append({'code': 'ISSUER_BRANCH_MISMATCH', 'severity': 'warning', 'explanation':
                f'The declared branch "{item.branch}" does not look like the listed branch "{row.branch}".'})
        return findings
    if succession is not None:
        return [{'code': 'ISSUER_MERGED', 'severity': 'info', 'explanation':
                 f'IFSC prefix {succession.old_code} belonged to {succession.old_name}, which merged into {succession.new_name}'
                 f'{" on " + succession.effective_date.isoformat() if succession.effective_date else ""}. It is not in the loaded directory: '
                 'check the document and the successor bank\'s current IFSC.'}]
    if BankBranch.objects.filter(bank_code=ifsc[:4]).exists():
        return [{'code': 'IFSC_NOT_IN_DIRECTORY', 'severity': 'warning', 'explanation':
                 f'The bank code {ifsc[:4]} is known but IFSC {ifsc} is not in the loaded directory. It may be mistyped or newer than the directory.'}]
    return [{'code': 'ISSUER_UNKNOWN', 'severity': 'warning', 'explanation': f'Bank code {ifsc[:4]} is not in the loaded directory; identity needs review.'}]
