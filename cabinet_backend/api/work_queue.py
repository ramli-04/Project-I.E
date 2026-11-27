"""Uncached, tenant-local read model. Descriptors never authorize a command."""
from datetime import datetime, timezone as datetime_timezone

from django.db.models import Prefetch
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import ValidationError

from .business_views import BusinessPagination
from .models import Prescription
from .permissions import LaboratoryResourcePermission, actor_role, can_operate_task
from .planning import case_risk
from .planning_models import PlanningSettings, PlanningTask
from .workflow_spec import describe_current_step

LAB_ROLES = {'RECEPTION', 'CAO', 'FAO', 'QUALITE', 'COMPTABILITE'}
QUOTE_STEPS = {'DEMANDE_RECUE', 'ANALYSE_DEMANDE', 'PLANIFICATION'}
EQUIPMENT_ACTIONS = {
    'SETUP': 'Chargement terminé : lancer le cycle',
    'CYCLE': 'Confirmer la fin réelle du cycle',
    'AWAITING_UNLOAD': 'Commencer le déchargement',
    'UNLOADING': 'Confirmer le déchargement et terminer',
}
INSPECTIONS = {
    'PHYSICAL': "Contrôler l'empreinte", 'DIGITAL': 'Contrôler le fichier STL',
    'MODEL': 'Contrôler le modèle et le scan', 'QUALITY': 'Contrôle qualité final',
}


def primary_action(order, step, task, quote=False):
    kind, label, command, view = step['kind'], 'Consulter le dossier', None, 'clinical'
    if quote:
        kind, label, command = 'QUOTE', 'Établir le devis J+1', 'quote'
    elif kind == 'ACCEPT':
        label = "Poursuivre vers l'analyse" if order.accepted else 'Accepter et analyser'
        command, view = ('advance' if order.accepted else 'accept'), 'stage'
    elif kind == 'CONFIRM':
        label = "Valider l'analyse" if order.status == 'ANALYSE_DEMANDE' else 'Confirmer la réception'
        command, view = 'advance', 'stage'
    elif kind == 'PLAN':
        label, command, view = 'Planifier la fabrication', 'advance', 'stage'
    elif kind == 'INSPECT':
        label, command = INSPECTIONS[step['inspection_stages'][0]], 'inspection'
    elif kind == 'DESIGN':
        label = 'Soumettre le design au dentiste' if order.design_validation_requested else 'Concevoir'
        command, view = ('design-request', 'clinical') if order.design_validation_requested else ('start', 'progress')
    elif kind in {'WORK', 'REWORK'}:
        view = 'progress'
        if task and task.status == 'IN_PROGRESS':
            label = EQUIPMENT_ACTIONS.get(task.resource_phase, f"Terminer : {step['label']}")
            command = {'SETUP': 'launch-cycle', 'CYCLE': 'cycle-finished',
                       'AWAITING_UNLOAD': 'begin-unload', 'UNLOADING': 'complete'}.get(task.resource_phase, 'complete')
        elif kind == 'REWORK' or task and task.status in {'PAUSED', 'BLOCKED'}:
            label = f"Reprendre : {step['label']}"
            command = 'resume' if task and task.status in {'PAUSED', 'BLOCKED'} else 'start'
        else:
            label, command = f"Démarrer : {step['label']}", 'start'
    result = {'kind': kind, 'label': label, 'command': command, 'view': view}
    if kind == 'INSPECT':
        result['inspection_stage'] = step['inspection_stages'][0]
    return result


def queue_row(order, tasks, request, role, selected_role, settings, now):
    step = describe_current_step(order)
    if not step or step['kind'] == 'DONE':
        return None
    current = [t for t in tasks if t.workflow_step == order.status]
    task = max(current, key=lambda t: t.generation, default=None)
    operates = bool(task and can_operate_task(task, request, role))
    quote = order.delivery_service == 'NEXT_DAY' and order.total_price is None and order.status in QUOTE_STEPS
    owner = (role == 'MANAGER' or role in step['owner_roles']) and (not selected_role or selected_role in step['owner_roles'])
    if quote and role in {'MANAGER', 'COMPTABILITE'} and selected_role in {'', 'COMPTABILITE'}:
        owner = True
    elif role == 'COMPTABILITE' or selected_role == 'COMPTABILITE':
        return None

    reason = ''
    if step['kind'] in {'CUSTODY', 'CLINIC'}:
        # No follow/subscription model exists: staff follow external handoffs in their lab.
        if selected_role and not owner and selected_role not in {'RECEPTION', 'QUALITE'}:
            return None
        group = 'WAITING'
        reason = 'En attente du coursier' if step['kind'] == 'CUSTODY' else 'En attente du dentiste'
    elif not owner:
        return None
    elif order.is_paused:
        group, reason = 'PAUSED', order.pause_reason
    elif step['kind'] in {'WORK', 'REWORK'} and not operates:
        group = 'TEAM'
        reason = 'Tâche affectée à un autre collaborateur' if task and task.assigned_employee_id else 'Responsable à affecter dans le planning'
    else:
        group = 'TODO'

    # Assigned equipment actions stay reachable even while the machine runs/holds the part.
    if operates and task.status == 'IN_PROGRESS' and task.resource_phase in {'CYCLE', 'AWAITING_UNLOAD'} and group == 'TODO':
        group = 'WAITING'
        reason = 'Cycle machine en cours' if task.resource_phase == 'CYCLE' else 'Machine occupée : déchargement à commencer'
    elif task and step['kind'] in {'WORK', 'REWORK', 'DESIGN'} and group == 'TODO':
        if task.status in {'PENDING', 'BLOCKED', 'PAUSED'}:
            reason = task.blocking_reason or 'Consulter le planning avant de reprendre'
        elif any(dependency.status != 'COMPLETED' for dependency in task.dependencies.all()):
            reason = 'Étape précédente à terminer'
        elif task.status in {'READY', 'SCHEDULED'} and task.planned_start and task.planned_start > now:
            reason = 'Démarrage prévu au planning ; une anticipation nécessite le responsable et un motif'

    risk = case_risk(order, tasks, now=now, settings=settings)
    action = primary_action(order, step, task, quote and role in {'MANAGER', 'COMPTABILITE'} and selected_role in {'', 'COMPTABILITE'})
    if group in {'TEAM', 'PAUSED'} or step['kind'] in {'CUSTODY', 'CLINIC'}:
        action.update(label='Consulter le dossier', command=None)
        if group == 'TEAM':
            action['view'] = 'progress'
        elif group == 'PAUSED':
            action['view'] = 'clinical'
    elif reason and not (task and task.status == 'IN_PROGRESS'):
        action.update(label='Consulter le planning', command=None, view='progress')
    return {
        'id': str(order.pk), 'patient_ref': order.patient_ref, 'dentist_name': order.dentist_name,
        'status': order.status, 'current_step': step, 'group': group, 'waiting_reason': reason,
        'primary_action': action,
        'task': {'id': str(task.pk), 'status': task.status, 'resource_phase': task.resource_phase,
                 'planned_start': task.planned_start, 'can_operate': operates,
                 'can_start_now': role == 'MANAGER'} if task else None,
        'deadline_at': risk['deadline'], 'risk': risk['risk'], 'delivery_service': order.delivery_service,
        'is_fast_track': order.is_fast_track, 'is_paused': order.is_paused, 'pause_reason': order.pause_reason,
    }


@api_view(['GET'])
@permission_classes([LaboratoryResourcePermission])
def work_queue(request):
    role = actor_role(request)
    selected_role = request.query_params.get('role', '') if role == 'MANAGER' else ''
    if selected_role and selected_role not in LAB_ROLES:
        raise ValidationError('Poste de laboratoire invalide.')
    # Unsaved defaults keep this endpoint strictly read-only even before planning is configured.
    settings = PlanningSettings.objects.filter(pk=1).first() or PlanningSettings()
    task_query = PlanningTask.objects.exclude(status='CANCELLED').select_related('assigned_employee').prefetch_related('dependencies')
    cases = Prescription.objects.exclude(status='CLOTURE').prefetch_related(
        Prefetch('planning_tasks', queryset=task_query, to_attr='queue_tasks'))
    search = request.query_params.get('search', '').strip()
    if search:
        from django.db.models import Q
        cases = cases.filter(Q(patient_ref__icontains=search) | Q(dentist_name__icontains=search))
    now = timezone.now()
    rows = []
    for order in cases:
        tasks = [t for t in order.queue_tasks if t.production_attempt == order.production_attempt and t.intake_revision == order.intake_revision]
        row = queue_row(order, tasks, request, role, selected_role, settings, now)
        if row:
            rows.append(row)
    rows.sort(key=lambda row: ({'LATE': 0, 'AT_RISK': 1, 'ON_TRACK': 2}[row['risk']],
                              row['deadline_at'] or datetime.max.replace(tzinfo=datetime_timezone.utc),
                              {'NEXT_DAY': 0, 'EXPRESS': 1, 'STANDARD': 2}.get(row['delivery_service'], 2), row['id']))
    paginator = BusinessPagination()
    return paginator.get_paginated_response(paginator.paginate_queryset(rows, request))
