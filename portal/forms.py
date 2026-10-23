from decimal import Decimal

from django import forms

from .models import Document, Instrument, ReviewObservation
from .uploads import validate_pdf_upload


class InstrumentForm(forms.ModelForm):
    amount = forms.DecimalField(label='Deposit amount (INR)', min_value=Decimal('0.01'),
                                max_digits=14, decimal_places=2)
    document = forms.FileField(label='FDR PDF (optional for a draft)', required=False)
    version = forms.IntegerField(widget=forms.HiddenInput, required=False, min_value=1)

    class Meta:
        model = Instrument
        fields = ['reference', 'bank', 'amount', 'issue_date', 'maturity_date']
        widgets = {'issue_date': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
                   'maturity_date': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d')}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            self.fields['version'].required = True
            self.initial['amount'] = self.instance.amount
            self.initial['version'] = self.instance.version

    def clean(self):
        cleaned = super().clean()
        issue, maturity = cleaned.get('issue_date'), cleaned.get('maturity_date')
        if issue and maturity and maturity < issue:
            self.add_error('maturity_date', 'Maturity date cannot precede issue date.')
        return cleaned

    def clean_document(self):
        return validate_pdf_upload(self.cleaned_data.get('document'))


class SubmitForm(forms.Form):
    version = forms.IntegerField(min_value=1, widget=forms.HiddenInput)


class RenewalForm(InstrumentForm):
    predecessor_version = forms.IntegerField(min_value=1, widget=forms.HiddenInput)


class ReviewForm(SubmitForm):
    decision = forms.ChoiceField(choices=[('accept', 'Accept for tracking'),
                                         ('changes', 'Request corrections')])
    reason = forms.CharField(max_length=2000, strip=True, widget=forms.Textarea(attrs={'rows': 4}))


class ObservationForm(SubmitForm):
    document = forms.ModelChoiceField(queryset=Document.objects.none())
    page_number = forms.IntegerField(required=False, min_value=1, max_value=2147483647,
                                    help_text='Optional, counted from page 1. Entered manually; page count is not verified.')
    severity = forms.ChoiceField(choices=ReviewObservation.Severity.choices,
                                initial=ReviewObservation.Severity.BLOCKING)
    comment = forms.CharField(max_length=2000, strip=True, widget=forms.Textarea(attrs={'rows': 4}))

    def __init__(self, *args, instrument, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['document'].queryset = instrument.documents.all()


class ResolutionForm(SubmitForm):
    resolution = forms.CharField(max_length=2000, strip=True,
                                 widget=forms.Textarea(attrs={'rows': 3}),
                                 help_text='Explain how the observation was checked and resolved.')


class ReleaseRequestForm(SubmitForm):
    reason = forms.CharField(max_length=2000, strip=True, widget=forms.Textarea(attrs={'rows': 3}))


class ReleaseDecisionForm(SubmitForm):
    decision = forms.ChoiceField(choices=[('approve', 'Authorize release'), ('reject', 'Reject request')])
    reason = forms.CharField(label='Decision reason', max_length=2000, strip=True,
                             widget=forms.Textarea(attrs={'rows': 3}))


class ReleaseCompletionForm(SubmitForm):
    notes = forms.CharField(label='Completion explanation', max_length=2000, strip=True,
                            widget=forms.Textarea(attrs={'rows': 3}))
    document = forms.FileField(label='New completion evidence PDF (required)')

    def clean_document(self):
        return validate_pdf_upload(self.cleaned_data['document'])
