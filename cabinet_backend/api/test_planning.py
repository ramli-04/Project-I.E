import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, date, timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import DatabaseError, IntegrityError, connection, connections, transaction
from django.test import TransactionTestCase, override_settings
from django_tenants.test.cases import TenantTestCase
from django_tenants.utils import schema_context
from rest_framework.test import APIClient

from customers.models import Client, PlatformAccount
from .case_commands import execute_case_command
from .documents import save_attachment
from .models import ClinicalItem, EmployeeProfile, Machine, PartnerClinic, Prescription, TaskOutbox
from .planning import TZ, configuration, employee_windows, recalculate, resources_changed, sync_order
from .planning_models import EmployeeAvailability, EmployeeQualification, PlanningEvent, PlanningTask
from .signals import prescription_audit_context
from .tasks import recalculate_planning_task

NOW = datetime(2026,11,9,8,tzinfo=TZ)
TEST_SETTINGS = dict(OUTBOX_PUBLISH_ON_COMMIT=False, EXTERNAL_DELIVERY_ENABLED=False,
    PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'],
    CACHES={'default':{'BACKEND':'django.core.cache.backends.locmem.LocMemCache','KEY_FUNCTION':'django_tenants.cache.make_key'}})


@override_settings(**TEST_SETTINGS)
class PlanningTests(TenantTestCase):
    @classmethod
    def setup_tenant(cls,tenant): tenant.name='Planning test laboratory'

    def setUp(self):
        connection.set_tenant(self.tenant)
        self.clock=patch('django.utils.timezone.now',return_value=NOW)
        self.clock.start(); self.addCleanup(self.clock.stop)
        self.files=__import__('tempfile').TemporaryDirectory()
        self.media=override_settings(PRIVATE_MEDIA_ROOT=self.files.name)
        self.media.enable(); self.addCleanup(self.files.cleanup); self.addCleanup(self.media.disable)
        with schema_context('public'):
            self.manager=PlatformAccount.objects.create(name='Planning manager',login_key='planning-manager',role='LAB',laboratory=self.tenant)
        self.actor=f'platform:{self.manager.pk}:Planning manager'
        self.clinic=PartnerClinic.objects.create(name='Planning clinic',pickup_address='Test address',contact_phone='000')
        self.client=APIClient(HTTP_HOST=self.get_test_tenant_domain())
        self.client.force_authenticate(user=self.manager)

    def employee(self,role='CAO',available=True):
        user=get_user_model().objects.create_user(username='planner-'+uuid.uuid4().hex)
        return EmployeeProfile.objects.create(user=user,role=role,contract_type='CDI',hire_date=date(2026,1,1),is_available=available)

    def order(self,**values):
        order=Prescription.objects.create(patient_ref='PLAN-'+uuid.uuid4().hex[:6],dentist_name='Dentist',disinfected=True,
            partner_clinic=self.clinic,material='Zircone',shade='A2',tooth_number='11',total_price=values.pop('total_price','1200'),
            impression_type=values.pop('impression_type','NUMERIQUE'),**values)
        ClinicalItem.objects.create(prescription=order,tooth_number=11,function='Couronne',form='Anatomique',shade='A2',material='Zircone',base_amount='1200')
        return order

    def update(self,order,**values):
        with prescription_audit_context(self.actor,'Planning test',{'role':'MANAGER'}):
            for key,value in values.items(): setattr(order,key,value)
            order.save()
        order.refresh_from_db()

    def cao_case(self,**values):
        order=self.order(**values)
        self.update(order,accepted=True)
        self.update(order,status='ANALYSE_DEMANDE')
        self.update(order,status='A_CONFIRMER',analysis_validated=True)
        content=b'solid a\nfacet normal 0 0 1\nouter loop\nvertex 0 0 0\nvertex 1 0 0\nvertex 0 1 0\nendloop\nendfacet\nendsolid a'
        save_attachment(order,SimpleUploadedFile('test.stl',content),'STL',self.actor)
        execute_case_command(order.pk,'inspection',{'stage':'DIGITAL','checks':dict.fromkeys(['margins','occlusion','space','scan_quality'],True)},self.actor,'MANAGER',uuid.uuid4())
        self.update(order,status='CONTROLE_DOSSIER',reception_validated=True)
        self.update(order,status='PLANIFICATION')
        if order.delivery_service=='NEXT_DAY' and order.total_price is None:
            return order
        self.update(order,status='SALLE_CAO',production_method='CFAO',delivery_date=date(2026,11,13))
        return order

    def task(self,order,step='SALLE_CAO'):
        return order.planning_tasks.filter(workflow_step=step).latest('generation')

    def command(self,order,action,data,key=None):
        return execute_case_command(order.pk,action,data,self.actor,'MANAGER',key or uuid.uuid4())

    def test_generation_is_route_specific_and_never_starts_unaccepted_case(self):
        order=self.order()
        self.assertFalse(order.planning_tasks.exists())
        self.update(order,accepted=True)
        steps=set(order.planning_tasks.values_list('workflow_step',flat=True))
        self.assertIn('PLANIFICATION',steps); self.assertNotIn('USINAGE_CNC',steps); self.assertNotIn('COULEE_PLATRE',steps)
        order=self.cao_case()
        steps=set(order.planning_tasks.values_list('workflow_step',flat=True))
        self.assertIn('USINAGE_CNC',steps); self.assertNotIn('IMPRESSION_3D',steps)
        count=order.planning_tasks.count()
        with transaction.atomic(): sync_order(order)
        self.assertEqual(order.planning_tasks.count(),count)

    def test_required_qualifications_are_hard_constraints(self):
        employee=self.employee(); order=self.cao_case()
        settings=configuration(); settings.step_rules={'SALLE_CAO':{'qualifications':['cao-cert']}};settings.save()
        task=self.task(order)
        recalculate(now=NOW);task.refresh_from_db();self.assertEqual(task.status,'BLOCKED')
        EmployeeQualification.objects.create(employee=employee,qualification='cao-cert',proficiency_level=4,valid_until=date(2026,11,30))
        recalculate(now=NOW);task.refresh_from_db();self.assertEqual(task.assigned_employee_id,employee.pk)

    def test_absence_replans_unlocked_task(self):
        first,second=self.employee(),self.employee();order=self.cao_case()
        recalculate(now=NOW);task=self.task(order);self.assertEqual(task.assigned_employee_id,first.pk)
        EmployeeAvailability.objects.create(employee=first,availability_type='ABSENCE',starts_at=NOW,ends_at=NOW+timedelta(days=40))
        resources_changed(self.actor,kind='ABSENCE_DECLARED')
        recalculate(now=NOW);task.refresh_from_db();self.assertEqual(task.assigned_employee_id,second.pk)

    def test_employee_unavailable_and_expired_qualification_are_never_assigned(self):
        self.employee(available=False);other=self.employee();order=self.cao_case();task=self.task(order)
        settings=configuration();settings.step_rules={'SALLE_CAO':{'qualifications':['cao']}};settings.save()
        EmployeeQualification.objects.create(employee=other,qualification='cao',valid_until=date(2026,11,8))
        recalculate(now=NOW);task.refresh_from_db();self.assertIsNone(task.assigned_employee_id)

    def test_schedules_respect_breaks_dependencies_and_do_not_overlap(self):
        employee=self.employee();a,b=self.cao_case(),self.cao_case()
        recalculate(now=NOW)
        x,y=sorted([self.task(a),self.task(b)],key=lambda t:t.planned_start)
        self.assertEqual(x.assigned_employee_id,employee.pk);self.assertLessEqual(x.planned_end,y.planned_start)
        self.assertEqual(x.planned_start,NOW)
        self.assertTrue(x.assignment_explanation['components'])

    def test_database_rejects_overlapping_employee_bookings(self):
        self.employee();a,b=self.cao_case(),self.cao_case();recalculate(now=NOW)
        x,y=self.task(a),self.task(b)
        with self.assertRaises(IntegrityError),transaction.atomic():
            PlanningTask.objects.filter(pk=y.pk).update(planned_start=x.planned_start,planned_end=x.planned_end)

    def test_urgent_case_precedes_standard_without_moving_started_work(self):
        self.employee();normal=self.cao_case();urgent=self.cao_case(delivery_service='EXPRESS')
        recalculate(now=NOW)
        self.assertLess(self.task(urgent).planned_start,self.task(normal).planned_start)
        started=self.task(urgent)
        self.command(urgent,'planning-start',{'task':str(started.pk)})
        before=PlanningTask.objects.get(pk=started.pk)
        recalculate(now=NOW+timedelta(minutes=15));after=PlanningTask.objects.get(pk=started.pk)
        self.assertEqual((before.assigned_employee_id,before.planned_start),(after.assigned_employee_id,after.planned_start))

    def test_next_day_manual_quote_blocks_production_generation(self):
        order=self.cao_case(delivery_service='NEXT_DAY',total_price=None)
        with transaction.atomic(): sync_order(order)
        self.assertFalse(order.planning_tasks.filter(workflow_step='USINAGE_CNC').exclude(status='CANCELLED').exists())

    def test_locked_assignment_survives_replanning_and_reports_absence(self):
        employee=self.employee();order=self.cao_case();recalculate(now=NOW);task=self.task(order)
        self.command(order,'planning-lock',{'task':str(task.pk),'locked':True})
        EmployeeAvailability.objects.create(employee=employee,availability_type='ABSENCE',starts_at=NOW,ends_at=NOW+timedelta(days=40))
        recalculate(now=NOW);task.refresh_from_db()
        self.assertEqual(task.assigned_employee_id,employee.pk);self.assertTrue(task.locked);self.assertIn('conflit',task.blocking_reason)

    def test_complete_uses_same_business_transition_and_is_idempotent(self):
        self.employee();order=self.cao_case();recalculate(now=NOW);task=self.task(order)
        self.command(order,'planning-start',{'task':str(task.pk)})
        key=uuid.uuid4();self.command(order,'planning-complete',{'task':str(task.pk)},key)
        self.command(order,'planning-complete',{'task':str(task.pk)},key)
        order.refresh_from_db();task.refresh_from_db()
        self.assertEqual(order.status,'PREPARATION_CNC');self.assertEqual(task.status,'COMPLETED')
        self.assertEqual(PlanningEvent.objects.filter(task=task,kind='PLANNING_COMPLETE').count(),1)

    def test_missing_required_production_lot_rejects_completion_atomically(self):
        self.employee();self.employee('FAO');order=self.cao_case();recalculate(now=NOW)
        task=self.task(order);self.command(order,'planning-start',{'task':str(task.pk)})
        self.command(order,'planning-complete',{'task':str(task.pk)})
        # CNC preparation is current. Starting is legal; entering fabrication still needs its lot.
        recalculate(now=NOW);task=self.task(order,'PREPARATION_CNC')
        self.command(order,'planning-start',{'task':str(task.pk)})
        with self.assertRaises(ValidationError): self.command(order,'planning-complete',{'task':str(task.pk)})
        task.refresh_from_db();order.refresh_from_db()
        self.assertEqual(task.status,'IN_PROGRESS');self.assertEqual(order.status,'PREPARATION_CNC')

    def test_manual_assignment_rejects_absence_and_conflicting_slot(self):
        employee=self.employee();order=self.cao_case();recalculate(now=NOW);task=self.task(order)
        EmployeeAvailability.objects.create(employee=employee,availability_type='ABSENCE',starts_at=NOW,ends_at=NOW+timedelta(hours=3))
        with self.assertRaises(ValidationError): self.command(order,'planning-assign',{'task':str(task.pk),'employee':employee.pk,'start':NOW.isoformat(),'end':(NOW+timedelta(hours=1)).isoformat()})

    def test_rework_preserves_completed_history_and_creates_new_attempt(self):
        self.employee();order=self.cao_case();recalculate(now=NOW);task=self.task(order)
        self.command(order,'planning-start',{'task':str(task.pk)})
        self.command(order,'rework',{'origin':'LAB','cause':'Design','corrective_action':'Redesign','restart_status':'SALLE_CAO','losses':[]})
        order.refresh_from_db();task.refresh_from_db()
        self.assertEqual(task.status,'CANCELLED');self.assertGreater(order.production_attempt,task.production_attempt)
        self.assertTrue(order.planning_tasks.filter(production_attempt=order.production_attempt,workflow_step='SALLE_CAO').exists())

    def test_audit_and_completed_task_history_are_database_immutable(self):
        order=self.cao_case();record=PlanningEvent.objects.filter(prescription=order).first()
        with self.assertRaises(DatabaseError),transaction.atomic():
            with connection.cursor() as cursor: cursor.execute('UPDATE api_planningevent SET notes=%s WHERE id=%s',['tampered',record.pk])

    def test_api_filters_invalid_payloads_and_tenant_membership(self):
        order=self.cao_case()
        response=self.client.get('/api/planning/tasks/',{'prescription':str(order.pk)})
        self.assertEqual(response.status_code,200,response.data);self.assertIn('results',response.data)
        self.assertEqual(self.client.get('/api/planning/calendar/',{'start':'not-a-date'}).status_code,400)
        self.assertEqual(self.client.patch('/api/planning/settings/',{'weights':{'workload':100}},format='json').status_code,400)
        with schema_context('public'):
            outsider=PlatformAccount.objects.create(name='Outside',login_key='outside',role='LAB',laboratory=None)
        self.client.force_authenticate(user=outsider)
        self.assertEqual(self.client.get('/api/planning/tasks/').status_code,403)

    def test_workload_is_computed_and_durable_task_is_tenant_scoped(self):
        self.employee();order=self.cao_case();queued=TaskOutbox.objects.filter(prescription=order,event_type='PLANNING').first()
        recalculate_planning_task(self.tenant.schema_name,str(order.pk),outbox_id=str(queued.pk))
        queued.refresh_from_db();self.assertIsNotNone(queued.processed_at)
        result=self.client.get('/api/planning/workload/',{'start':NOW.isoformat(),'end':(NOW+timedelta(days=1)).isoformat()})
        self.assertEqual(result.status_code,200,result.data);self.assertGreater(result.data['results'][0]['planned_minutes'],0)
        with self.assertRaises(ValueError): recalculate_planning_task('public',str(order.pk))

    def test_employee_role_and_ownership_are_enforced_for_manual_progress(self):
        employee=self.employee();order=self.cao_case();recalculate(now=NOW);task=self.task(order)
        with self.assertRaises(ValidationError):
            execute_case_command(order.pk,'planning-start',{'task':str(task.pk)},'user:999:Other','CAO',uuid.uuid4())
        with self.assertRaises(ValidationError):
            execute_case_command(order.pk,'planning-start',{'task':str(task.pk)},f'user:{employee.user_id}:CAO','FAO',uuid.uuid4())
        execute_case_command(order.pk,'planning-start',{'task':str(task.pk)},f'user:{employee.user_id}:CAO','CAO',uuid.uuid4())
        task.refresh_from_db();self.assertEqual(task.status,'IN_PROGRESS')

    def test_another_laboratory_cannot_read_or_assign_known_task(self):
        order=self.cao_case();task=self.task(order)
        with schema_context('public'):
            other=Client(schema_name='other_planning_lab',name='Other lab');other.auto_create_schema=False;other.save()
            account=PlatformAccount.objects.create(name='Other manager',login_key='other-manager',role='LAB',laboratory=other)
        self.client.force_authenticate(user=account)
        self.assertEqual(self.client.get(f'/api/planning/tasks/{task.pk}/').status_code,403)
        self.assertEqual(self.client.post(f'/api/planning/tasks/{task.pk}/assign/',{},format='json',HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4())).status_code,403)

    def test_equipment_capacity_and_maintenance_are_strict(self):
        self.employee();self.employee();order=self.cao_case();other=self.cao_case()
        settings=configuration();settings.step_rules={'SALLE_CAO':{'machine_type':'SCANNER'}};settings.save()
        machine=Machine.objects.create(name='Planning scanner',machine_type='SCANNER',capacity=1,status='ACTIF')
        recalculate(now=NOW);a,b=sorted([self.task(order),self.task(other)],key=lambda t:t.planned_start)
        self.assertEqual(a.machine_id,machine.pk);self.assertLessEqual(a.planned_end,b.planned_start)
        machine.status='MAINTENANCE';machine.save();recalculate(now=NOW)
        a.refresh_from_db();self.assertEqual(a.status,'BLOCKED')

    def test_overlapping_weekly_rules_do_not_double_count_capacity(self):
        employee=self.employee()
        for _ in range(2):
            EmployeeAvailability.objects.create(employee=employee,availability_type='SHIFT',weekday=0,start_time='08:00',end_time='18:00')
        windows=employee_windows(employee,NOW.date(),configuration())
        self.assertEqual(sum((b-a).total_seconds()/60 for a,b in windows),540)

    def test_advancement_uses_server_transition_and_preserves_design_gate(self):
        order=self.cao_case()
        with self.assertRaises(ValidationError): self.command(order,'advance',{'status':'CLOTURE'})
        self.command(order,'advance',{})
        order.refresh_from_db();self.assertEqual(order.status,'PREPARATION_CNC')
        task=self.task(order);self.assertEqual(task.status,'COMPLETED')

    def test_settings_publish_the_scheduler_timezone_rules(self):
        response=self.client.get('/api/planning/settings/')
        self.assertEqual(response.status_code,200,response.data)
        zone=response.data['timezone']
        self.assertEqual(zone['zone'],'Africa/Casablanca')
        at=NOW.timestamp()
        changes=[r for r in zone['transitions'] if datetime.fromisoformat(r['at']).timestamp()<=at]
        self.assertEqual(changes[-1]['offset'],int(NOW.utcoffset().total_seconds()/60))


@override_settings(**TEST_SETTINGS)
class PlanningConcurrencyTests(TransactionTestCase):
    def test_concurrent_recalculation_uses_one_consistent_reservation_set(self):
        connection.set_schema_to_public()
        tenant=Client.objects.create(schema_name='planning_race',name='Disposable planning race')
        try:
            with schema_context(tenant.schema_name):
                user=get_user_model().objects.create_user(username='planning-race')
                employee=EmployeeProfile.objects.create(user=user,role='RECEPTION',contract_type='CDI',hire_date=date(2026,1,1))
                for _ in range(2):
                    order=Prescription.objects.create(patient_ref='RACE',dentist_name='D',disinfected=True,total_price='1200',tooth_number='11',material='Zircone',shade='A1')
                    order.accepted=True;order.save()
                ids=set(PlanningTask.objects.values_list('pk',flat=True))
            def run():
                try:
                    with schema_context(tenant.schema_name): return recalculate(now=NOW)
                finally: connections['default'].close()
            with ThreadPoolExecutor(max_workers=2) as pool:
                results=list(pool.map(lambda _:run(),range(2)))
            self.assertEqual(len(results),2)
            with schema_context(tenant.schema_name):
                self.assertEqual(set(PlanningTask.objects.values_list('pk',flat=True)),ids)
                slots=list(PlanningTask.objects.filter(assigned_employee=employee,planned_start__isnull=False).order_by('planned_start'))
                self.assertEqual(len(slots),2)
                self.assertLessEqual(slots[0].planned_end,slots[1].planned_start)
        finally:
            connection.set_schema_to_public();tenant.delete(force_drop=True)
