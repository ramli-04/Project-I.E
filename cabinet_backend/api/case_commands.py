"""Transactional BPMN commands. Caller role comes from authentication, never request JSON."""
import hashlib
import json
import uuid
from datetime import timedelta
from decimal import Decimal

from django.core import signing
from django.contrib.auth.hashers import check_password, make_password
from django.core.exceptions import ValidationError
from django.db import connection, transaction
from django.utils import timezone

from .models import (Prescription, CaseCommandReceipt, CaseInspection, CaseAttachment, DesignReview,
                     CaseNotification, MessageDelivery, WorkflowEvent, BillingDispute, StatementLine)
from .domain import latest_inspection, REWORK_ORIGINS
from .signals import prescription_audit_context
from .workflow import next_status

CHECKS = {
    'PHYSICAL': {'deformation', 'bubbles', 'limits', 'occlusion', 'hygiene'},
    'DIGITAL': {'margins', 'occlusion', 'space', 'scan_quality'},
    'MODEL': {'model', 'scan'},
    'QUALITY': {'margins', 'contacts', 'shade', 'occlusion', 'cosmetic', 'glazing', 'polishing'},
}


def notify(order, kind, payload, key=None):
    notification, created = CaseNotification.objects.get_or_create(
        event_key=key or f'{kind}:{order.pk}:{uuid.uuid4()}',
        defaults={'prescription': order, 'kind': kind, 'payload': payload},
    )
    if created:
        clinic = order.partner_clinic
        destinations = [('EMAIL', clinic.contact_email if clinic else ''), ('WHATSAPP', clinic.contact_phone if clinic else '')]
        if not destinations[0][1] and order.dentist_account_id:
            destinations[0] = ('EMAIL', order.dentist_account.email)
        for channel, destination in destinations:
            if destination:
                MessageDelivery.objects.get_or_create(notification=notification, channel=channel, destination=destination)
    return notification


def qr_token(order):
    return signing.dumps({'schema': connection.schema_name, 'case': str(order.pk), 'nonce': str(order.qr_nonce)},
                         salt='case-qr-v1', compress=True)


def verify_qr(order, token):
    try:
        data = signing.loads(token, salt='case-qr-v1', max_age=365 * 86400)
    except (signing.BadSignature, TypeError, ValueError) as exc:
        raise ValidationError('Invalid or expired QR code.') from exc
    if data != {'schema': connection.schema_name, 'case': str(order.pk), 'nonce': str(order.qr_nonce)}:
        raise ValidationError('QR code belongs to a different laboratory or case.')


def set_pause(order, paused, reason=''):
    now = timezone.now()
    if paused and not order.is_paused:
        order.pause_started_at = now
    elif not paused and order.pause_started_at:
        order.deadline_suspended_seconds += max(0, int((now - order.pause_started_at).total_seconds()))
        order.pause_started_at = None
    order.is_paused, order.pause_reason = paused, reason if paused else ''


def change_status(order, status):
    if order.status != status:
        order.workflow_history = [*order.workflow_history, {'status': status, 'at': timezone.now().isoformat()}]
    order.status = status


def execute_case_command(order_id, command, data, actor, role, idempotency_key):
    try:
        key = uuid.UUID(str(idempotency_key))
    except (ValueError, TypeError, AttributeError) as exc:
        raise ValidationError('A UUID Idempotency-Key is required.') from exc
    digest = hashlib.sha256(json.dumps({'command': command, 'data': data}, sort_keys=True, default=str).encode()).hexdigest()
    with transaction.atomic():
        if command in {'confirm-delivery', 'rework', 'dispute', 'assess-loss'}:
            from .billing import billing_lock
            clinic_id = Prescription.objects.values_list('partner_clinic_id', flat=True).get(pk=order_id)
            if clinic_id:
                billing_lock(clinic_id)
        order = Prescription.objects.select_for_update().get(pk=order_id)
        prior = CaseCommandReceipt.objects.filter(pk=key).first()
        if prior:
            if prior.prescription_id != order.pk or prior.command != command or prior.payload_digest != digest:
                raise ValidationError('This idempotency key belongs to a different command.')
            return order, prior.result
        metadata = {'role': role, 'action': command.upper()}
        result = {}
        with prescription_audit_context(actor, str(data.get('notes', ''))[:2000], metadata):
            result = _execute(order, command, data, actor, role, metadata)
        saved_result = {k: v for k, v in result.items() if k != 'pin_once'}
        CaseCommandReceipt.objects.create(idempotency_key=key, prescription=order, command=command,
                                          payload_digest=digest, result=saved_result)
        return order, result


def allowed(role, roles):
    if role not in roles | {'MANAGER'}:
        raise ValidationError('Your role cannot perform this command.')


def _execute(order, command, data, actor, role, metadata):
    # Update the context dictionary in place; the signal reads this same transaction's metadata.
    from .signals import _workflow_metadata
    metadata = _workflow_metadata.get()
    if command == 'inspection':
        allowed(role, {'RECEPTION', 'QUALITE', 'CAO'})
        stage, checks = data.get('stage'), data.get('checks')
        if stage not in CHECKS or not isinstance(checks, dict) or not CHECKS[stage] <= checks.keys():
            raise ValidationError('Supply every required check for a valid inspection stage.')
        if any(type(checks[k]) is not bool for k in CHECKS[stage]):
            raise ValidationError('Inspection checks must be booleans.')
        permitted = {'PHYSICAL': {'A_CONFIRMER', 'CONTROLE_DOSSIER'}, 'DIGITAL': {'A_CONFIRMER', 'CONTROLE_DOSSIER'},
                     'MODEL': {'CONTROLE_MODELE'}, 'QUALITY': {'CONTROLE_QUALITE'}}
        if order.status not in permitted[stage]:
            raise ValidationError('This inspection does not match the current workflow step.')
        if (stage == 'PHYSICAL' and order.impression_type != 'PHYSIQUE') or (stage == 'DIGITAL' and order.impression_type != 'NUMERIQUE'):
            raise ValidationError('Inspection track does not match the case.')
        if stage == 'DIGITAL' and not order.attachments.filter(kind='STL').exists():
            raise ValidationError('Upload the actual STL file before its inspection.')
        passed = all(checks[k] for k in CHECKS[stage])
        photo = None
        if data.get('photo'):
            photo = CaseAttachment.objects.filter(pk=data['photo'], prescription=order, kind='PHOTO').first()
            if photo is None:
                raise ValidationError('Choose a photograph from this case.')
        if (not passed or checks.get('gap') is True) and photo is None:
            raise ValidationError('A failed inspection or gap requires photographic evidence.')
        if not passed and not str(data.get('notes', '')).strip():
            raise ValidationError('Describe the non-compliance reason.')
        inspection = CaseInspection.objects.create(prescription=order, stage=stage, checks=checks, passed=passed,
            photo=photo, notes=str(data.get('notes', ''))[:4000], checked_by=actor,
            production_attempt=order.production_attempt, intake_revision=order.intake_revision)
        if stage == 'QUALITY':
            order.quality_validated = passed
        if not passed:
            notify(order, 'INSPECTION_FAILED', {'inspection': inspection.pk, 'stage': stage, 'notes': inspection.notes,
                                               'photo': str(photo.pk)})
            if stage in {'PHYSICAL', 'DIGITAL'}:
                metadata['action'] = 'INSPECTION_FAILED'
                change_status(order, 'RETOUR_DEMANDE')
            # Model/quality failures stay at their checkpoint until an explicit, measured rework command.
        order.save()
        return {'inspection_id': inspection.pk, 'passed': passed}
    if command == 'rework':
        allowed(role, {'RECEPTION', 'CAO', 'FAO', 'QUALITE', 'DENTIST'})
        if order.status not in REWORK_ORIGINS:
            raise ValidationError('This case is not at a rework-capable step.')
        if role == 'DENTIST' and order.status not in {'LIVRE', 'ESSAYAGE', 'CLOTURE'}:
            raise ValidationError('Dentists report remakes after delivery/fitting.')
        origin, cause, action = data.get('origin'), str(data.get('cause', '')).strip(), str(data.get('corrective_action', '')).strip()
        restart = data.get('restart_status')
        if origin not in {'LAB', 'CLINIC'} or not cause or not action:
            raise ValidationError('Origin, cause and corrective action are mandatory.')
        valid = {'SALLE_CAO', 'FINITION'}
        valid.add({'CFAO': 'PREPARATION_CNC', 'IMPRESSION_3D': 'PREPARATION_3D', 'CONVENTIONNEL': 'MODELAGE'}.get(order.production_method, 'COULEE_PLATRE'))
        if order.impression_type == 'PHYSIQUE':
            valid |= {'COULEE_PLATRE', 'SCAN_LABO'}
        if restart not in valid:
            raise ValidationError('Choose a responsible restart step from this production route.')
        losses = data.get('losses', [])
        if not isinstance(losses, list) or len(losses) > 100:
            raise ValidationError('Supply a bounded list of measured losses; use [] for a zero-material correction.')
        metadata.update({'action': 'REWORK', 'origin': origin, 'cause': cause, 'corrective_action': action,
                         'restart_status': restart, 'losses': losses, 'cause_step': order.status})
        order.rework_restart_status = restart
        set_pause(order, False)
        change_status(order, 'RECOULER' if restart == 'COULEE_PLATRE' else 'RESCANNER' if restart == 'SCAN_LABO' else 'A_REFAIRE')
        order.save()
        notify(order, 'REWORK', {'origin': origin, 'cause': cause, 'action': action, 'restart_status': restart,
                               'original_case_id': str(order.pk), 'attempt': order.production_attempt})
        line = StatementLine.objects.filter(prescription=order).select_related('period').first()
        if line and line.period.closed_at is None:
            line.contested, line.dispute_reason = True, cause
            line.save(update_fields=['contested', 'dispute_reason'])
        return {'original_case_id': str(order.pk), 'attempt': order.production_attempt}
    if command == 'design-request':
        allowed(role, {'CAO'})
        if order.status not in {'SALLE_CAO', 'VALIDATION_CAO'} or not order.design_validation_requested:
            raise ValidationError('Dentist review must be requested on a CAO case.')
        attachment = CaseAttachment.objects.filter(pk=data.get('attachment'), prescription=order, kind='DESIGN').first()
        if not attachment:
            raise ValidationError('Upload a design artifact for this case.')
        if order.design_reviews.filter(status='PENDING').exists():
            raise ValidationError('A design review is already pending.')
        review = DesignReview.objects.create(prescription=order, attachment=attachment,
            version=order.design_reviews.count() + 1, production_attempt=order.production_attempt)
        metadata['action'] = 'DESIGN_REQUEST'
        set_pause(order, True, 'Awaiting dentist design validation')
        change_status(order, 'VALIDATION_CAO')
        order.save()
        notify(order, 'DESIGN_APPROVAL_REQUESTED', {'review_id': str(review.pk), 'version': review.version})
        return {'review_id': str(review.pk)}
    if command == 'design-decision':
        if role != 'DENTIST':
            raise ValidationError('Only the owning dentist can approve or request design changes.')
        review = order.design_reviews.select_for_update().filter(pk=data.get('review'), status='PENDING').first()
        decision = data.get('decision')
        if not review or decision not in {'APPROVED', 'CHANGES_REQUESTED'}:
            raise ValidationError('Choose a pending review and valid design decision.')
        notes = str(data.get('notes', '')).strip()
        if decision == 'CHANGES_REQUESTED' and not notes:
            raise ValidationError('Describe the requested design changes.')
        review.status, review.response_notes, review.responded_at, review.responded_by = decision, notes, timezone.now(), actor
        review.save(update_fields=['status', 'response_notes', 'responded_at', 'responded_by'])
        metadata['action'] = 'DESIGN_DECISION'
        if decision == 'APPROVED':
            set_pause(order, False)
            change_status(order, next_status(order))
        else:
            change_status(order, 'SALLE_CAO')
        order.save()
        notify(order, 'DESIGN_DECISION', {'review_id': str(review.pk), 'decision': decision, 'notes': notes})
        return {'decision': decision}
    if command == 'pause':
        allowed(role, {'RECEPTION', 'CAO', 'FAO', 'QUALITE'})
        paused = data.get('paused')
        if type(paused) is not bool or (paused and not str(data.get('notes', '')).strip()):
            raise ValidationError('Provide paused=true/false and a pause reason.')
        if not paused and order.design_reviews.filter(status='PENDING').exists():
            raise ValidationError('A pending dentist review cannot be bypassed by resuming manually.')
        set_pause(order, paused, str(data.get('notes', '')))
        order.save(update_fields=['is_paused', 'pause_reason', 'pause_started_at', 'deadline_suspended_seconds', 'updated_at'])
        return {'paused': paused}
    if command == 'resubmit':
        allowed(role, {'DENTIST', 'RECEPTION'})
        if order.status != 'RETOUR_DEMANDE':
            raise ValidationError('Only a returned intake can be resubmitted.')
        order.intake_revision += 1
        order.reception_validated = False
        change_status(order, 'A_CONFIRMER')
        metadata['action'] = 'RESUBMIT'
        order.save()
        notify(order, 'INTAKE_RESUBMITTED', {'revision': order.intake_revision})
        return {'revision': order.intake_revision}
    if command in {'pickup', 'lab-deposit', 'checkout'}:
        allowed(role, {'COURIER', 'RECEPTION', 'QUALITE'})
        before, after = {'pickup': ('ATTENTE_RAMASSAGE', 'EN_ROUTE_LABO'), 'lab-deposit': ('EN_ROUTE_LABO', 'A_CONFIRMER'),
                         'checkout': ('PRET_EXPEDITION', 'EN_ROUTE_CABINET')}[command]
        if order.status != before:
            raise ValidationError('This scan does not match the current custody step.')
        verify_qr(order, data.get('qr_token'))
        change_status(order, after)
        order.save()
        notify(order, 'COURIER_' + command.upper(), {'case_id': str(order.pk)})
        return {'scanned': True}
    if command == 'confirm-delivery':
        allowed(role, {'DENTIST', 'COURIER'})
        if order.status != 'EN_ROUTE_CABINET':
            raise ValidationError('Checkout is required before delivery confirmation.')
        now = timezone.now()
        if order.pin_locked_until and order.pin_locked_until > now:
            return {'error': 'PIN temporarily locked. Try again later.', 'http_status': 429}
        pin = data.get('pin', '')
        if not isinstance(pin, str) or len(pin) != 4 or not pin.isdigit() or not check_password(pin, order.delivery_pin_hash):
            order.pin_attempts += 1
            if order.pin_attempts >= 5:
                order.pin_locked_until, order.pin_attempts = now + timedelta(minutes=15), 0
            order.save(update_fields=['pin_attempts', 'pin_locked_until', 'updated_at'])
            return {'error': 'Incorrect delivery PIN.', 'http_status': 400}
        metadata['action'] = 'CONFIRM_DELIVERY'
        order.delivered_at, order.pin_attempts, order.pin_locked_until = now, 0, None
        change_status(order, 'LIVRE')
        order.save()
        from .billing import add_delivered_case
        add_delivered_case(order)
        notify(order, 'DELIVERED', {'delivered_at': now.isoformat()})
        return {'delivered': True}
    if command == 'issue-pin':
        if role != 'DENTIST' or order.status in {'LIVRE', 'ESSAYAGE', 'CLOTURE'}:
            raise ValidationError('Only the owning dentist can issue a delivery PIN before receipt.')
        import secrets
        pin = f'{secrets.randbelow(10000):04d}'
        order.delivery_pin_hash = make_password(pin)
        order.pin_attempts, order.pin_locked_until = 0, None
        order.save(update_fields=['delivery_pin_hash', 'pin_attempts', 'pin_locked_until', 'updated_at'])
        return {'pin_once': pin}
    if command == 'fitting':
        if role != 'DENTIST' or order.status not in {'LIVRE', 'ESSAYAGE'}:
            raise ValidationError('The owning dentist records fitting after delivery.')
        if data.get('passed') is not True:
            raise ValidationError('For failed fitting, use the rework command with origin, cause and action.')
        metadata['action'] = 'FITTING'
        order.fitting_validated_at = timezone.now()
        change_status(order, 'CLOTURE')
        order.save()
        notify(order, 'FITTING_ACCEPTED', {'original_case_id': str(order.pk)})
        return {'passed': True}
    if command == 'quote':
        allowed(role, {'COMPTABILITE'})
        if order.delivery_service != 'NEXT_DAY' or order.invoiced_at or order.status not in {'DEMANDE_RECUE', 'ANALYSE_DEMANDE', 'PLANIFICATION'}:
            raise ValidationError('Manual J+1 quotes are accepted before production/invoicing.')
        from .pricing import price_items
        items = list(order.clinical_items.values('material'))
        base, extra = price_items(items, 'NEXT_DAY', data.get('surcharge'))
        if extra is None:
            raise ValidationError('Provide the manual urgency surcharge.')
        order.manual_surcharge, order.base_amount, order.express_surcharge, order.total_price = extra, base, extra, base + extra
        order.save(update_fields=['manual_surcharge', 'base_amount', 'express_surcharge', 'total_price', 'updated_at'])
        return {'total_price': str(order.total_price)}
    if command == 'note':
        allowed(role, {'RECEPTION', 'CAO', 'FAO', 'QUALITE', 'COMPTABILITE'})
        workstation = data.get('workstation', role)
        if role != 'MANAGER' and workstation != role:
            raise ValidationError('Edit remarks for your workstation only.')
        order.workstation_notes = {**order.workstation_notes, workstation: str(data.get('notes', ''))[:4000]}
        order.save(update_fields=['workstation_notes', 'updated_at'])
        return {'saved': True}
    if command == 'dispute':
        allowed(role, {'DENTIST', 'COMPTABILITE'})
        reason = str(data.get('notes', '')).strip()
        if not reason:
            raise ValidationError('Describe the contested line.')
        line = StatementLine.objects.filter(prescription=order).select_related('period').first()
        invoice = None
        if line:
            if line.period.closed_at:
                invoice = getattr(line.period, 'invoice', None)
            else:
                line.contested, line.dispute_reason = True, reason
                line.save(update_fields=['contested', 'dispute_reason'])
        dispute = BillingDispute.objects.create(prescription=order, invoice=invoice, reason=reason, raised_by=actor)
        notify(order, 'BILLING_DISPUTE', {'dispute': str(dispute.pk), 'reason': reason})
        order.save(update_fields=['updated_at'])
        return {'dispute_id': str(dispute.pk)}
    if command == 'assess-loss':
        allowed(role, {'QUALITE', 'FAO', 'CAO', 'RECEPTION'})
        attempt = data.get('attempt')
        if attempt is None:
            attempt = order.production_attempt - 1
        try:
            attempt = int(attempt)
        except (ValueError, TypeError):
            raise ValidationError('A valid integer production attempt is required.')
        losses = data.get('losses', [])
        if not isinstance(losses, list) or not losses or len(losses) > 100:
            raise ValidationError('Supply a non-empty list of measured losses; maximum 100.')
        from .inventory import assess_rework_loss
        notes = str(data.get('notes', '')).strip()
        recorded = assess_rework_loss(order, attempt, losses, changed_by=actor, notes=notes)
        notify(order, 'REWORK_LOSS_ASSESSED', {'attempt': attempt, 'losses': recorded, 'notes': notes},
               key=f'loss-assessed:{order.pk}:{attempt}:{uuid.uuid4()}')
        return {'attempt': attempt, 'losses': recorded}
    raise ValidationError('Unknown workflow command.')
