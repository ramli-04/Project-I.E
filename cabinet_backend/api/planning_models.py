"""Tenant-local production planning; prescription status remains the business truth."""
import uuid
from datetime import time

from django.contrib.postgres.constraints import ExclusionConstraint
from django.contrib.postgres.fields import DateTimeRangeField, RangeOperators
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from .business_models import ImmutableEvidence


def default_weights():
    return {'qualification': 30, 'availability': 25, 'workload': 20, 'urgency': 15, 'continuity': 10}


def default_working_days():
    return [0, 1, 2, 3, 4]


class PlanningSettings(models.Model):
    id = models.PositiveSmallIntegerField(primary_key=True, default=1, editable=False)
    working_days = models.JSONField(default=default_working_days, blank=True)
    open_time = models.TimeField(default=time(8))
    close_time = models.TimeField(default=time(18))
    break_start = models.TimeField(default=time(12))
    break_end = models.TimeField(default=time(13))
    horizon_days = models.PositiveSmallIntegerField(default=28, validators=[MinValueValidator(1), MaxValueValidator(90)])
    weights = models.JSONField(default=default_weights)
    step_rules = models.JSONField(default=dict, blank=True)
    revision = models.PositiveBigIntegerField(default=1)
    applied_revision = models.PositiveBigIntegerField(default=0)
    last_recalculated_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.CheckConstraint(condition=models.Q(id=1), name='planning_single_settings')]


class EmployeeQualification(models.Model):
    employee = models.ForeignKey('api.EmployeeProfile', on_delete=models.CASCADE, related_name='planning_qualifications')
    qualification = models.SlugField(max_length=64)
    proficiency_level = models.PositiveSmallIntegerField(default=1, validators=[MinValueValidator(1), MaxValueValidator(5)])
    valid_until = models.DateField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['employee', 'qualification'], name='planning_unique_qualification'),
            models.CheckConstraint(condition=models.Q(proficiency_level__gte=1, proficiency_level__lte=5), name='planning_proficiency_range'),
        ]


class EmployeeAvailability(models.Model):
    employee = models.ForeignKey('api.EmployeeProfile', on_delete=models.CASCADE, related_name='planning_availability')
    availability_type = models.CharField(max_length=8, choices=[('SHIFT', 'Horaire'), ('ABSENCE', 'Absence'), ('BREAK', 'Pause')])
    weekday = models.PositiveSmallIntegerField(null=True, blank=True, validators=[MaxValueValidator(6)])
    start_time = models.TimeField(null=True, blank=True)
    end_time = models.TimeField(null=True, blank=True)
    effective_from = models.DateField(null=True, blank=True)
    effective_until = models.DateField(null=True, blank=True)
    starts_at = models.DateTimeField(null=True, blank=True)
    ends_at = models.DateTimeField(null=True, blank=True)
    notes = models.CharField(max_length=500, blank=True)

    class Meta:
        ordering = ['employee_id', 'weekday', 'starts_at', 'pk']
        indexes = [models.Index(fields=['employee', 'starts_at', 'ends_at'], name='planning_absence_interval')]
        constraints = [models.CheckConstraint(condition=(
            models.Q(availability_type='SHIFT', weekday__gte=0, weekday__lte=6, start_time__isnull=False,
                     end_time__gt=models.F('start_time'), starts_at__isnull=True, ends_at__isnull=True)
            | models.Q(availability_type__in=['ABSENCE', 'BREAK'], starts_at__isnull=False,
                       ends_at__gt=models.F('starts_at'), weekday__isnull=True)
        ), name='planning_availability_shape')]


ACTIVE_BOOKINGS = ['READY', 'SCHEDULED', 'IN_PROGRESS', 'PAUSED']


class PlanningTask(models.Model):
    class Status(models.TextChoices):
        PENDING = 'PENDING', 'En attente'
        READY = 'READY', 'Prête'
        SCHEDULED = 'SCHEDULED', 'Planifiée'
        IN_PROGRESS = 'IN_PROGRESS', 'En cours'
        PAUSED = 'PAUSED', 'En pause'
        BLOCKED = 'BLOCKED', 'Bloquée'
        COMPLETED = 'COMPLETED', 'Terminée'
        CANCELLED = 'CANCELLED', 'Annulée'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    prescription = models.ForeignKey('api.Prescription', on_delete=models.PROTECT, related_name='planning_tasks')
    workflow_step = models.CharField(max_length=32)
    title = models.CharField(max_length=160)
    description = models.TextField(blank=True)
    production_attempt = models.PositiveIntegerField(default=1)
    intake_revision = models.PositiveIntegerField(default=1)
    generation = models.PositiveIntegerField(default=1)
    sequence = models.PositiveSmallIntegerField()
    assigned_employee = models.ForeignKey('api.EmployeeProfile', null=True, blank=True, on_delete=models.PROTECT, related_name='planning_tasks')
    required_role = models.CharField(max_length=12)
    required_qualifications = models.JSONField(default=list, blank=True)
    estimated_duration_minutes = models.PositiveIntegerField(default=30, validators=[MinValueValidator(1), MaxValueValidator(1440)])
    actual_duration_minutes = models.PositiveIntegerField(default=0)
    worked_seconds = models.PositiveIntegerField(default=0)
    last_started_at = models.DateTimeField(null=True, blank=True)
    planned_start = models.DateTimeField(null=True, blank=True)
    planned_end = models.DateTimeField(null=True, blank=True)
    actual_start = models.DateTimeField(null=True, blank=True)
    actual_end = models.DateTimeField(null=True, blank=True)
    priority = models.PositiveSmallIntegerField(default=1)
    priority_override = models.PositiveSmallIntegerField(null=True, blank=True, validators=[MinValueValidator(1), MaxValueValidator(3)])
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PENDING)
    workstation = models.CharField(max_length=32)
    machine_type = models.CharField(max_length=20, blank=True)
    machine = models.ForeignKey('api.Machine', null=True, blank=True, on_delete=models.PROTECT, related_name='planning_tasks')
    machine_slot = models.PositiveSmallIntegerField(default=1)
    dependencies = models.ManyToManyField('self', symmetrical=False, blank=True, related_name='dependents')
    assignment_mode = models.CharField(max_length=6, choices=[('AUTO', 'Automatique'), ('MANUAL', 'Manuelle')], default='AUTO')
    locked = models.BooleanField(default=False)
    manual_block = models.BooleanField(default=False)
    blocking_reason = models.CharField(max_length=1000, blank=True)
    assignment_explanation = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['planned_start', 'prescription_id', 'sequence', 'generation']
        indexes = [
            models.Index(fields=['status', 'planned_start'], name='planning_status_start'),
            models.Index(fields=['assigned_employee', 'planned_start'], name='planning_employee_start'),
            models.Index(fields=['prescription', 'production_attempt'], name='planning_case_attempt'),
        ]
        constraints = [
            models.UniqueConstraint(fields=['prescription', 'production_attempt', 'intake_revision', 'workflow_step', 'generation'], name='planning_unique_task_step'),
            models.CheckConstraint(condition=models.Q(planned_start__isnull=True, planned_end__isnull=True) | models.Q(planned_start__isnull=False, planned_end__gt=models.F('planned_start')), name='planning_valid_interval'),
            models.CheckConstraint(condition=models.Q(estimated_duration_minutes__gte=1), name='planning_positive_duration'),
            models.CheckConstraint(condition=models.Q(priority__gte=1, priority__lte=3), name='planning_priority_range'),
            ExclusionConstraint(name='planning_employee_no_overlap', expressions=[
                ('assigned_employee', RangeOperators.EQUAL),
                (models.Func('planned_start', 'planned_end', models.Value('[)'), function='TSTZRANGE', output_field=DateTimeRangeField()), RangeOperators.OVERLAPS),
            ], condition=models.Q(status__in=ACTIVE_BOOKINGS, assigned_employee__isnull=False, planned_start__isnull=False)),
            ExclusionConstraint(name='planning_machine_no_overlap', expressions=[
                ('machine', RangeOperators.EQUAL), ('machine_slot', RangeOperators.EQUAL),
                (models.Func('planned_start', 'planned_end', models.Value('[)'), function='TSTZRANGE', output_field=DateTimeRangeField()), RangeOperators.OVERLAPS),
            ], condition=models.Q(status__in=ACTIVE_BOOKINGS, machine__isnull=False, planned_start__isnull=False)),
        ]


class PlanningEvent(ImmutableEvidence):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    task = models.ForeignKey(PlanningTask, null=True, blank=True, on_delete=models.PROTECT, related_name='events')
    prescription = models.ForeignKey('api.Prescription', null=True, blank=True, on_delete=models.PROTECT, related_name='planning_events')
    kind = models.CharField(max_length=40)
    actor = models.CharField(max_length=255)
    notes = models.TextField(blank=True)
    payload = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at', 'id']
        indexes = [models.Index(fields=['created_at', 'kind'], name='planning_event_time')]
