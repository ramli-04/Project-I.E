"""Workflow invariants shared by API commands, Django Admin and background jobs."""
from copy import copy
from django.core.exceptions import ValidationError

from .workflow import next_status

MANUFACTURING = {'USINAGE_CNC', 'IMPRESSION_3D', 'FABRICATION_MANUELLE', 'TRAITEMENT_THERMIQUE', 'FRITTAGE_9H'}
REWORK_ORIGINS = {'SALLE_CAO', 'MODELE_TRAVAIL', 'COULEE_PLATRE', 'SCAN_LABO', 'CONTROLE_MODELE',
                  'PREPARATION_CNC', 'PREPARATION_3D', 'MODELAGE', 'FINITION', 'CONTROLE_QUALITE',
                  'LIVRE', 'ESSAYAGE', 'CLOTURE'} | MANUFACTURING | {'LAVAGE_SECHAGE', 'POST_POLYMERISATION'}
ROLE_STAGES = {
    'RECEPTION': {'DEMANDE_RECUE', 'ANALYSE_DEMANDE', 'A_CONFIRMER', 'CONTROLE_DOSSIER', 'PLANIFICATION',
                  'COULEE_PLATRE', 'SCAN_LABO', 'CONTROLE_MODELE', 'RETOUR_DEMANDE'},
    'CAO': {'SALLE_CAO', 'VALIDATION_CAO'},
    'FAO': MANUFACTURING | {'PREPARATION_CNC', 'PREPARATION_3D', 'MODELAGE', 'MODELE_TRAVAIL',
                          'FINITION', 'LAVAGE_SECHAGE', 'POST_POLYMERISATION', 'A_REFAIRE', 'RECOULER', 'RESCANNER'},
    'QUALITE': {'CONTROLE_QUALITE', 'CONDITIONNEMENT'},
    'COURIER': {'ATTENTE_RAMASSAGE', 'EN_ROUTE_LABO', 'PRET_EXPEDITION', 'EN_ROUTE_CABINET'},
}


def latest_inspection(order, stage):
    query = order.inspections.filter(stage=stage)
    if stage == 'QUALITY':
        query = query.filter(production_attempt=order.production_attempt)
    else:
        query = query.filter(intake_revision=order.intake_revision)
    return query.order_by('-created_at', '-pk').first()


def require_inspection(order, stage):
    evidence = latest_inspection(order, stage)
    if evidence is None or not evidence.passed:
        raise ValidationError({'status': f'A passing {stage} inspection for this revision/attempt is required.'})


def validate_source_change(order, previous, fields):
    from .signals import _workflow_metadata
    metadata = _workflow_metadata.get()
    if previous is None:
        if not order.disinfected:
            raise ValidationError({'disinfected': 'An explicit disinfection declaration is required.'})
        return
    written = lambda field: fields is None or field in fields
    if previous['accepted'] and written('accepted') and not order.accepted:
        raise ValidationError('An accepted case cannot become an unaccepted request.')
    planning = {'DEMANDE_RECUE', 'ANALYSE_DEMANDE', 'ATTENTE_RAMASSAGE', 'EN_ROUTE_LABO', 'A_CONFIRMER',
                'CONTROLE_DOSSIER', 'COULEE_PLATRE', 'SCAN_LABO', 'CONTROLE_MODELE', 'PLANIFICATION', 'RETOUR_DEMANDE'}
    if previous['status'] not in planning:
        for field in ('production_method', 'thermal_treatment'):
            if written(field) and getattr(order, field) != previous[field]:
                raise ValidationError('The production route is locked after planning.')
    if written('billing_stage') and order.billing_stage == 'FACTURE' and previous['billing_stage'] != 'FACTURE':
        if metadata.get('action') != 'ISSUE_INVOICE' or metadata.get('role') not in {'MANAGER', 'COMPTABILITE'}:
            raise ValidationError('Issue invoices through monthly closing.')
    if previous['invoiced_at'] and written('is_fast_track') and order.is_fast_track != previous['is_fast_track']:
        raise ValidationError('Issued urgency pricing cannot be changed.')
    if previous['status'] not in {'DEMANDE_RECUE', 'ANALYSE_DEMANDE', 'RETOUR_DEMANDE'}:
        for field in ('tooth_number', 'shade', 'material', 'design_validation_requested'):
            if written(field) and getattr(order, field) != previous[field]:
                raise ValidationError({field: 'Accepted clinical specifications require a recorded revision.'})
    if order.invoiced_at and any(written(f) and getattr(order, f) != previous[f] for f in ('delivery_service',)):
        raise ValidationError('Issued pricing/service cannot be changed; issue an adjustment.')
    if not written('status') or order.status == previous['status']:
        return
    old = previous['status']
    role = metadata.get('role', 'SYSTEM')
    action = metadata.get('action', 'TRANSITION')
    if role not in {'MANAGER', 'SYSTEM'}:
        special = ((role == 'DENTIST' and action in {'DESIGN_DECISION', 'FITTING', 'RESUBMIT'})
                   or (action == 'REWORK' and role in {'RECEPTION', 'CAO', 'FAO', 'QUALITE', 'DENTIST'}))
        if not special and old not in ROLE_STAGES.get(role, set()):
            raise ValidationError('Your workstation cannot perform this transition.')
    if order.is_paused and action not in {'DESIGN_REQUEST', 'DESIGN_DECISION', 'REWORK'}:
        raise ValidationError('Resume the case before advancing.')
    if not order.accepted:
        raise ValidationError('Accept the case before advancing.')
    before = copy(order)
    before.status = old
    if order.status in {'A_REFAIRE', 'RECOULER', 'RESCANNER'}:
        if old not in REWORK_ORIGINS or action != 'REWORK' or not metadata.get('cause') or not metadata.get('corrective_action'):
            raise ValidationError('Use the rework command with origin, cause, action and measured losses.')
    elif order.status == 'RETOUR_DEMANDE':
        if action != 'INSPECTION_FAILED' or old not in {'A_CONFIRMER', 'CONTROLE_DOSSIER', 'CONTROLE_MODELE'}:
            raise ValidationError('A failed intake inspection is required.')
    elif old == 'VALIDATION_CAO' and order.status == 'SALLE_CAO':
        if action != 'DESIGN_DECISION':
            raise ValidationError('Only a design decision can return this case to CAO.')
    elif old == 'LIVRE' and order.status == 'CLOTURE':
        if action != 'FITTING':
            raise ValidationError('Use the dentist fitting command.')
    elif order.status != next_status(before):
        raise ValidationError({'status': 'Advance to the next workflow step or use an explicit exception command.'})
    if old == 'ANALYSE_DEMANDE' and not order.analysis_validated:
        raise ValidationError('Complete the analysis checkpoint.')
    if old == 'A_CONFIRMER' and order.status != 'RETOUR_DEMANDE' and not order.reception_validated:
        raise ValidationError('Confirm reception before advancing.')
    if order.intake_version >= 2:
        if old == 'CONTROLE_DOSSIER' and order.status != 'RETOUR_DEMANDE':
            require_inspection(order, 'PHYSICAL' if order.impression_type == 'PHYSIQUE' else 'DIGITAL')
        if old == 'CONTROLE_MODELE' and order.status not in {'RETOUR_DEMANDE', 'RECOULER', 'RESCANNER'}:
            require_inspection(order, 'MODEL')
        if old == 'CONTROLE_QUALITE' and order.status not in {'A_REFAIRE', 'RECOULER', 'RESCANNER'}:
            require_inspection(order, 'QUALITY')
        if order.status in MANUFACTURING and not order.production_lots.exists():
            raise ValidationError('Link a production lot before fabrication.')
        if order.status == 'VALIDATION_CAO' and action != 'DESIGN_REQUEST':
            raise ValidationError('Submit a design version for dentist review.')
        if old == 'VALIDATION_CAO' and order.status != 'SALLE_CAO':
            if action != 'DESIGN_DECISION' or not order.design_reviews.filter(production_attempt=order.production_attempt, status='APPROVED').exists():
                raise ValidationError('Dentist design approval is required.')
    if order.status == 'LIVRE' and action != 'CONFIRM_DELIVERY':
        raise ValidationError('Use QR checkout and server-side PIN confirmation.')
    custody_actions = {'ATTENTE_RAMASSAGE': 'PICKUP', 'EN_ROUTE_LABO': 'LAB-DEPOSIT', 'PRET_EXPEDITION': 'CHECKOUT'}
    if old in custody_actions and action != custody_actions[old]:
        raise ValidationError('Use the authenticated QR custody command.')
    if old == 'PLANIFICATION' and (not order.production_method or not order.delivery_date):
        raise ValidationError('Choose production method and confirmed delivery date.')
    if old == 'PLANIFICATION' and order.total_price is None:
        raise ValidationError('A manual J+1 quote is required before production.')
    if old == 'CONTROLE_QUALITE' and order.status == 'CONDITIONNEMENT' and not order.quality_validated:
        raise ValidationError('Validate final quality control.')
