"""CSV presentation only. Authorization and filtering belong to the shared view helper."""
import csv
from io import StringIO

from django.http import HttpResponse

from .deadlines import classify_maturity


def spreadsheet_text(value):
    text = str(value)
    # Excel may ignore whitespace/control characters before interpreting a formula.
    leading = text
    while leading and (leading[0].isspace() or ord(leading[0]) < 33 or leading[0] == '\ufeff'):
        leading = leading[1:]
    if leading.startswith(('=', '+', '-', '@')) or text.startswith(('\t', '\r', '\n')):
        return "'" + text
    return text


def register_csv(records, as_of):
    output = StringIO(newline='')
    writer = csv.writer(output)
    writer.writerow(['ID', 'Institution code', 'Institution', 'Reference', 'Bank', 'Amount INR',
                     'Issue date', 'Maturity date', 'Review status', 'Lifecycle',
                     'Evaluation date', 'Days remaining', 'Reminder band days', 'Bank verification'])
    for item in records.iterator():
        maturity = classify_maturity(item.maturity_date, as_of)
        lifecycle = ('Released' if item.is_released else 'Superseded' if item.is_superseded
                     else 'Current' if item.is_current else 'Not accepted')
        writer.writerow([item.pk, *map(spreadsheet_text, [item.institution.code, item.institution.name,
                         item.reference, item.bank]), format(item.amount, '.2f'),
                         item.issue_date.isoformat(), item.maturity_date.isoformat(), item.status,
                         lifecycle, as_of.isoformat(), maturity.days_remaining,
                         maturity.reminder_band if item.is_current and maturity.reminder_band else '',
                         'Not verified by bank'])
    response = HttpResponse('\ufeff' + output.getvalue(), content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = 'attachment; filename="instrument-register.csv"'
    response['X-Content-Type-Options'] = 'nosniff'
    return response
