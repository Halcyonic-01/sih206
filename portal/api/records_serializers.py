from decimal import Decimal
from rest_framework import serializers

from obligations.models import DepositObligation
from portal.models import Document, Instrument


class RecordWrite(serializers.Serializer):
    version = serializers.IntegerField(min_value=1, required=False)
    predecessor_version = serializers.IntegerField(min_value=1, required=False)
    reference = serializers.CharField(max_length=100, required=False)
    bank = serializers.CharField(max_length=200, required=False)
    amount = serializers.DecimalField(max_digits=14, decimal_places=2, min_value=Decimal('0.01'), required=False)
    issue_date = serializers.DateField(required=False)
    maturity_date = serializers.DateField(required=False)
    mode = serializers.ChoiceField(choices=Instrument.Mode.choices, required=False)
    ifsc = serializers.RegexField(r'\A[A-Z]{4}0[A-Z0-9]{6}\Z', max_length=11, allow_blank=True, required=False)
    branch = serializers.CharField(max_length=200, allow_blank=True, required=False)
    holder_names = serializers.CharField(max_length=500, allow_blank=True, required=False)
    utr = serializers.CharField(max_length=100, allow_blank=True, required=False)
    lien_marked = serializers.BooleanField(allow_null=True, required=False)
    obligation_id = serializers.IntegerField(min_value=1, allow_null=True, required=False)
    document = serializers.FileField(required=False)
    renewal_reason = serializers.ChoiceField(choices=['ROUTINE_RENEWAL', 'BANK_MERGER_REPLACEMENT', 'BANK_REISSUE', 'OTHER'], required=False)
    renewal_note = serializers.CharField(max_length=300, allow_blank=True, required=False)

    def validate(self, values):
        forbidden = {'institution', 'institution_id', 'created_by', 'verification_level', 'status',
                     'released_at', 'superseded_at'} & set(self.initial_data)
        if forbidden:
            raise serializers.ValidationError('Ownership, verification and workflow fields are server-controlled.')
        item = self.context.get('item')
        if item and 'version' not in values:
            raise serializers.ValidationError({'version': 'A current version is required.'})
        for field in ['reference', 'bank', 'amount', 'issue_date', 'maturity_date']:
            if field not in values:
                if item:
                    values[field] = getattr(item, field)
                else:
                    raise serializers.ValidationError({field: 'This field is required.'})
        if values['maturity_date'] < values['issue_date']:
            raise serializers.ValidationError({'maturity_date': 'Maturity cannot precede issue date.'})
        if 'obligation_id' in values:
            pk = values.pop('obligation_id')
            obligation = DepositObligation.objects.filter(pk=pk,
                institution_id=self.context['institution_id']).first() if pk else None
            if pk and obligation is None:
                raise serializers.ValidationError({'obligation_id': 'Choose an obligation belonging to this institution.'})
            values['obligation'] = obligation
        mode = values.get('mode', item.mode if item else 'FDR')
        utr = values.get('utr', item.utr if item else '')
        if mode == 'RTGS' and not utr:
            raise serializers.ValidationError({'utr': 'A payment reference is required for RTGS records.'})
        return values


class ActionInput(serializers.Serializer):
    version = serializers.IntegerField(min_value=1)
    decision = serializers.ChoiceField(choices=['accept', 'changes'], required=False)
    reason = serializers.CharField(max_length=2000, required=False)
    resolution = serializers.CharField(max_length=2000, required=False)
    document = serializers.IntegerField(min_value=1, required=False)
    page_number = serializers.IntegerField(min_value=1, allow_null=True, required=False)
    severity = serializers.ChoiceField(choices=['WARNING', 'BLOCKING'], required=False)
    comment = serializers.CharField(max_length=2000, required=False)


class UploadInput(serializers.Serializer):
    version = serializers.IntegerField(min_value=1)
    document = serializers.FileField()
    kind = serializers.ChoiceField(choices=Document.Kind.choices)
