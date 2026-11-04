from decimal import Decimal
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.utils import timezone
from rest_framework import serializers

from customers.models import PlatformAccount
from .models import ClinicalItem, Prescription
from .permissions import actor_role
from .pricing import price_items
from .signals import prescription_audit_context
from .workflow import LABELS, next_status, workflow_steps


def actor_identity(request):
    if request is None:
        return 'system'
    user = request.user
    if isinstance(user, PlatformAccount):
        return f'platform:{user.pk}:{user.name}'[:255]
    return f'user:{user.pk}:{user.get_username()}'[:255]


class ClinicalItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = ClinicalItem
        fields = ['id', 'tooth_number', 'function', 'form', 'shade', 'material', 'base_amount']
        read_only_fields = ['id', 'base_amount']

    def validate_tooth_number(self, value):
        quadrant, tooth = divmod(value, 10)
        if not ((1 <= quadrant <= 4 and 1 <= tooth <= 8) or (5 <= quadrant <= 8 and 1 <= tooth <= 5)):
            raise serializers.ValidationError('Use a valid FDI tooth number.')
        return value


class PrescriptionSerializer(serializers.ModelSerializer):
    clinical_items = ClinicalItemSerializer(many=True, required=False)
    action_notes = serializers.CharField(write_only=True, required=False, allow_blank=True, max_length=2000)
    workflow_steps = serializers.SerializerMethodField()
    next_status = serializers.SerializerMethodField()
    status_label = serializers.SerializerMethodField()
    quote_required = serializers.SerializerMethodField()

    class Meta:
        model = Prescription
        exclude = ['delivery_pin', 'delivery_pin_hash', 'qr_nonce', 'pin_attempts', 'pin_locked_until']
        read_only_fields = [
            'id', 'created_at', 'updated_at', 'workflow_history', 'accepted_at', 'received_at', 'dentist_account',
            'invoiced_at', 'invoiced_amount', 'invoiced_clinic_name', 'production_attempt', 'state_version',
            'intake_version', 'intake_revision', 'automatic_deadline', 'deadline_at', 'deadline_calculated_at',
            'pause_started_at', 'deadline_suspended_seconds', 'delivered_at', 'fitting_validated_at',
            'base_amount', 'express_surcharge', 'manual_surcharge', 'total_price', 'workstation_notes', 'rework_restart_status',
        ]
        extra_kwargs = {'tooth_number': {'required': False}, 'shade': {'required': False}, 'material': {'required': False}}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance is None:
            for name in ['status', 'delivery_date', 'billing_stage', 'production_method', 'thermal_treatment',
                         'analysis_validated', 'reception_validated', 'quality_validated', 'accepted',
                         'is_paused', 'pause_reason', 'current_issues', 'technical_notes']:
                self.fields[name].read_only = True

    def get_workflow_steps(self, obj):
        return workflow_steps(obj)

    def get_next_status(self, obj):
        return next_status(obj)

    def get_status_label(self, obj):
        return LABELS.get(obj.status, obj.status)

    def get_quote_required(self, obj):
        return obj.total_price is None

    def _audit_actor(self):
        return actor_identity(self.context.get('request'))

    def to_representation(self, instance):
        data = super().to_representation(instance)
        request = self.context.get('request')
        if request and actor_role(request) != 'MANAGER':
            role = actor_role(request)
            data['workstation_notes'] = {role: data['workstation_notes'][role]} if role in data.get('workstation_notes', {}) else {}
        return data

    def validate(self, attrs):
        request = self.context.get('request')
        role = actor_role(request) if request else 'SYSTEM'
        if self.instance is None:
            if attrs.get('disinfected') is not True:
                raise serializers.ValidationError({'disinfected': 'Explicit disinfection confirmation is required.'})
            items = attrs.get('clinical_items')
            if not items:
                raise serializers.ValidationError({'clinical_items': 'Add at least one tooth with function, form, shade and material.'})
            if len(items) > 32 or len({x['tooth_number'] for x in items}) != len(items):
                raise serializers.ValidationError({'clinical_items': 'Use distinct teeth; maximum 32 items.'})
            service = attrs.get('delivery_service', 'EXPRESS' if attrs.get('is_fast_track') else 'STANDARD')
            attrs['delivery_service'] = service
            attrs['is_fast_track'] = service != 'STANDARD'
            try:
                base, surcharge = price_items(items, service)
            except DjangoValidationError as exc:
                raise serializers.ValidationError(exc.messages) from exc
            attrs['base_amount'], attrs['express_surcharge'] = base, surcharge or Decimal('0')
            attrs['total_price'] = base + surcharge if surcharge is not None else None
            attrs.update({field: items[0][field] for field in ['tooth_number', 'shade', 'material']})
            clinic = attrs.get('partner_clinic')
            if not clinic:
                raise serializers.ValidationError({'partner_clinic': 'Choose a verified partner clinic with a pickup address.'})
            if request and isinstance(request.user, PlatformAccount) and request.user.role == 'DENTIST':
                if clinic.platform_dentist_id != request.user.pk:
                    raise serializers.ValidationError({'partner_clinic': 'This clinic does not belong to your account.'})
            if not clinic.pickup_address.strip():
                raise serializers.ValidationError({'partner_clinic': 'A pickup address is required.'})
            return attrs
        if 'clinical_items' in attrs:
            raise serializers.ValidationError({'clinical_items': 'Submitted clinical items are immutable. Create a documented revision.'})
        if role == 'COURIER':
            raise serializers.ValidationError('Use the courier QR and delivery commands.')
        permitted = {
            'MANAGER': {'status', 'accepted', 'analysis_validated', 'reception_validated', 'quality_validated',
                        'production_method', 'thermal_treatment', 'delivery_date', 'technical_notes', 'current_issues', 'action_notes'},
            'RECEPTION': {'status', 'accepted', 'analysis_validated', 'reception_validated', 'production_method',
                          'thermal_treatment', 'delivery_date', 'technical_notes', 'current_issues', 'action_notes'},
            'CAO': {'status', 'technical_notes', 'action_notes'}, 'FAO': {'status', 'technical_notes', 'action_notes'},
            'QUALITE': {'status', 'quality_validated', 'technical_notes', 'action_notes'},
            'SYSTEM': set(attrs),
        }
        forbidden = set(attrs) - permitted.get(role, set())
        if forbidden:
            raise serializers.ValidationError({field: 'Use the authorized workflow command for this field.' for field in forbidden})
        return attrs

    def create(self, validated_data):
        items = validated_data.pop('clinical_items')
        notes = validated_data.pop('action_notes', '')
        request = self.context.get('request')
        with transaction.atomic(), prescription_audit_context(self._audit_actor(), notes, {'role': actor_role(request) if request else 'SYSTEM'}):
            order = Prescription.objects.create(**validated_data)
            for item in items:
                ClinicalItem.objects.create(prescription=order, **item)
            return order

    def update(self, instance, validated_data):
        notes = validated_data.pop('action_notes', '')
        if validated_data.get('accepted') and not instance.accepted:
            validated_data['accepted_at'] = timezone.now()
        if validated_data.get('reception_validated') and not instance.reception_validated:
            validated_data['received_at'] = timezone.now()
        if 'status' in validated_data and validated_data['status'] != instance.status:
            validated_data['workflow_history'] = [*instance.workflow_history, {'status': validated_data['status'], 'at': timezone.now().isoformat()}]
        request = self.context.get('request')
        try:
            with prescription_audit_context(self._audit_actor(), notes, {'role': actor_role(request) if request else 'SYSTEM'}):
                return super().update(instance, validated_data)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(getattr(exc, 'message_dict', exc.messages)) from exc


class CourierPrescriptionSerializer(serializers.ModelSerializer):
    clinic_name = serializers.CharField(source='partner_clinic.name', default='')
    pickup_address = serializers.CharField(source='partner_clinic.pickup_address', default='')
    contact_phone = serializers.CharField(source='partner_clinic.contact_phone', default='')

    class Meta:
        model = Prescription
        fields = ['id', 'patient_ref', 'dentist_name', 'status', 'delivery_date', 'clinic_name', 'pickup_address', 'contact_phone', 'created_at', 'updated_at']
