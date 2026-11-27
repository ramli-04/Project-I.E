"""Advisory capacity: reuse real scheduling primitives on unsaved objects only.

This is a provisional lower bound over configured routes and known reservations.
External approvals/courier rounds and future unplanned work have no known ETA.
Nothing here accepts a case, selects its route, reserves a slot or approves a check.
"""
import uuid
from copy import copy

from django.utils import timezone

from .models import EmployeeProfile, Machine, Prescription
from .planning import (EXTERNAL, TERMINAL, TZ, candidate_slot, deadline, ordered_jobs,
                       priority, reservations, rule)
from .planning_models import PlanningSettings, PlanningTask
from .workflow import METHODS, workflow_steps


def capacity_preview(payload):
    result = {'requested_deadline': None, 'feasible': None,
              'earliest_feasible_date': None, 'reason_code': None, 'message': '',
              'provisional': True}
    if not isinstance(payload, dict):
        return result
    service = payload.get('delivery_service', 'STANDARD')
    impression = payload.get('impression_type', 'PHYSIQUE')
    method = payload.get('production_method')
    count = payload.get('clinical_item_count', 1)
    if (not isinstance(service, str) or not isinstance(impression, str)
        or (method is not None and not isinstance(method, str))
        or service not in {'STANDARD', 'EXPRESS', 'NEXT_DAY'}
        or impression not in {'PHYSIQUE', 'NUMERIQUE'}
        or (method and method not in METHODS)
        or type(count) is not int or not 1 <= count <= 32):
        return result
    now = timezone.now().astimezone(TZ)
    settings = PlanningSettings.objects.filter(pk=1).first() or PlanningSettings()
    # Local calendar days, exactly as calculate_automatic_calendar_task uses them.
    order = Prescription(created_at=now, delivery_service=service,
                         impression_type=impression, intake_version=2)
    due = deadline(order, settings)
    result['requested_deadline'] = due.isoformat()
    tasks = list(PlanningTask.objects.exclude(status__in=TERMINAL)
        .select_related('prescription', 'machine').prefetch_related('dependencies'))
    if len(tasks) > 5000:
        return result
    employees = list(EmployeeProfile.objects.select_related('user', 'platform_account')
        .prefetch_related('planning_qualifications', 'planning_availability').order_by('pk'))
    machines = list(Machine.objects.filter(status='ACTIF').order_by('pk'))
    if not employees:
        return result
    finishes = []
    for route in ([method] if method else METHODS):
        candidate = copy(order)
        candidate.pk = uuid.uuid5(uuid.NAMESPACE_URL, 'capacity-preview:' + route)
        candidate.production_method = route
        # The minimum existing thermal option; no clinical protocol is inferred.
        candidate.thermal_treatment = 'AUCUN'
        projected = []
        for index, step in enumerate(workflow_steps(candidate)):
            key = step['key']
            if key in EXTERNAL or key == 'DEMANDE_RECUE':
                continue
            task = PlanningTask(prescription=candidate, workflow_step=key, sequence=index,
                                priority=priority(candidate), **rule(key, settings))
            task._prefetched_objects_cache = {'dependencies': []}
            projected.append(task)
        bookings = reservations(tasks, now)
        # Include known internal backlog, retaining all real reservations unchanged.
        pending = [copy(t) for t in tasks if not t.planned_end and t.workflow_step not in EXTERNAL]
        unknown_backlog = False
        finish = None
        for group in ordered_jobs([*pending, *projected], settings, now):
            ready = now
            for task in sorted(group, key=lambda t: (t.sequence, t.generation)):
                if task.prescription.is_paused or task.manual_block:
                    unknown_backlog = True
                    break
                ready = max([ready, *[d.planned_end for d in task.dependencies.all()
                                      if d.status != 'COMPLETED' and d.planned_end]])
                choice = candidate_slot(task, task.prescription, ready, settings, bookings, employees, machines)
                if choice is None:
                    if task.prescription_id != candidate.pk:
                        unknown_backlog = True
                    break
                _, _, start, _, _, slot, end, employee, machine, _ = choice
                task.assigned_employee, task.machine, task.machine_slot = employee, machine, slot
                task.planned_start, task.planned_end, task.status = start, end, 'SCHEDULED'
                bookings.extend(reservations([task], now))
                ready = end
            else:
                if group[0].prescription_id == candidate.pk:
                    finish = ready
            if unknown_backlog:
                break
        if finish is not None and not unknown_backlog:
            finishes.append(finish)
    if not finishes:
        return result
    earliest = min(finishes)
    closed = due.astimezone(TZ).weekday() not in settings.working_days
    feasible = earliest <= due and not closed
    result.update(feasible=feasible, earliest_feasible_date=earliest.astimezone(TZ).date().isoformat(),
                  reason_code=None if feasible else 'CLOSED_DAY' if closed else 'CAPACITY',
                  message='Estimation provisoire selon les parcours et disponibilités connus, hors transport et attente de validation. Le laboratoire confirme le parcours et la date.')
    return result
