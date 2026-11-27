"""Shared resource phases; equipment stays occupied until a human confirms unloading.

Durations are planning estimates, never device events or clinical approvals.
Database exclusion functions in migration 0025 mirror these booking intervals.
"""
from datetime import datetime, timedelta, timezone as utc

from django.core.exceptions import ValidationError
from django.utils import timezone

from .planning_models import ACTIVE_BOOKINGS, EQUIPMENT_PHASES

UNATTENDED_TYPES = {'USINEUSE_CNC', 'FOUR_FRITTAGE', 'IMPRESSION_3D'}
FOREVER = datetime.max.replace(tzinfo=utc.utc)


def attended_intervals(task, start=None, end=None):
    start, end = start or task.planned_start, end or task.planned_end
    if not start or not end:
        return []
    if task.resource_phase == 'MANUAL':
        return [(start, end)]
    if task.resource_phase == 'PLANNED':
        return [(start, start + timedelta(minutes=task.setup_minutes)),
                (end - timedelta(minutes=task.unload_minutes), end)]
    if task.resource_phase in {'SETUP', 'UNLOADING'}:
        return [(task.phase_started_at or start, FOREVER)]
    return []


def phase_bookings(tasks, now):
    result = []
    for task in tasks:
        if not task.planned_start or not task.planned_end:
            continue
        if task.status not in ACTIVE_BOOKINGS and task.resource_phase not in EQUIPMENT_PHASES:
            continue
        intervals = attended_intervals(task)
        if task.resource_phase == 'MANUAL' and task.status in {'IN_PROGRESS', 'PAUSED'}:
            intervals = [(task.planned_start, max(task.planned_end, now + timedelta(
                minutes=max(15, task.estimated_duration_minutes - task.actual_duration_minutes))))]
        for start, end in intervals:
            result.append((task.assigned_employee_id, None, 1, start, end, task.pk))
        if task.machine_id:
            end = FOREVER if task.resource_phase in EQUIPMENT_PHASES else task.planned_end
            if task.resource_phase == 'MANUAL' and intervals:
                end = intervals[0][1]
            result.append((None, task.machine_id, task.machine_slot, task.planned_start, end, task.pk))
    return result


def equipment_slot(employee, task, machine, slot, earliest, settings, bookings):
    """Find attended windows around a continuous unattended machine interval."""
    from .planning import TZ, employee_windows, overlap, qualified
    setup = timedelta(minutes=task.setup_minutes)
    unload = timedelta(minutes=task.unload_minutes)
    cycle = timedelta(minutes=task.estimated_duration_minutes-task.setup_minutes-task.unload_minutes)
    if cycle <= timedelta(0):
        return None
    first_day = earliest.astimezone(TZ).date()
    horizon = timezone.localdate(timezone.now(),TZ) + timedelta(days=settings.horizon_days)
    windows = []
    day = first_day
    while day < horizon:
        windows.extend(employee_windows(employee, day, settings))
        day += timedelta(days=1)
    employee_busy = sorted((a,b) for emp,_,_,a,b,pk in bookings if emp == employee.pk and pk != task.pk)
    machine_busy = [(a,b) for _,mid,s,a,b,pk in bookings if mid == machine.pk and s == slot and pk != task.pk]

    def attended(ready, duration):
        for a,b in windows:
            start = max(a,ready)
            for x,y in employee_busy:
                if start > b-duration:
                    break
                if start+duration <= x:
                    break
                if overlap(start,start+duration,x,y):
                    start = y
            if start <= b-duration:
                return start
        return None

    ready = earliest
    # Each retry advances beyond a conflicting equipment reservation.
    for _ in range(len(machine_busy)+1):
        start = attended(ready,setup)
        if start is None:
            return None
        unload_start = attended(start+setup+cycle,unload)
        if unload_start is None:
            return None
        end = unload_start+unload
        conflicts = [b for a,b in machine_busy if overlap(start,end,a,b)]
        if conflicts:
            ready = max(conflicts)
            if ready == FOREVER:
                return None
            continue
        if qualified(employee,task,end):
            return start,end
        return None
    return None


def validate_attended(task, employee, start, end, settings, bookings, *, duration=None):
    from .planning import TZ, employee_windows, overlap, qualified
    intervals = [(start,end)] if duration is not None else attended_intervals(task,start,end)
    for a,b in intervals:
        if not qualified(employee,task,b):
            raise ValidationError('Employé indisponible ou qualification expirée.')
        if not any(x <= a and b <= y for x,y in employee_windows(employee,a.astimezone(TZ).date(),settings)):
            raise ValidationError('Chargement ou déchargement hors horaire / absence / pause.')
        if any(pk != task.pk and emp == employee.pk and overlap(a,b,x,y)
               for emp,_,_,x,y,pk in bookings):
            raise ValidationError('Conflit de réservation du technicien pendant une phase manuelle.')
