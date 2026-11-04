from rest_framework import serializers
from .models import (
    Prescription, StaffMember, Equipment, StockItem,
    EmployeeProfile, Machine, Inventory, PartnerClinic, InventoryTransaction,
)
import math
from .workflow import workflow_steps, next_status, LABELS
from django.utils import timezone
from copy import copy


class EmployeeProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmployeeProfile
        fields = ['id', 'user', 'role', 'contract_type', 'hire_date', 'is_available']
        read_only_fields = ['id']


class MachineSerializer(serializers.ModelSerializer):
    class Meta:
        model = Machine
        fields = ['id', 'name', 'machine_type', 'capacity', 'status']
        read_only_fields = ['id']


class InventorySerializer(serializers.ModelSerializer):
    is_low_stock = serializers.BooleanField(read_only=True)

    class Meta:
        model = Inventory
        fields = ['id', 'material_name', 'quantity', 'unit', 'alert_threshold', 'unit_cost', 'is_low_stock']
        read_only_fields = ['id']

    def validate_quantity(self, value):
        if self.instance and value != self.instance.quantity:
            raise serializers.ValidationError('Use an inventory transaction to change the balance.')
        if not math.isfinite(value):
            raise serializers.ValidationError('Quantity must be finite.')
        return value

    def validate_unit(self, value):
        if self.instance and value != self.instance.unit:
            raise serializers.ValidationError('The unit cannot change after an opening ledger entry.')
        return value

    def validate_alert_threshold(self, value):
        if not math.isfinite(value):
            raise serializers.ValidationError('Alert threshold must be finite.')
        return value


class PartnerClinicSerializer(serializers.ModelSerializer):
    class Meta:
        model = PartnerClinic
        fields = ['id', 'name', 'pickup_address', 'contact_phone', 'contact_email', 'linked_dentist', 'platform_dentist']
        read_only_fields = ['id']

    def validate_platform_dentist(self, value):
        if value and (value.role != 'DENTIST' or not value.is_active):
            raise serializers.ValidationError('Choose an active platform dentist account.')
        return value


class InventoryTransactionSerializer(serializers.ModelSerializer):
    idempotency_key = serializers.UUIDField()
    quantity_changed = serializers.DecimalField(max_digits=20, decimal_places=6, required=False)
    transaction_type = serializers.ChoiceField(choices=['USAGE', 'RESTOCK', 'REWORK_LOSS', 'REVERSAL'])

    class Meta:
        model = InventoryTransaction
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'changed_by', 'production_attempt', 'source_history',
                            'reclassifies', 'unit_snapshot', 'material_name_snapshot', 'unit_cost_snapshot', 'balance_after']
        validators = []  # Command idempotency is checked under a database lock, including payload equality.

    def validate(self, attrs):
        source = attrs.get('reversal_of')
        if attrs['transaction_type'] == 'REVERSAL':
            if source is None:
                raise serializers.ValidationError({'reversal_of': 'A source movement is required.'})
            if source.inventory_item_id != attrs['inventory_item'].pk:
                raise serializers.ValidationError({'inventory_item': 'The correction must use the source inventory item.'})
            attrs['quantity_changed'] = -source.quantity_changed
            attrs['prescription'] = source.prescription
        elif source:
            raise serializers.ValidationError({'reversal_of': 'Only REVERSAL may reference a correction source.'})
        if 'quantity_changed' not in attrs:
            raise serializers.ValidationError({'quantity_changed': 'This field is required.'})
        return attrs

    def create(self, validated_data):
        from django.core.exceptions import ValidationError as DjangoValidationError
        from django.db import IntegrityError
        from .inventory import record_movement
        try:
            return record_movement(**validated_data, changed_by=PrescriptionSerializer._audit_actor(self))
        except DjangoValidationError as exc:
            raise serializers.ValidationError(getattr(exc, 'message_dict', exc.messages)) from exc
        except IntegrityError as exc:
            raise serializers.ValidationError('Conflicting movement or invalid inventory correction.') from exc


class StaffMemberSerializer(serializers.ModelSerializer):
    class Meta:
        model = StaffMember
        fields = '__all__'

    def validate(self, attrs):
        status = attrs.get('account_status', getattr(self.instance, 'account_status', 'A_CREER'))
        username = attrs.get('account_username', getattr(self.instance, 'account_username', ''))
        if status == 'ACTIF' and not username.strip():
            raise serializers.ValidationError({'account_username': 'Renseignez un identifiant pour un compte actif.'})
        return attrs


class EquipmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Equipment
        fields = '__all__'


class StockItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = StockItem
        fields = '__all__'
        read_only_fields = ['updated_at']

    def validate(self, attrs):
        received = attrs.get('received_date', getattr(self.instance, 'received_date', None))
        expiry = attrs.get('expiry_date', getattr(self.instance, 'expiry_date', None))
        if received and expiry and expiry < received:
            raise serializers.ValidationError({'expiry_date': 'La péremption doit être postérieure ou égale à la réception.'})
        return attrs


from .case_serializers import PrescriptionSerializer  # noqa: E402,F401
