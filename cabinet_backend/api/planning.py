"""Deterministic, non-preemptive scheduling behind tenant-scoped business commands.

Planning reservations are serialized by a tenant advisory lock. This service never
locks or writes a prescription while holding only that lock: source commands lock
their prescription first, and scheduling only reads source state (no reverse lock).
"""
from __future__ import annotations

import math
import uuid
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from django.core.exceptions import ValidationError
from django.db import connection, transaction
from django.db.models import F
from django.utils import timezone

from .models import EmployeeProfile, Machine, Prescription
from .planning_models import (ACTIVE_BOOKINGS, EmployeeAvailability, PlanningEvent,
                              PlanningSettings, PlanningTask)
from .workflow import LABELS, next_status, workflow_steps

TZ = ZoneInfo('Africa/Casablanca')
TERMINAL = {'COMPLETED', 'CANCELLED'}
EXTERNAL = {'ATTENTE_RAMASSAGE', 'EN_ROUTE_LABO', 'PRET_EXPEDITION', 'EN_ROUTE_CABINET',
            'VALIDATION_CAO', 'LIVRE', 'ESSAYAGE', 'CLOTURE', 'RETOUR_DEMANDE'}
DEFAULT_RULES = {
    'ANALYSE_DEMANDE': ('RECEPTION', 20, ''), 'A_CONFIRMER': ('RECEPTION', 15, ''),
    'CONTROLE_DOSSIER': ('RECEPTION', 20, ''), 'COULEE_PLATRE': ('RECEPTION', 45, ''),
    'SCAN_LABO': ('RECEPTION', 30, 'SCANNER'), 'CONTROLE_MODELE': ('RECEPTION', 20, ''),
    'PLANIFICATION': ('RECEPTION', 20, ''), 'SALLE_CAO': ('CAO', 60, ''),
    'PREPARATION_CNC': ('FAO', 30, ''), 'USINAGE_CNC': ('FAO', 60, 'USINEUSE_CNC'),
    'TRAITEMENT_THERMIQUE': ('FAO', 120, 'FOUR_FRITTAGE'), 'FRITTAGE_9H': ('FAO', 540, 'FOUR_FRITTAGE'),
    'PREPARATION_3D': ('FAO', 30, ''), 'IMPRESSION_3D': ('FAO', 90, 'IMPRESSION_3D'),
    'LAVAGE_SECHAGE': ('FAO', 30, ''), 'POST_POLYMERISATION': ('FAO', 30, ''),
    'MODELE_TRAVAIL': ('FAO', 30, ''), 'MODELAGE': ('FAO', 60, ''),
    'FABRICATION_MANUELLE': ('FAO', 90, ''), 'FINITION': ('FAO', 45, ''),
    'CONTROLE_QUALITE': ('QUALITE', 30, ''), 'CONDITIONNEMENT': ('QUALITE', 15, ''),
    'A_REFAIRE': ('FAO', 15, ''), 'RECOULER': ('FAO', 15, ''), 'RESCANNER': ('FAO', 15, ''),
}


def lock_planning() -> None:
    if connection.schema_name == 'public':
        raise ValidationError('Choisissez un laboratoire actif pour gérer le planning.')
    with connection.cursor() as cursor:
        cursor.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s,0))',
                       [f'planning:{connection.schema_name}'])


def event(kind, actor='system', *, task=None, order=None, notes='', link_source=True, **payload):
    return PlanningEvent.objects.create(kind=kind, actor=actor, task=task,
        prescription=(order or (task.prescription if task else None)) if link_source else None, notes=notes, payload=payload)


def configuration():
    return PlanningSettings.objects.get_or_create(pk=1)[0]


def rule(step, settings):
    role, duration, machine = DEFAULT_RULES.get(step, ('EXTERNAL', 15, ''))
    extra = settings.step_rules.get(step, {})
    return {'required_role': role, 'estimated_duration_minutes': extra.get('duration', duration),
            'required_qualifications': extra.get('qualifications', []),
            'machine_type': extra.get('machine_type', machine), 'workstation': role}


def priority(order):
    return {'STANDARD': 1, 'EXPRESS': 2, 'NEXT_DAY': 3}.get(order.delivery_service, 1)


def finish_clock(task, now):
    if task.last_started_at:
        task.worked_seconds += max(0, int((now - task.last_started_at).total_seconds()))
    task.last_started_at = None
    task.actual_duration_minutes = math.ceil(task.worked_seconds / 60)


def sync_order(order, actor='system'):
    """Called explicitly after a validated source save, inside its transaction."""
    lock_planning()
    if not order.accepted:
        return []
    settings = configuration()
    now = timezone.now()
    tasks = list(order.planning_tasks.order_by('generation').prefetch_related('dependencies'))
    if order.status == 'CLOTURE':
        for task in tasks:
            if task.status not in TERMINAL:
                finish_clock(task,now)
                task.status,task.actual_end,task.blocking_reason = 'COMPLETED',now,''
                task.save()
                event('SOURCE_COMPLETED',actor,task=task,source_status=order.status)
        return []
    route = workflow_steps(order)
    current = next((i for i, step in enumerate(route) if step['key'] == order.status), -1)
    if current < 0:
        return []
    # The route is unknown before planning; do not manufacture generic future steps.
    if not order.production_method or (order.delivery_service == 'NEXT_DAY' and order.total_price is None):
        route = route[:next(i for i, s in enumerate(route) if s['key'] == 'PLANIFICATION') + 1]
    applicable = {s['key'] for s in route}
    latest = {}
    for task in tasks:
        same_attempt = task.production_attempt == order.production_attempt and task.intake_revision == order.intake_revision
        if not same_attempt or task.workflow_step not in applicable:
            if task.status not in TERMINAL:
                finish_clock(task, now)
                task.status, task.blocking_reason = 'CANCELLED', 'Parcours ou tentative remplacé.'
                task.save()
                event('TASK_CANCELLED', actor, task=task, reason=task.blocking_reason)
            continue
        latest[task.workflow_step] = task
    result, dependency = [], None
    for index, step in enumerate(route):
        key = step['key']
        if key == 'DEMANDE_RECUE':
            continue
        task = latest.get(key)
        if index < current:
            if task and task.status not in TERMINAL:
                finish_clock(task, now)
                task.status, task.actual_end, task.blocking_reason = 'COMPLETED', now, ''
                task.save()
                event('SOURCE_COMPLETED', actor, task=task, source_status=order.status,
                      actual_start_recorded=bool(task.actual_start))
            if task and task.status == 'COMPLETED':
                dependency = task
            continue
        if task is None or task.status in TERMINAL:
            task = PlanningTask.objects.create(prescription=order, workflow_step=key,
                title=step['label'], sequence=index, production_attempt=order.production_attempt,
                intake_revision=order.intake_revision, generation=(task.generation + 1 if task else 1),
                priority=priority(order), **rule(key, settings))
            event('TASK_CREATED', actor, task=task, attempt=order.production_attempt, step=key)
        task.dependencies.set([dependency] if dependency else [])
        task.priority = task.priority_override or priority(order)
        task.sequence = index
        if order.is_paused and task.status == 'IN_PROGRESS':
            finish_clock(task, now)
            task.status, task.blocking_reason = 'PAUSED', order.pause_reason
        task.save()
        result.append(task)
        dependency = task
    return result


def request_replan(order, reason='source-change'):
    from .outbox import enqueue_event
    configuration()
    PlanningSettings.objects.filter(pk=1).update(revision=F('revision') + 1)
    return enqueue_event(order, 'PLANNING', f'planning:{reason}:{order.pk}:{uuid.uuid4()}')


def source_saved(order):
    if order.accepted:
        from .signals import _audit_details
        actor = _audit_details.get()[0]
        sync_order(order, actor)
        request_replan(order)


@transaction.atomic
def resources_changed(actor='system', kind='RESOURCE_CHANGED', *, anchor=None, resources_locked=False, **payload):
    if not resources_locked:
        anchor = lock_resources()
    event(kind, actor, **payload)
    if anchor:
        request_replan(anchor, kind)


def lock_resources():
    """Lock the outbox anchor before the tenant lock, like source commands.

    Creating a durable outbox row takes a foreign-key lock on its prescription.
    Reversing this order could deadlock with a concurrent source command.
    """
    anchor = Prescription.objects.select_for_update().filter(accepted=True).exclude(status='CLOTURE').order_by('pk').first()
    lock_planning()
    return anchor


def _subtract(windows, start, end):
    result = []
    for a, b in windows:
        if end <= a or start >= b:
            result.append((a, b))
        else:
            if a < start: result.append((a, min(start, b)))
            if end < b: result.append((max(end, a), b))
    return result


def employee_windows(employee, day, settings):
    if not employee.is_available or not employee.user.is_active or day.weekday() not in settings.working_days:
        return []
    if employee.platform_account_id and not employee.platform_account.is_active:
        return []
    combine = lambda t: datetime.combine(day, t, tzinfo=TZ)
    windows = [(combine(settings.open_time), combine(settings.close_time))]
    windows = _subtract(windows, combine(settings.break_start), combine(settings.break_end))
    rules = list(employee.planning_availability.all())
    shifts = [r for r in rules if r.availability_type == 'SHIFT']
    if shifts:
        matching = [r for r in shifts if r.weekday == day.weekday()
            and (r.effective_from is None or r.effective_from <= day)
            and (r.effective_until is None or r.effective_until >= day)]
        windows = [(max(a, combine(r.start_time)), min(b, combine(r.end_time)))
                   for a,b in windows for r in matching if max(a, combine(r.start_time)) < min(b, combine(r.end_time))]
    for r in rules:
        if r.availability_type != 'SHIFT':
            windows = _subtract(windows, r.starts_at, r.ends_at)
    # Overlapping weekly rules describe a union, never extra capacity.
    merged = []
    for a, b in sorted(windows):
        if merged and a <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], b))
        else:
            merged.append((a, b))
    return merged


def qualified(employee, task, end):
    if employee.role != task.required_role or not employee.is_available or not employee.user.is_active:
        return False
    if employee.platform_account_id:
        account = employee.platform_account
        account_role = account.workstation_role if account.role == 'LAB' else 'COURSIER'
        if not account.is_active or account.laboratory_id != connection.tenant.pk or account_role not in {employee.role,'MANAGER'}:
            return False
    valid = {q.qualification for q in employee.planning_qualifications.all()
             if q.valid_until is None or q.valid_until >= end.astimezone(TZ).date()}
    return set(task.required_qualifications) <= valid


def deadline(order, settings):
    if order.delivery_date:
        return datetime.combine(order.delivery_date, settings.close_time, tzinfo=TZ)
    if order.deadline_at:
        return order.deadline_at
    if order.automatic_deadline:
        return datetime.combine(order.automatic_deadline, settings.close_time, tzinfo=TZ)
    return order.created_at + timedelta(days={'STANDARD': 4, 'EXPRESS': 2, 'NEXT_DAY': 1}.get(order.delivery_service, 4))


def overlap(start, end, a, b):
    return start < b and a < end


def reservations(tasks, now):
    result = []
    for t in tasks:
        if t.planned_start and t.planned_end and t.status in ACTIVE_BOOKINGS:
            end = t.planned_end
            if t.status in {'IN_PROGRESS', 'PAUSED'}:
                remaining = max(15, t.estimated_duration_minutes - t.actual_duration_minutes)
                end = max(end, now + timedelta(minutes=remaining))
            result.append((t.assigned_employee_id, t.machine_id, t.machine_slot, t.planned_start, end, t.pk))
    return result


def slot_for(employee, task, machine, machine_slot, earliest, settings, bookings):
    duration = timedelta(minutes=task.estimated_duration_minutes)
    first_day = earliest.astimezone(TZ).date()
    horizon = timezone.localdate(timezone.now(), TZ) + timedelta(days=settings.horizon_days)
    day = first_day
    while day < horizon:
        for start, end in employee_windows(employee, day, settings):
            start = max(start, earliest)
            # Advance to the end of the conflicting booking, retaining half-open intervals.
            blocked = sorted((a,b) for emp,mid,slot,a,b,pk in bookings if pk != task.pk
                and (emp == employee.pk or (machine and mid == machine.pk and slot == machine_slot)))
            for a,b in blocked:
                if start + duration <= a: break
                if overlap(start, start + duration, a, b): start = b
            if start + duration <= end and qualified(employee, task, start + duration):
                return start, start + duration
        day += timedelta(days=1)
    return None


def explain_score(employee, task, start, earliest, settings, bookings):
    qualifications = [q.proficiency_level for q in employee.planning_qualifications.all()
        if (not task.required_qualifications or q.qualification in task.required_qualifications)
        and (q.valid_until is None or q.valid_until >= start.astimezone(TZ).date())]
    load = sum((b-a).total_seconds()/60 for emp,_,_,a,b,_ in bookings if emp == employee.pk)
    continuity = any(dep.assigned_employee_id == employee.pk for dep in task.dependencies.all())
    components = {
        'qualification': (sum(qualifications)/len(qualifications)/5 if qualifications else .5),
        'availability': max(0, 1 - (start-earliest).total_seconds()/(settings.horizon_days*86400)),
        'workload': max(0, 1-load/(settings.horizon_days*8*60)),
        'urgency': task.priority/3, 'continuity': int(continuity),
    }
    total = sum(settings.weights[key]*value for key,value in components.items())/sum(settings.weights.values())
    return round(total, 6), {key: round(value, 4) for key,value in components.items()}


def interval_valid(task, employee, start, end, settings, bookings, machine=None, machine_slot=1):
    if start >= end or end-start < timedelta(minutes=task.estimated_duration_minutes):
        raise ValidationError('Le créneau est trop court pour la durée estimée.')
    if not qualified(employee, task, end):
        raise ValidationError('Employé indisponible, rôle ou qualifications obligatoires manquants/expirés.')
    if not any(a <= start and end <= b for a,b in employee_windows(employee, start.astimezone(TZ).date(), settings)):
        raise ValidationError('Le créneau est hors horaire ou recouvre une absence/pause.')
    if task.machine_type and (not machine or machine.machine_type != task.machine_type):
        raise ValidationError('Un équipement du type requis est obligatoire.')
    if machine and (machine.status != 'ACTIF' or not 1 <= machine_slot <= machine.capacity):
        raise ValidationError('Équipement indisponible ou capacité dépassée.')
    for emp,mid,slot,a,b,pk in bookings:
        if pk != task.pk and overlap(start,end,a,b) and (emp == employee.pk or (machine and mid == machine.pk and slot == machine_slot)):
            raise ValidationError('Conflit de réservation : employé ou équipement déjà occupé.')
    for dep in task.dependencies.all():
        if dep.status != 'COMPLETED' and (not dep.planned_end or dep.planned_end > start):
            raise ValidationError('Le créneau précède la fin d’une dépendance.')


@transaction.atomic
def recalculate(*, actor='system', now=None):
    now = now or timezone.now()
    lock_planning()
    settings = configuration()
    tasks = list(PlanningTask.objects.exclude(status__in=TERMINAL).select_related('prescription', 'assigned_employee__user',
        'assigned_employee__platform_account', 'machine').prefetch_related('dependencies').order_by('prescription_id','sequence','generation'))
    if len(tasks) > 5000:
        raise ValidationError('Planning trop volumineux : réduire le périmètre avant le recalcul.')
    employees = list(EmployeeProfile.objects.select_related('user','platform_account').prefetch_related('planning_qualifications','planning_availability').order_by('pk'))
    machines = list(Machine.objects.filter(status='ACTIF').order_by('pk'))
    protected = [t for t in tasks if t.locked or t.status in {'IN_PROGRESS','PAUSED'} or t.manual_block]
    mutable = [t for t in tasks if t not in protected]
    old = {t.pk: (t.assigned_employee_id, t.planned_start, t.planned_end) for t in mutable}
    # Release movable reservations together before rebuilding them under the tenant lock.
    PlanningTask.objects.filter(pk__in=[t.pk for t in mutable]).update(planned_start=None, planned_end=None,
        assigned_employee=None, machine=None, status='PENDING')
    for task in mutable:
        if task.assignment_mode == 'AUTO':
            for field, value in rule(task.workflow_step, settings).items():
                setattr(task, field, value)
        task.planned_start = task.planned_end = None
        task.assigned_employee = task.machine = None
        task.status, task.blocking_reason = 'PENDING', ''
    bookings = reservations(protected, now)
    employee_by_id = {e.pk:e for e in employees}
    for task in protected:
        if task.planned_start and task.assigned_employee_id and not task.manual_block:
            try:
                interval_valid(task, employee_by_id[task.assigned_employee_id], task.planned_start,
                    task.planned_end, settings, bookings, task.machine, task.machine_slot)
                task.blocking_reason = ''
            except (ValidationError, KeyError) as exc:
                task.blocking_reason = 'Affectation conservée — conflit à résoudre : ' + str(exc)
            task.save(update_fields=['blocking_reason','updated_at'])
    # Keep each order topological, then order entire jobs by urgency and remaining slack.
    by_order = {}
    for task in tasks: by_order.setdefault(task.prescription_id, []).append(task)
    jobs = sorted(by_order.values(), key=lambda group: (
        -max(t.priority for t in group),
        (deadline(group[0].prescription,settings)-now).total_seconds()/60-sum(t.estimated_duration_minutes for t in group),
        str(group[0].prescription_id)))
    by_id = {t.pk:t for t in tasks}
    changed, blocked = 0, 0
    for group in jobs:
        for task in sorted(group,key=lambda t:(t.sequence,t.generation)):
            if task in protected: continue
            order = task.prescription
            deps = [by_id.get(d.pk,d) for d in task.dependencies.all()]
            waiting = [d for d in deps if d.status != 'COMPLETED']
            reason = ''
            if order.is_paused: reason = order.pause_reason or 'Commande en pause.'
            elif task.workflow_step in EXTERNAL: reason = 'Validation ou commande métier externe requise : ' + task.title
            elif any(not d.planned_end for d in waiting): reason = 'Dépendance bloquée ou validation externe en attente.'
            elif order.delivery_service == 'NEXT_DAY' and order.total_price is None and task.sequence > 10: reason = 'Devis manuel J+1 non validé.'
            earliest = max([now, *[d.planned_end for d in waiting if d.planned_end]])
            candidates = []
            if not reason:
                equipment = [(m,slot) for m in machines if m.machine_type == task.machine_type for slot in range(1,m.capacity+1)] if task.machine_type else [(None,1)]
                for employee in employees:
                    if employee.role != task.required_role: continue
                    for machine, slot in equipment:
                        interval = slot_for(employee,task,machine,slot,earliest,settings,bookings)
                        if interval:
                            start,end = interval
                            score,components = explain_score(employee,task,start,earliest,settings,bookings)
                            candidates.append((max(0,(end-deadline(order,settings)).total_seconds()),-score,start,employee.pk,
                                               machine.pk if machine else 0,slot,end,employee,machine,components))
                if not candidates: reason = 'Aucun créneau compatible : rôle, qualifications, absence ou capacité indisponible dans l’horizon.'
            if reason:
                task.status, task.blocking_reason = 'BLOCKED', reason
                task.assignment_explanation = {'reason': reason}
                blocked += 1
            else:
                _,neg_score,start,_,_,slot,end,employee,machine,components = min(candidates,key=lambda c:c[:6])
                task.assigned_employee, task.machine, task.machine_slot = employee,machine,slot
                task.planned_start, task.planned_end = start,end
                task.status = 'READY' if order.status == task.workflow_step and not waiting else 'SCHEDULED'
                task.assignment_mode = 'AUTO'
                task.assignment_explanation = {'score':-neg_score,'components':components,'weights':settings.weights,
                    'policy':'urgence, marge avant échéance, contraintes strictes, score pondéré, identifiants stables'}
                bookings.append((employee.pk,machine.pk if machine else None,slot,start,end,task.pk))
            task.save()
            if old[task.pk] != (task.assigned_employee_id,task.planned_start,task.planned_end):
                changed += 1
                event('TASK_SCHEDULED',actor,task=task,link_source=False,employee=task.assigned_employee_id,
                    start=task.planned_start.isoformat() if task.planned_start else None,
                    end=task.planned_end.isoformat() if task.planned_end else None,reason=task.blocking_reason)
    # A preserved future booking can become incompatible with a moved predecessor.
    # Keep the supervisor's reservation and surface that conflict explicitly.
    for task in protected:
        if not task.planned_start or task.manual_block: continue
        dependencies = [by_id.get(d.pk,d) for d in task.dependencies.all()]
        if any(d.status != 'COMPLETED' and (not d.planned_end or d.planned_end > task.planned_start) for d in dependencies):
            reason = 'Affectation conservée — conflit à résoudre : une dépendance se termine après ce créneau ou reste bloquée.'
            if task.blocking_reason != reason:
                task.blocking_reason = reason
                task.save(update_fields=['blocking_reason','updated_at'])
                event('LOCKED_DEPENDENCY_CONFLICT',actor,task=task,link_source=False,reason=reason)
    settings.applied_revision, settings.last_recalculated_at = settings.revision, now
    settings.save(update_fields=['applied_revision','last_recalculated_at'])
    event('RECALCULATED',actor,changed=changed,blocked=blocked,revision=settings.revision)
    return {'changed':changed,'blocked':blocked,'revision':settings.revision}


def employee_name(employee):
    return employee.platform_account.name if employee.platform_account_id else employee.user.get_full_name() or employee.user.get_username()


def case_risk(order, tasks, now=None, settings=None):
    now = now or timezone.now()
    due = deadline(order,settings or configuration())
    remaining = [t for t in tasks if t.status not in TERMINAL]
    finish = max([now,*[t.planned_end for t in remaining if t.planned_end]])
    unscheduled = sum(not t.planned_end for t in remaining)
    risk = 'LATE' if finish > due or (remaining and now > due) else 'AT_RISK' if unscheduled else 'ON_TRACK'
    return {'risk':risk,'deadline':due,'projected_end':finish,'unscheduled':unscheduled,
            'remaining_minutes':sum(t.estimated_duration_minutes for t in remaining)}


def _can_operate(task, actor, role):
    if role == 'MANAGER': return
    employee = task.assigned_employee
    if not employee or role != task.required_role:
        raise ValidationError('Cette tâche doit être exécutée par son responsable ou le responsable du laboratoire.')
    prefix = f'platform:{employee.platform_account_id}:' if employee.platform_account_id else f'user:{employee.user_id}:'
    if not actor.startswith(prefix):
        raise ValidationError('Cette tâche est affectée à un autre collaborateur.')


def task_command(order, command, data, actor, role):
    """Runs inside execute_case_command's source lock, audit and UUID receipt."""
    lock_planning()
    task = PlanningTask.objects.select_for_update(of=('self',)).select_related('prescription','assigned_employee__user',
        'assigned_employee__platform_account','machine').filter(pk=data.get('task'),prescription=order).first()
    if task is None: raise ValidationError('Tâche introuvable dans cette commande et ce laboratoire.')
    if not isinstance(data.get('notes',''),str) or len(data.get('notes','')) > 1000:
        raise ValidationError('Le commentaire doit contenir au plus 1000 caractères.')
    if task.status in TERMINAL: raise ValidationError('Cette tâche est déjà terminée ou annulée.')
    old_source_status, old_task_status = order.status, task.status
    settings, now = configuration(), timezone.now()
    supervision = {'planning-assign','planning-reschedule','planning-lock','planning-estimate'}
    if command in supervision:
        if role != 'MANAGER': raise ValidationError('Action réservée au responsable du laboratoire.')
        if task.status in {'IN_PROGRESS','PAUSED'}: raise ValidationError('Ne déplacez pas une tâche déjà commencée ; suspendez/résolvez son exécution.')
        if command == 'planning-lock':
            if type(data.get('locked')) is not bool: raise ValidationError('locked doit être un booléen.')
            if data['locked'] and not task.planned_start: raise ValidationError('Planifiez la tâche avant de la verrouiller.')
            task.locked = data['locked']
        else:
            if 'duration' in data:
                duration = data['duration']
                if type(duration) is not int or not 1 <= duration <= 1440: raise ValidationError('Durée entière comprise entre 1 et 1440 minutes requise.')
                task.estimated_duration_minutes = duration
            if 'priority' in data:
                if type(data['priority']) is not int or not 1 <= data['priority'] <= 3: raise ValidationError('Priorité comprise entre 1 et 3 requise.')
                task.priority_override = task.priority = data['priority']
            employee = EmployeeProfile.objects.select_related('user','platform_account').prefetch_related('planning_availability','planning_qualifications').filter(pk=data.get('employee',task.assigned_employee_id)).first()
            if employee is None: raise ValidationError('Choisissez un collaborateur de ce laboratoire.')
            from django.utils.dateparse import parse_datetime
            def timestamp(key, fallback):
                value = data.get(key)
                if value is None: return fallback
                parsed = parse_datetime(value) if isinstance(value,str) else None
                if parsed is None or timezone.is_naive(parsed): raise ValidationError('Horodatage ISO avec fuseau requis.')
                return parsed
            start = timestamp('start',task.planned_start)
            end = timestamp('end',start + timedelta(minutes=task.estimated_duration_minutes) if start else None)
            if not start or not end: raise ValidationError('Choisissez un début et une fin.')
            if start < now: raise ValidationError('Une affectation ne peut pas commencer dans le passé.')
            machine = Machine.objects.filter(pk=data.get('machine',task.machine_id)).first()
            slot = data.get('machine_slot',task.machine_slot)
            if type(slot) is not int: raise ValidationError('Numéro de capacité entier requis.')
            bookings = reservations(PlanningTask.objects.exclude(pk=task.pk).exclude(status__in=TERMINAL),now)
            interval_valid(task,employee,start,end,settings,bookings,machine,slot)
            task.assigned_employee,task.machine,task.machine_slot = employee,machine,slot
            task.planned_start,task.planned_end,task.assignment_mode,task.locked = start,end,'MANUAL',True
            task.status,task.blocking_reason = 'SCHEDULED',''
    else:
        _can_operate(task,actor,role)
        if task.workflow_step != order.status: raise ValidationError('Seule la tâche de l’étape métier actuelle peut être exécutée.')
        if task.workflow_step in EXTERNAL: raise ValidationError('Utilisez la commande spécialisée de validation, QR/PIN ou retour de dossier.')
        if task.dependencies.exclude(status='COMPLETED').exists(): raise ValidationError('Les tâches préalables ne sont pas terminées.')
        if command in {'planning-start','planning-resume'}:
            if task.status == 'IN_PROGRESS': raise ValidationError('Tâche déjà démarrée.')
            if order.is_paused: raise ValidationError('Reprenez d’abord la commande via la commande métier de pause.')
            if not task.assigned_employee_id: raise ValidationError('Affectez un collaborateur qualifié avant de démarrer.')
            employee = EmployeeProfile.objects.select_related('user','platform_account').prefetch_related('planning_availability','planning_qualifications').get(pk=task.assigned_employee_id)
            end = now + timedelta(minutes=task.estimated_duration_minutes)
            interval_valid(task,employee,now,end,settings,reservations(PlanningTask.objects.exclude(pk=task.pk),now),task.machine,task.machine_slot)
            task.status,task.actual_start,task.last_started_at = 'IN_PROGRESS',task.actual_start or now,now
            task.planned_start,task.planned_end,task.manual_block,task.blocking_reason = now,end,False,''
        elif command in {'planning-pause','planning-block'}:
            if not str(data.get('notes','')).strip(): raise ValidationError('Un motif est obligatoire.')
            if command == 'planning-pause' and task.status != 'IN_PROGRESS': raise ValidationError('Seule une tâche en cours peut être mise en pause.')
            finish_clock(task,now)
            task.status,task.blocking_reason = ('PAUSED' if command == 'planning-pause' else 'BLOCKED'),data['notes']
            task.manual_block = True
        elif command == 'planning-complete':
            if task.status != 'IN_PROGRESS': raise ValidationError('Démarrez la tâche avant de la terminer.')
            target = next_status(order)
            if not target: raise ValidationError('Aucune transition suivante disponible.')
            # These remain the SAME business guard and audit context as all other transitions.
            from .case_commands import change_status
            change_status(order,target)
            order.save()
            task.refresh_from_db()
        else: raise ValidationError('Commande de planning inconnue.')
    task.save()
    event(command.upper().replace('-','_'),actor,task=task,notes=str(data.get('notes','')),
          old_source_status=old_source_status,old_task_status=old_task_status,
          source_status=order.status,task_status=task.status,employee=task.assigned_employee_id,
          start=task.planned_start.isoformat() if task.planned_start else None,
          end=task.planned_end.isoformat() if task.planned_end else None)
    request_replan(order,command)
    return {'task_id':str(task.pk),'status':task.status}
