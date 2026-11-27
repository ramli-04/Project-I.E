"""Tenant-local, uncached composition of existing operational and finance reads."""
from datetime import timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from django.db.models import Max, Prefetch, Sum
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from .analytics import PIPELINE
from .models import (AnalyticsRefreshState, BillingDispute, BillingPeriod, MonthlyBillingSummary,
                     MonthlyFinancialCatalog, Prescription, ReworkCase)
from .payments import receivables
from .permissions import LaboratoryResourcePermission, actor_role
from .planning import case_risk
from .planning_models import PlanningSettings, PlanningTask
from .workflow_spec import STAGES, STEPS

TZ = ZoneInfo('Africa/Casablanca')
ZERO = Decimal('0.00')


class DashboardPermission(LaboratoryResourcePermission):
    def has_permission(self, request, view):
        return super().has_permission(request, view) and actor_role(request) in {'MANAGER', 'COMPTABILITE'}


def finance_summary(now):
    today = timezone.localdate(now, TZ)
    month = today.replace(day=1)
    last_month = BillingPeriod.objects.filter(closed_at__isnull=False).aggregate(month=Max('month'))['month']
    amounts = receivables(today=today)
    state = AnalyticsRefreshState.objects.filter(pipeline=PIPELINE).first()
    refreshed = state.last_success_at if state else None
    return {
        'month': month,
        'billed_this_month': MonthlyBillingSummary.objects.filter(billing_month=month).aggregate(total=Sum('invoiced_total'))['total'] or ZERO,
        'last_closed_month': last_month,
        'invoiced_last_closed_month': (MonthlyFinancialCatalog.objects.filter(closing_month=last_month)
            .aggregate(total=Sum('gross_amount'))['total'] or ZERO) if last_month else ZERO,
        'total_receivables': sum((row['total_due'] for row in amounts), ZERO),
        'over_60_days': sum((row['buckets']['61_90'] + row['buckets']['90_plus'] for row in amounts), ZERO),
        'overpaid_amount': sum((row['overpaid_amount'] for row in amounts), ZERO),
        'open_disputes': BillingDispute.objects.filter(status='OPEN').count(),
        'analytics': {'last_refreshed_at': refreshed,
                      'stale': refreshed is None or now - refreshed > timedelta(minutes=20),
                      'refresh_failed': bool(state and state.last_error)},
    }


def operations_summary(now):
    today = timezone.localdate(now, TZ)
    week_end = today + timedelta(days=6-today.weekday())
    settings = PlanningSettings.objects.filter(pk=1).first() or PlanningSettings()
    task_query = PlanningTask.objects.exclude(status='CANCELLED')
    orders = Prescription.objects.exclude(status='CLOTURE').prefetch_related(
        Prefetch('planning_tasks', queryset=task_query, to_attr='dashboard_tasks'))
    counts = dict.fromkeys((key for key, _ in STAGES), 0)
    late, at_risk = [], []
    paused = blocked = paused_or_blocked = due_today = due_week = active = 0
    for order in orders:
        active += 1
        step = STEPS.get(order.status)
        if step:
            counts[step.stage] += 1
        tasks = [task for task in order.dashboard_tasks if task.production_attempt == order.production_attempt
                 and task.intake_revision == order.intake_revision]
        is_blocked = any(task.workflow_step == order.status and task.status == 'BLOCKED' for task in tasks)
        paused += bool(order.is_paused)
        blocked += is_blocked
        paused_or_blocked += bool(order.is_paused or is_blocked)
        # Delivery risks end at the actual delivery; fitting remains an active case.
        if order.delivered_at:
            continue
        risk = case_risk(order, tasks, now=now, settings=settings)
        due = timezone.localdate(risk['deadline'], TZ)
        due_today += due == today
        due_week += today <= due <= week_end
        row = {'id': str(order.pk), 'patient_ref': order.patient_ref, 'deadline_at': risk['deadline'],
               'projected_end': risk['projected_end'], 'stage_label': dict(STAGES).get(step.stage) if step else '',
               'risk': risk['risk']}
        if risk['risk'] == 'LATE':
            late.append(row)
        elif risk['risk'] == 'AT_RISK':
            at_risk.append(row)
    start = now - timedelta(days=30)
    reworks = ReworkCase.objects.filter(created_at__gte=start, created_at__lte=now).count()
    delivered = Prescription.objects.filter(delivered_at__gte=start, delivered_at__lte=now).count()
    return {
        'active_cases': active, 'stages': [{'key': key, 'label': label, 'count': counts[key]} for key, label in STAGES],
        'late': sorted(late, key=lambda row: (row['deadline_at'], row['id'])),
        'at_risk': sorted(at_risk, key=lambda row: (row['deadline_at'], row['id'])),
        'deliveries_due_today': due_today, 'deliveries_due_this_week': due_week,
        'paused_cases': paused, 'blocked_cases': blocked, 'paused_or_blocked_cases': paused_or_blocked,
        'rework_30_days': {'reworks': reworks, 'delivered': delivered,
                           'rate_percent': round(reworks * 100 / delivered, 1) if delivered else None},
    }


def _wire(value):
    # DRF's default Decimal encoder emits floats; money stays exact on the wire.
    if isinstance(value, Decimal):
        return format(value, '.2f')
    if isinstance(value, dict):
        return {key: _wire(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_wire(item) for item in value]
    return value


@api_view(['GET'])
@permission_classes([DashboardPermission])
def dashboard_summary(request):
    now = timezone.now()
    data = {'as_of': now, 'timezone': 'Africa/Casablanca', 'currency': 'MAD', 'finance': finance_summary(now)}
    if actor_role(request) == 'MANAGER':
        data['operations'] = operations_summary(now)
    response = Response(_wire(data))
    response['Cache-Control'] = 'no-store'
    return response
