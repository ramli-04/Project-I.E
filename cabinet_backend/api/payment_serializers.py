from decimal import Decimal

from rest_framework import serializers

from .models import PartnerClinic, FinanceInvoice, Payment, PaymentAllocation, PaymentReversal

AMOUNT_ERROR = 'Payments require a positive cent-precise amount.'


def amount_field():
    return serializers.DecimalField(max_digits=16, decimal_places=2, min_value=Decimal('0.01'),
        error_messages={key: AMOUNT_ERROR for key in ['invalid', 'max_digits', 'max_decimal_places', 'max_whole_digits', 'min_value']})


class AllocationInput(serializers.Serializer):
    invoice = serializers.PrimaryKeyRelatedField(queryset=FinanceInvoice.objects.all(),
        error_messages={'does_not_exist': 'Choose an invoice from this laboratory.', 'incorrect_type': 'Choose an invoice from this laboratory.'})
    amount = amount_field()


class PaymentInput(serializers.Serializer):
    clinic = serializers.PrimaryKeyRelatedField(queryset=PartnerClinic.objects.all(),
        error_messages={'does_not_exist': 'Choose a clinic from this laboratory.', 'incorrect_type': 'Choose a clinic from this laboratory.'})
    method = serializers.ChoiceField(choices=Payment._meta.get_field('method').choices, error_messages={'invalid_choice': 'Choose a payment method.'})
    amount = amount_field()
    received_on = serializers.DateField(error_messages={'invalid': 'Choose a valid payment date.'})
    due_on = serializers.DateField(required=False, allow_null=True, default=None, error_messages={'invalid': 'Choose a valid payment date.'})
    reference = serializers.CharField(max_length=60, required=False, allow_blank=True, default='')
    bank = serializers.CharField(max_length=80, required=False, allow_blank=True, default='')
    notes = serializers.CharField(required=False, allow_blank=True, default='')
    allocations = AllocationInput(many=True, allow_empty=False)

    def validate(self, attrs):
        if attrs['method'] != 'ESPECES' and not attrs['reference']:
            raise serializers.ValidationError('Reference is required for this payment method.')
        if attrs['method'] == 'LCN' and attrs['due_on'] is None:
            raise serializers.ValidationError('An LCN maturity date is required.')
        return attrs


class AllocationSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaymentAllocation
        fields = ['invoice', 'amount']


class ReversalSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaymentReversal
        fields = ['id', 'reason', 'notes', 'reversed_by', 'reversed_at']


class PaymentSerializer(serializers.ModelSerializer):
    allocations = AllocationSerializer(many=True, read_only=True)
    reversal = ReversalSerializer(read_only=True)

    class Meta:
        model = Payment
        fields = ['id', 'clinic', 'method', 'amount', 'received_on', 'due_on', 'reference', 'bank', 'notes',
                  'recorded_by', 'created_at', 'allocations', 'reversal']


class ReceivablesSerializer(serializers.Serializer):
    clinic = serializers.IntegerField()
    terms_days = serializers.IntegerField()
    total_due = serializers.DecimalField(max_digits=28, decimal_places=2)
    not_due = serializers.DecimalField(max_digits=28, decimal_places=2)
    overpaid_amount = serializers.DecimalField(max_digits=28, decimal_places=2)
    buckets = serializers.DictField(child=serializers.DecimalField(max_digits=28, decimal_places=2))
    oldest_overdue_days = serializers.IntegerField()
