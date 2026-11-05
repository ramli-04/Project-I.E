"""Authenticated laboratory planning API. Source progression uses case commands."""
import uuid
from datetime import datetime, timedelta
from functools import lru_cache

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction
from django.db.models import F, Q
from django.utils import timezone
from rest_framework import serializers, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from .business_views import BusinessPagination, translate_error
from .case_serializers import actor_identity
from .models import EmployeeProfile, Prescription, TaskOutbox
from .permissions import LaboratoryResourcePermission, actor_role
from .planning import (DEFAULT_RULES, EXTERNAL, TZ, case_risk, configuration, deadline, employee_name,
                       employee_windows, lock_planning, lock_resources, request_replan, resources_changed)
from .planning_models import EmployeeAvailability, EmployeeQualification, PlanningEvent, PlanningSettings, PlanningTask
from .workflow import LABELS


@lru_cache(maxsize=4)
def timezone_transitions(year):
    """Publish the scheduler's tzdata so browser ICU versions cannot shift slots."""
    from datetime import timezone as utc
    first = datetime(year-3,1,1,tzinfo=utc.utc)
    last = datetime(year+3,1,1,tzinfo=utc.utc)
    offset = lambda value: int(value.astimezone(TZ).utcoffset().total_seconds()/60)
    entries = [{'at':first.isoformat(),'offset':offset(first)}]
    day = first
    while day < last:
        following = min(last,day+timedelta(days=1))
        if offset(day) != offset(following):
            lo,hi = int(day.timestamp()),int(following.timestamp())
            before = offset(day)
            while hi-lo>1:
                middle=(lo+hi)//2
                if offset(datetime.fromtimestamp(middle,utc.utc)) == before: lo=middle
                else: hi=middle
            changed=datetime.fromtimestamp(hi,utc.utc)
            entries.append({'at':changed.isoformat(),'offset':offset(changed)})
        day=following
    return {'zone':'Africa/Casablanca','until':last.isoformat(),'transitions':entries}


class ResourcePlanningMixin:
    def perform_create(self, serializer):
        with transaction.atomic():
            anchor = lock_resources()
            obj = serializer.save()
            resources_changed(actor_identity(self.request),anchor=anchor,resources_locked=True,kind='RESOURCE_CREATED',model=obj._meta.model_name,id=str(obj.pk))

    def perform_update(self, serializer):
        with transaction.atomic():
            anchor = lock_resources()
            obj = serializer.save()
            resources_changed(actor_identity(self.request),anchor=anchor,resources_locked=True,kind='RESOURCE_UPDATED',model=obj._meta.model_name,id=str(obj.pk))

    def perform_destroy(self, instance):
        with transaction.atomic():
            anchor = lock_resources()
            identity = str(instance.pk)
            try: instance.delete()
            except IntegrityError as exc: raise ValidationError('Cette ressource est liée à un historique de production.') from exc
            resources_changed(actor_identity(self.request),anchor=anchor,resources_locked=True,kind='RESOURCE_DELETED',id=identity)


class AvailabilitySerializer(serializers.ModelSerializer):
    class Meta:
        model = EmployeeAvailability
        fields = '__all__'

    def validate(self, attrs):
        merged = {field.name:getattr(self.instance,field.name) for field in self.Meta.model._meta.fields} if self.instance else {}
        merged.update(attrs)
        if merged.get('availability_type') == 'SHIFT':
            if merged.get('weekday') not in range(7) or not merged.get('start_time') or not merged.get('end_time') or merged['start_time'] >= merged['end_time']:
                raise ValidationError('Choisissez un jour et un horaire de début/fin cohérent.')
            if merged.get('starts_at') or merged.get('ends_at'): raise ValidationError('Un horaire hebdomadaire ne comporte pas de dates ponctuelles.')
        else:
            if not merged.get('starts_at') or not merged.get('ends_at') or merged['starts_at'] >= merged['ends_at']:
                raise ValidationError('Début et fin d’absence/pause sont obligatoires et doivent être ordonnés.')
            if merged.get('weekday') is not None: raise ValidationError('Une absence ponctuelle ne comporte pas de jour hebdomadaire.')
        if merged.get('effective_from') and merged.get('effective_until') and merged['effective_from'] > merged['effective_until']:
            raise ValidationError('La période de validité est inversée.')
        return attrs


class AvailabilityViewSet(ResourcePlanningMixin, viewsets.ModelViewSet):
    permission_classes = [LaboratoryResourcePermission]
    write_roles = {'MANAGER'}
    queryset = EmployeeAvailability.objects.all()
    serializer_class = AvailabilitySerializer
    pagination_class = BusinessPagination

    def get_queryset(self):
        query = super().get_queryset()
        if self.request.query_params.get('employee'):
            try: query = query.filter(employee_id=int(self.request.query_params['employee']))
            except ValueError as exc: raise ValidationError('Identifiant du collaborateur invalide.') from exc
        return query


class QualificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmployeeQualification
        fields = '__all__'


class QualificationViewSet(ResourcePlanningMixin, viewsets.ModelViewSet):
    permission_classes = [LaboratoryResourcePermission]
    write_roles = {'MANAGER'}
    queryset = EmployeeQualification.objects.all().order_by('employee_id','qualification','pk')
    serializer_class = QualificationSerializer
    pagination_class = BusinessPagination


class SettingsSerializer(serializers.ModelSerializer):
    defaults = serializers.SerializerMethodField()
    timezone = serializers.SerializerMethodField()

    def get_timezone(self,obj):
        return timezone_transitions(timezone.now().year)

    class Meta:
        model = PlanningSettings
        fields = '__all__'
        read_only_fields = ['id','updated_at','revision','applied_revision','last_recalculated_at']

    def get_defaults(self,obj):
        return {key:{'title':LABELS.get(key,key),'role':r,'duration':d,'machine_type':m,'qualifications':[]}
                for key,(r,d,m) in DEFAULT_RULES.items()}

    def validate_weights(self,value):
        keys = {'qualification','availability','workload','urgency','continuity'}
        if not isinstance(value,dict) or set(value) != keys or any(type(v) not in {int,float} or not 0 <= v <= 100 for v in value.values()) or sum(value.values()) <= 0:
            raise ValidationError('Pondérations positives ou nulles, bornées à 100, pour chaque critère.')
        return value

    def validate_working_days(self,value):
        if not isinstance(value,list) or any(type(d) is not int or d not in range(7) for d in value) or len(value) != len(set(value)):
            raise ValidationError('Jours uniques entre 0 (lundi) et 6 (dimanche).')
        return value

    def validate_step_rules(self,value):
        if not isinstance(value,dict) or set(value)-DEFAULT_RULES.keys(): raise ValidationError('Étape de fabrication inconnue.')
        for step,rule in value.items():
            if not isinstance(rule,dict) or set(rule)-{'duration','qualifications','machine_type'}: raise ValidationError('Règle de fabrication invalide.')
            if type(rule.get('duration',30)) is not int or not 1 <= rule.get('duration',30) <= 1440: raise ValidationError('Durée comprise entre 1 et 1440 minutes.')
            qualifications=rule.get('qualifications',[])
            if not isinstance(qualifications,list) or len(qualifications)>30 or any(not isinstance(q,str) or not q or len(q)>64 for q in qualifications): raise ValidationError('Liste de codes de qualifications attendue.')
            if rule.get('machine_type','') not in {'','SCANNER','USINEUSE_CNC','FOUR_FRITTAGE','IMPRESSION_3D'}: raise ValidationError('Type de machine inconnu.')
        return value

    def validate(self,attrs):
        opening = attrs.get('open_time',self.instance.open_time)
        closing = attrs.get('close_time',self.instance.close_time)
        a,b = attrs.get('break_start',self.instance.break_start),attrs.get('break_end',self.instance.break_end)
        if not opening <= a <= b <= closing or opening >= closing: raise ValidationError('Horaires incohérents : ouverture ≤ pause ≤ fermeture.')
        return attrs


@api_view(['GET','PATCH'])
@permission_classes([LaboratoryResourcePermission])
def planning_settings(request):
    with transaction.atomic():
        anchor = lock_resources() if request.method == 'PATCH' else None
        if request.method != 'PATCH': lock_planning()
        obj = configuration()
        if request.method == 'PATCH':
            if actor_role(request) != 'MANAGER': raise ValidationError('Responsable du laboratoire requis.')
            serializer = SettingsSerializer(obj,data=request.data,partial=True)
            serializer.is_valid(raise_exception=True)
            serializer.save()
            resources_changed(actor_identity(request),anchor=anchor,resources_locked=True,kind='SETTINGS_UPDATED')
        return Response(SettingsSerializer(obj).data)


class TaskSerializer(serializers.ModelSerializer):
    employee_name = serializers.SerializerMethodField()
    patient_ref = serializers.CharField(source='prescription.patient_ref')
    source_status = serializers.CharField(source='prescription.status')
    machine_name = serializers.CharField(source='machine.name',default='')
    deadline = serializers.SerializerMethodField()
    late = serializers.SerializerMethodField()
    external = serializers.SerializerMethodField()
    can_operate = serializers.SerializerMethodField()

    class Meta:
        model = PlanningTask
        fields = '__all__'

    def get_employee_name(self,obj): return employee_name(obj.assigned_employee) if obj.assigned_employee_id else ''
    def get_deadline(self,obj): return deadline(obj.prescription,self.context['planning_settings'])
    def get_late(self,obj): return bool(obj.planned_end and obj.planned_end > self.get_deadline(obj))
    def get_external(self,obj): return obj.workflow_step in EXTERNAL
    def get_can_operate(self,obj):
        request=self.context['request']
        role=actor_role(request)
        if role=='MANAGER': return True
        employee=obj.assigned_employee
        if not employee or role != obj.required_role: return False
        from customers.models import PlatformAccount
        return employee.platform_account_id == request.user.pk if isinstance(request.user,PlatformAccount) else employee.user_id == request.user.pk


def date_period(params):
    now = timezone.localtime(timezone.now(),TZ)
    try:
        def parse(key,default):
            value = params.get(key)
            if not value: return default
            result = datetime.fromisoformat(value.replace('Z','+00:00'))
            return timezone.make_aware(result,TZ) if timezone.is_naive(result) else result
        start = parse('start',now.replace(hour=0,minute=0,second=0,microsecond=0))
        end = parse('end',start+timedelta(days=7))
        if start >= end or end-start > timedelta(days=93): raise ValueError()
        return start,end
    except (ValueError,TypeError) as exc: raise ValidationError('Période ISO valide, ordonnée et de 93 jours maximum requise.') from exc


class PlanningTaskViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [LaboratoryResourcePermission]
    write_roles = {'MANAGER'}
    serializer_class = TaskSerializer
    pagination_class = BusinessPagination
    queryset = PlanningTask.objects.select_related('prescription','assigned_employee__user','assigned_employee__platform_account','machine').prefetch_related('dependencies')

    def get_serializer_context(self):
        return {**super().get_serializer_context(),'planning_settings':configuration()}

    def get_queryset(self):
        query = super().get_queryset()
        params = self.request.query_params
        for key,field in [('employee','assigned_employee_id'),('prescription','prescription_id'),('status','status'),('role','required_role'),('workstation','workstation'),('priority','priority')]:
            if params.get(key):
                try:
                    value = uuid.UUID(params[key]) if key=='prescription' else int(params[key]) if key in {'employee','priority'} else params[key]
                    query = query.filter(**{field:value})
                except (ValueError,TypeError) as exc: raise ValidationError(f'Filtre {key} invalide.') from exc
        if params.get('start') or params.get('end') or self.request.path.endswith('/calendar/'):
            start,end = date_period(params)
            query = query.filter(Q(planned_start__lt=end,planned_end__gt=start)|Q(planned_start__isnull=True))
        if params.get('include_terminal') != 'true': query = query.exclude(status__in=['CANCELLED'])
        return query.order_by('planned_start','prescription_id','sequence','generation')

    def _command(self,request,operation):
        from .case_commands import execute_case_command
        task = self.get_object()
        if not isinstance(request.data,dict): raise ValidationError('Objet JSON requis.')
        try:
            order,result = execute_case_command(task.prescription_id,'planning-'+operation,
                {**request.data,'task':str(task.pk)},actor_identity(request),actor_role(request),request.headers.get('Idempotency-Key'))
        except (DjangoValidationError,ValueError,TypeError,IntegrityError) as exc: raise translate_error(exc) from exc
        task.refresh_from_db()
        return Response({'task':self.get_serializer(task).data,'result':result})

    @action(detail=True,methods=['post'])
    def assign(self,request,pk=None): return self._command(request,'assign')

    @action(detail=True,methods=['post'])
    def reschedule(self,request,pk=None): return self._command(request,'reschedule')

    @action(detail=True,methods=['post'])
    def lock(self,request,pk=None): return self._command(request,'lock')


class EventSerializer(serializers.ModelSerializer):
    class Meta:
        model = PlanningEvent
        fields = '__all__'


class PlanningEventViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [LaboratoryResourcePermission]
    queryset = PlanningEvent.objects.all()
    serializer_class = EventSerializer
    pagination_class = BusinessPagination

    def get_queryset(self):
        query = super().get_queryset()
        for key in ['task','prescription']:
            if self.request.query_params.get(key):
                try:
                    value = uuid.UUID(self.request.query_params[key])
                    query = query.filter(Q(prescription_id=value)|Q(task__prescription_id=value)) if key=='prescription' else query.filter(task_id=value)
                except ValueError as exc: raise ValidationError('UUID invalide.') from exc
        return query


@api_view(['POST'])
@permission_classes([LaboratoryResourcePermission])
def recalculate_view(request):
    if actor_role(request) != 'MANAGER': raise ValidationError('Responsable du laboratoire requis.')
    try: key = uuid.UUID(request.headers.get('Idempotency-Key',''))
    except ValueError as exc: raise ValidationError('Une clé UUID Idempotency-Key est requise.') from exc
    from .outbox import enqueue_event
    queued=[]
    # Backfill accepted legacy cases one source at a time; no order locks under a tenant planning lock.
    for pk in Prescription.objects.filter(accepted=True).exclude(status='CLOTURE').order_by('pk').values_list('pk',flat=True):
        with transaction.atomic():
            order=Prescription.objects.select_for_update().get(pk=pk)
            lock_planning()
            event_key=f'planning:manual:{key}:{pk}'
            prior=TaskOutbox.objects.filter(event_key=event_key).first()
            if prior: queued.append(str(prior.pk)); continue
            configuration()
            PlanningSettings.objects.filter(pk=1).update(revision=F('revision')+1)
            event=enqueue_event(order,'PLANNING',event_key)
            queued.append(str(event.pk))
    return Response({'status':'QUEUED' if queued else 'EMPTY','events':queued},status=202 if queued else 200)


@api_view(['GET'])
@permission_classes([LaboratoryResourcePermission])
def workload_view(request):
    start,end=date_period(request.query_params)
    settings=configuration()
    employees=list(EmployeeProfile.objects.select_related('user','platform_account').prefetch_related('planning_availability','planning_qualifications'))
    tasks=list(PlanningTask.objects.exclude(status__in=['COMPLETED','CANCELLED']).select_related('prescription'))
    results=[]
    for employee in employees:
        capacity=0
        day=start.astimezone(TZ).date()
        while day<=end.astimezone(TZ).date():
            capacity+=sum(max(0,(min(b,end)-max(a,start)).total_seconds()/60) for a,b in employee_windows(employee,day,settings))
            day+=timedelta(days=1)
        assigned=[t for t in tasks if t.assigned_employee_id==employee.pk and t.planned_start and t.planned_end and t.planned_start<end and start<t.planned_end]
        minutes=sum((min(t.planned_end,end)-max(t.planned_start,start)).total_seconds()/60 for t in assigned)
        results.append({'employee':employee.pk,'name':employee_name(employee),'role':employee.role,
            'planned_minutes':round(minutes,2),'available_minutes':round(capacity,2),
            'utilization':round(minutes/capacity*100,2) if capacity else None,'available':employee.is_available and capacity>0,
            'conflicts':sum(bool(t.blocking_reason) for t in assigned)})
    by_order={}
    for t in tasks: by_order.setdefault(t.prescription_id,[]).append(t)
    risks=[{'prescription':str(key),'patient_ref':values[0].prescription.patient_ref,
        **case_risk(values[0].prescription,values,settings=settings)} for key,values in by_order.items()]
    page=BusinessPagination()
    response=page.get_paginated_response(page.paginate_queryset(results,request))
    response.data.update(start=start,end=end,risks=risks,revision=settings.revision,
        applied_revision=settings.applied_revision,last_recalculated_at=settings.last_recalculated_at)
    return response


@api_view(['GET'])
@permission_classes([LaboratoryResourcePermission])
def planning_accounts(request):
    from customers.models import PlatformAccount
    if actor_role(request) != 'MANAGER': raise ValidationError('Responsable du laboratoire requis.')
    return Response(list(PlatformAccount.objects.filter(laboratory=request.tenant,is_active=True,
        role__in=['LAB','COURIER']).values('id','name','role','workstation_role')))
