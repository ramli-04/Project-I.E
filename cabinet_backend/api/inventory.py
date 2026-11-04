"""Atomic inventory commands. Material consumption is explicit, never inferred from names."""
import uuid

from django.core.exceptions import ValidationError
from django.db import transaction

from .models import Inventory, InventoryTransaction, Prescription

REWORK_STATUSES = {'A_REFAIRE', 'RECOULER'}
REWORK_FROM = {
    'USINAGE_CNC', 'FRITTAGE_9H', 'TRAITEMENT_THERMIQUE', 'IMPRESSION_3D',
    'LAVAGE_SECHAGE', 'POST_POLYMERISATION', 'FABRICATION_MANUELLE',
    'FINITION', 'CONTROLE_QUALITE',
}


def record_movement(*, inventory_item, quantity_changed, transaction_type,
                    idempotency_key, prescription=None, reversal_of=None, production_lot=None, notes='', changed_by='system'):
    with transaction.atomic():
        # Consistent lock order: prescription, then inventory. Rework uses the same order.
        if reversal_of:
            prescription = reversal_of.prescription
        if prescription:
            prescription = Prescription.objects.select_for_update().get(pk=prescription.pk)
        item = Inventory.objects.select_for_update().get(pk=inventory_item.pk)
        existing = InventoryTransaction.objects.filter(idempotency_key=idempotency_key).first()
        if existing:
            if (existing.inventory_item_id != item.pk or existing.prescription_id != getattr(prescription, 'pk', None)
                or existing.quantity_changed != quantity_changed or existing.transaction_type != transaction_type
                or existing.reversal_of_id != getattr(reversal_of, 'pk', None) or existing.notes != notes
                or existing.production_lot_id != getattr(production_lot, 'pk', None)):
                raise ValidationError({'idempotency_key': 'This key already identifies a different movement.'})
            return existing
        if reversal_of:
            if reversal_of.source_history_id or reversal_of.reclassifies_id:
                raise ValidationError('Automatic rework classifications cannot be manually reversed.')
            if InventoryTransaction.objects.filter(reversal_of=reversal_of).exists():
                raise ValidationError('This movement has already been reversed.')
        if transaction_type == 'USAGE' and prescription and prescription.status not in REWORK_FROM | {
            'SALLE_CAO', 'PREPARATION_CNC', 'PREPARATION_3D', 'MODELE_TRAVAIL', 'MODELAGE',
            'COULEE_PLATRE', 'SCAN_LABO', 'CONTROLE_MODELE',
        }:
            raise ValidationError({'prescription': 'Record material usage during a production step.'})
        return InventoryTransaction.objects.create(
            inventory_item=item, prescription=prescription, quantity_changed=quantity_changed,
            transaction_type=transaction_type, idempotency_key=idempotency_key,
            reversal_of=reversal_of, notes=notes, changed_by=changed_by,
            production_lot=production_lot,
        )


def classify_rework(history, using='default'):
    """Reclassify only measured waste. A zero-material correction never deducts stock."""
    from decimal import Decimal, InvalidOperation
    from .models import ReworkCase
    with transaction.atomic(using=using):
        order = Prescription.objects.using(using).select_for_update().get(pk=history.prescription_id)
        if ReworkCase.objects.using(using).filter(history=history).exists():
            return order.production_attempt
        details = history.metadata
        if order.status != history.new_status or details.get('action') != 'REWORK':
            raise ValidationError('Use the explicit, audited rework command.')
        seen, recorded = set(), []
        for loss in details.get('losses', []):
            try:
                usage_id = uuid.UUID(str(loss['usage_id']))
                amount = Decimal(str(loss['quantity']))
            except (KeyError, TypeError, ValueError, InvalidOperation) as exc:
                raise ValidationError('Each measured loss requires a usage UUID and decimal quantity.') from exc
            if not amount.is_finite() or amount < 0 or amount != amount.quantize(Decimal('0.000001')) or usage_id in seen:
                raise ValidationError('Use distinct usages and finite, non-negative quantities with at most six decimal places.')
            seen.add(usage_id)
            usage = InventoryTransaction.objects.using(using).filter(
                pk=usage_id, prescription=order, production_attempt=order.production_attempt,
                transaction_type='USAGE', reversal__isnull=True, loss_classification__isnull=True,
            ).first()
            if usage is None or amount > -usage.quantity_changed:
                raise ValidationError('Loss must reference unreversed consumption from the current attempt and cannot exceed it.')
            if not amount:
                continue
            full = amount == -usage.quantity_changed
            for kind, quantity, references in (
                ('REVERSAL' if full else 'LOSS_OFFSET', amount,
                 {'reversal_of': usage} if full else {'source_usage': usage}),
                ('REWORK_LOSS', -amount, {'reclassifies': usage}),
            ):
                InventoryTransaction.objects.using(using).create(
                    inventory_item_id=usage.inventory_item_id, prescription=order,
                    quantity_changed=quantity, transaction_type=kind, source_history=history,
                    notes=details['cause'] + '; ' + details['corrective_action'], changed_by=history.changed_by,
                    idempotency_key=uuid.uuid5(uuid.NAMESPACE_URL, f'rework:{history.pk}:{usage.pk}:{kind}'),
                    production_lot_id=usage.production_lot_id, **references,
                )
            recorded.append({'usage_id': str(usage_id), 'quantity': str(amount)})
        ReworkCase.objects.using(using).create(
            prescription=order, history=history, attempt=order.production_attempt,
            origin=details['origin'], cause_step=details['cause_step'], restart_status=details['restart_status'],
            cause=details['cause'], action=details['corrective_action'], losses=recorded,
        )
        order.production_attempt += 1
        order.quality_validated = False
        order.save(using=using, update_fields=['production_attempt', 'quality_validated', 'updated_at'])
        return order.production_attempt


def assess_rework_loss(order, attempt, losses, changed_by='system', notes='', using='default'):
    """Assess material waste for an existing rework case without double deduction or altering attempt."""
    from decimal import Decimal, InvalidOperation
    from .models import ReworkCase
    with transaction.atomic(using=using):
        order = Prescription.objects.using(using).select_for_update().get(pk=order.pk)
        rework = ReworkCase.objects.using(using).filter(prescription=order, attempt=attempt).first()
        if rework is None:
            raise ValidationError(f'No rework record found for attempt {attempt}.')
        history = rework.history
        seen, recorded = set(), []
        for loss in losses:
            try:
                usage_id = uuid.UUID(str(loss['usage_id']))
                amount = Decimal(str(loss['quantity']))
            except (KeyError, TypeError, ValueError, InvalidOperation) as exc:
                raise ValidationError('Each measured loss requires a usage UUID and decimal quantity.') from exc
            if not amount.is_finite() or amount <= 0 or amount != amount.quantize(Decimal('0.000001')) or usage_id in seen:
                raise ValidationError('Use distinct usages and positive quantities with at most six decimal places.')
            seen.add(usage_id)
            usage = InventoryTransaction.objects.using(using).filter(
                pk=usage_id, prescription=order, production_attempt=attempt,
                transaction_type='USAGE', reversal__isnull=True, loss_classification__isnull=True,
            ).first()
            if usage is None or amount > -usage.quantity_changed:
                raise ValidationError(f'Loss must reference unreversed consumption from attempt {attempt} and cannot exceed it.')
            full = amount == -usage.quantity_changed
            for kind, quantity, references in (
                ('REVERSAL' if full else 'LOSS_OFFSET', amount,
                 {'reversal_of': usage} if full else {'source_usage': usage}),
                ('REWORK_LOSS', -amount, {'reclassifies': usage}),
            ):
                InventoryTransaction.objects.using(using).create(
                    inventory_item_id=usage.inventory_item_id, prescription=order,
                    quantity_changed=quantity, transaction_type=kind, source_history=history,
                    notes=notes or (rework.cause + '; ' + rework.action), changed_by=changed_by,
                    idempotency_key=uuid.uuid5(uuid.NAMESPACE_URL, f'assess-loss:{rework.pk}:{usage.pk}:{kind}'),
                    production_lot_id=usage.production_lot_id, **references,
                )
            recorded.append({'usage_id': str(usage_id), 'quantity': str(amount)})
        return recorded