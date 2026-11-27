"""Queue reads use isolated synthetic tenants; no workflow commands are implied."""
from datetime import date, timedelta
import uuid

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection
from django.test import override_settings
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from django_tenants.test.cases import TenantTestCase
from django_tenants.utils import schema_context
from rest_framework.test import APIClient

from customers.models import Client, PlatformAccount
from .case_commands import execute_case_command
from .models import EmployeeProfile, PartnerClinic, Prescription
from .test_planning import TEST_SETTINGS
from .test_support import WorkflowFixtures


@override_settings(**TEST_SETTINGS)
class WorkQueueTests(WorkflowFixtures, TenantTestCase):
    def setUp(self):
        super().setUp()
        connection.set_tenant(self.tenant)
        self.client = APIClient(HTTP_HOST=self.get_test_tenant_domain())
        self.manager = self.account('MANAGER')
        self.client.force_authenticate(self.manager)
        self.clinic = PartnerClinic.objects.create(name='Queue clinic', pickup_address='Synthetic test address')

    def account(self, role):
        with schema_context('public'):
            return PlatformAccount.objects.create(name='Queue '+role, login_key='queue-'+role,
                role='LAB', workstation_role=role, laboratory=self.tenant)

    def order(self, status='DEMANDE_RECUE', **values):
        paused = values.pop('is_paused', False)
        reason = values.pop('pause_reason', '')
        order = Prescription.objects.create(patient_ref='QUEUE-'+str(Prescription.objects.count()), dentist_name='Queue dentist',
            tooth_number=11, shade='A1', material='Zircone', disinfected=True, status=status,
            partner_clinic=self.clinic,
            **{'accepted': True, 'total_price': '1200', 'impression_type': 'NUMERIQUE', 'production_method': 'CFAO', **values})
        # Reach every fixture through real workflow commands, keeping all guards/audits.
        if status != 'DEMANDE_RECUE':
            target = 'SALLE_CAO' if status in {'VALIDATION_CAO', 'A_REFAIRE'} else 'LIVRE' if status == 'CLOTURE' else status
            self.deliver_case(order, stop_at=target)
        if status == 'VALIDATION_CAO':
            uploaded = self.client.post(f'/api/prescriptions/{order.pk}/attachments/', {'kind': 'DESIGN',
                'file': SimpleUploadedFile('design.stl', b'solid test\nfacet normal 0 0 1\nouter loop\nvertex 0 0 0\nvertex 1 0 0\nvertex 0 1 0\nendloop\nendfacet\nendsolid test')}, format='multipart')
            self.assertEqual(uploaded.status_code, 201, uploaded.data)
            self.workflow_command(order, 'design-request', {'attachment': uploaded.data['id']})
        elif status == 'A_REFAIRE':
            self.workflow_command(order, 'rework', {'origin': 'LAB', 'cause': 'Correction',
                'corrective_action': 'Revoir le design', 'restart_status': 'SALLE_CAO', 'losses': []})
        elif status == 'CLOTURE':
            execute_case_command(order.pk, 'fitting', {'passed': True}, 'platform:1:Queue dentist', 'DENTIST', uuid.uuid4())
            order.refresh_from_db()
        if paused:
            self.workflow_command(order, 'pause', {'paused': True, 'notes': reason})
        return order

    def task(self, order, **values):
        task = order.planning_tasks.filter(workflow_step=order.status).latest('generation')
        for key, value in values.items():
            setattr(task, key, value)
        task.save()
        return task

    def employee(self, role='FAO', account=None):
        return EmployeeProfile.objects.create(role=role, platform_account=account,
            user=get_user_model().objects.create_user(username='queue-'+role+'-'+str(EmployeeProfile.objects.count())),
            contract_type='CDI', hire_date=date(2026, 1, 1))

    def queue(self, account=None, **params):
        if account:
            self.client.force_authenticate(account)
        response = self.client.get('/api/work-queue/', params)
        self.assertEqual(response.status_code, 200, response.data)
        return {row['id']: row for row in response.data['results']}

    def test_reception_accept_legacy_analysis_and_paused(self):
        new = self.order(accepted=False)
        legacy = self.order()
        analysis = self.order('ANALYSE_DEMANDE')
        paused = self.order('A_CONFIRMER', is_paused=True, pause_reason='Documents manquants')
        hidden = self.order('PREPARATION_CNC')
        rows = self.queue(self.account('RECEPTION'))
        self.assertEqual(rows[str(new.pk)]['primary_action']['label'], 'Accepter et analyser')
        self.assertEqual(rows[str(legacy.pk)]['primary_action']['command'], 'advance')
        self.assertEqual(rows[str(analysis.pk)]['group'], 'TODO')
        self.assertEqual(rows[str(paused.pk)]['group'], 'PAUSED')
        self.assertEqual(rows[str(paused.pk)]['pause_reason'], 'Documents manquants')
        self.assertNotIn(str(hidden.pk), rows)

    def test_cao_and_quality_ownership_and_inspection(self):
        design = self.order('SALLE_CAO', design_validation_requested=True)
        qc = self.order('CONTROLE_QUALITE')
        rows = self.queue(self.account('CAO'))
        self.assertIn(str(design.pk), rows)
        self.assertNotIn(str(qc.pk), rows)
        rows = self.queue(self.account('QUALITE'))
        self.assertEqual(rows[str(qc.pk)]['primary_action']['inspection_stage'], 'QUALITY')
        self.assertNotIn(str(design.pk), rows)

    def test_work_assignee_unassigned_other_and_platform_identity(self):
        account = self.account('FAO')
        employee = self.employee(account=account)
        assigned, unassigned, other = [self.order('PREPARATION_CNC') for _ in range(3)]
        self.task(assigned, assigned_employee=employee, status='READY')
        self.task(other, assigned_employee=self.employee(), status='READY')
        rows = self.queue(account)
        self.assertEqual(rows[str(assigned.pk)]['group'], 'TODO')
        self.assertTrue(rows[str(assigned.pk)]['task']['can_operate'])
        for case in (unassigned, other):
            self.assertEqual(rows[str(case.pk)]['group'], 'TEAM')
            self.assertFalse(rows[str(case.pk)]['task']['can_operate'])

    def test_django_employee_identity_uses_the_shared_permission(self):
        employee = self.employee()
        order = self.order('FINITION')
        task = self.task(order, assigned_employee=employee, status='IN_PROGRESS')
        self.client.force_authenticate(employee.user)
        rows = self.queue()
        self.assertTrue(rows[str(order.pk)]['task']['can_operate'])
        from .planning_views import TaskSerializer
        request = self.client.get('/api/work-queue/').wsgi_request
        request.user = employee.user
        self.assertEqual(TaskSerializer(context={'request': request}).get_can_operate(task), True)

    def test_accounting_only_sees_unquoted_j1_and_manager_filter(self):
        quote = self.order(delivery_service='NEXT_DAY', total_price=None)
        self.order(delivery_service='NEXT_DAY', total_price='1500')
        self.order('SALLE_CAO')
        rows = self.queue(self.account('COMPTABILITE'))
        self.assertEqual(list(rows), [str(quote.pk)])
        self.assertEqual(rows[str(quote.pk)]['primary_action']['command'], 'quote')
        self.assertEqual(self.queue(self.manager, role='COMPTABILITE').keys(), rows.keys())
        self.assertEqual(len(self.queue(role='CAO')), 1)
        self.assertEqual(self.client.get('/api/work-queue/?role=INVALID').status_code, 400)

    def test_external_waiting_and_machine_confirmations_remain_accessible(self):
        external = [self.order('ATTENTE_RAMASSAGE', impression_type='PHYSIQUE'),
                    self.order('VALIDATION_CAO', design_validation_requested=True), self.order('LIVRE')]
        closed = self.order('CLOTURE')
        machine = self.order('USINAGE_CNC')
        account = self.account('FAO'); employee = self.employee(account=account)
        task = self.task(machine, assigned_employee=employee, status='IN_PROGRESS', resource_phase='CYCLE', estimated_duration_minutes=60)
        rows = self.queue(account)
        self.assertNotIn(str(closed.pk), rows)
        self.assertTrue(all(rows[str(case.pk)]['group'] == 'WAITING' for case in external))
        self.assertEqual(rows[str(machine.pk)]['primary_action']['command'], 'cycle-finished')
        task.resource_phase = 'AWAITING_UNLOAD'; task.save()
        row = self.queue()[str(machine.pk)]
        self.assertEqual(row['group'], 'WAITING')
        self.assertEqual(row['primary_action']['command'], 'begin-unload')

    def test_future_booking_and_dependency_are_explanations_not_start_buttons(self):
        order = self.order('PREPARATION_CNC')
        now = timezone.now()
        self.task(order, status='SCHEDULED', planned_start=now+timedelta(days=2), planned_end=now+timedelta(days=2, hours=1))
        row = self.queue()[str(order.pk)]
        self.assertEqual(row['primary_action']['label'], 'Consulter le planning')
        self.assertIn('Démarrage prévu au planning', row['waiting_reason'])
        self.assertTrue(row['task']['can_start_now'])

    def test_ordering_search_pagination_and_no_per_user_cache(self):
        now = timezone.now()
        late = self.order(deadline_at=now-timedelta(days=1))
        standard = self.order(deadline_at=now+timedelta(days=2))
        express = self.order(deadline_at=standard.deadline_at, delivery_service='EXPRESS')
        j1 = self.order(deadline_at=standard.deadline_at, delivery_service='NEXT_DAY')
        rows = self.queue()
        self.assertEqual(list(rows), [str(late.pk), str(j1.pk), str(express.pk), str(standard.pk)])
        response = self.client.get('/api/work-queue/?page_size=1')
        self.assertEqual(response.data['count'], 4); self.assertIsNotNone(response.data['next'])
        self.assertEqual(list(self.queue(search=express.patient_ref)), [str(express.pk)])
        self.assertEqual(self.queue(self.account('FAO')), {})

    def test_query_count_stays_constant_and_get_does_not_write(self):
        order = self.order('FINITION')
        self.task(order, status='IN_PROGRESS')
        with CaptureQueriesContext(connection) as small:
            self.queue()
        for _ in range(12):
            self.order()
        with CaptureQueriesContext(connection) as large:
            self.queue()
        self.assertEqual(len(small), len(large))
        self.assertLessEqual(len(large), 10)  # Includes tenant middleware/search_path statements.
        self.assertFalse(any(query['sql'].lstrip().upper().startswith(('INSERT', 'UPDATE', 'DELETE')) for query in large))

    def test_rework_assignment_and_risk_precede_deadline_order(self):
        now = timezone.now()
        rework = self.order('A_REFAIRE', deadline_at=now+timedelta(days=5))
        on_track = self.order('FINITION', deadline_at=now+timedelta(days=2))
        on_track.planning_tasks.exclude(status__in=['COMPLETED', 'CANCELLED']).update(
            planned_start=now+timedelta(hours=1), planned_end=now+timedelta(hours=2))
        self.task(on_track, planned_start=now+timedelta(hours=1), planned_end=now+timedelta(hours=2), status='SCHEDULED')
        account = self.account('FAO'); employee = self.employee(account=account)
        self.task(rework, assigned_employee=employee, status='READY')
        rows = self.queue(account)
        self.assertEqual(rows[str(rework.pk)]['primary_action']['label'], 'Reprendre : Reprise de fabrication')
        self.assertEqual(rows[str(rework.pk)]['primary_action']['command'], 'start')
        self.assertEqual(rows[str(on_track.pk)]['group'], 'TEAM')
        self.assertEqual(list(rows), [str(rework.pk), str(on_track.pk)])
        self.assertEqual([row['risk'] for row in rows.values()], ['AT_RISK', 'ON_TRACK'])

    def test_other_schema_cases_are_absent_and_endpoint_rejects_writes(self):
        local = self.order()
        with schema_context('public'):
            other = Client.objects.create(schema_name='queue_isolation_lab', name='Queue isolation lab')
        with schema_context(other.schema_name):
            Prescription.objects.create(patient_ref='FOREIGN-QUEUE', dentist_name='Other dentist',
                tooth_number=11, material='Zircone', shade='A1', disinfected=True)
        self.assertEqual(list(self.queue()), [str(local.pk)])
        self.assertEqual(self.client.post('/api/work-queue/', {}, format='json').status_code, 405)
        # TestCase rolls back this schema's transactional DDL and evidence together.
        # Dropping it before the rollback conflicts with deferred audit triggers.

    def test_anonymous_foreign_tenant_and_courier_denied(self):
        self.order()
        self.client.force_authenticate(None)
        self.assertIn(self.client.get('/api/work-queue/').status_code, (401, 403))
        with schema_context('public'):
            other = Client(schema_name='other_queue_lab', name='Other queue lab')
            other.auto_create_schema = False; other.save()
            foreign = PlatformAccount.objects.create(name='Foreign', login_key='queue-foreign', role='LAB', laboratory=other)
            courier = PlatformAccount.objects.create(name='Courier', login_key='queue-courier', role='COURIER', laboratory=self.tenant)
        for account in (foreign, courier):
            self.client.force_authenticate(account)
            self.assertEqual(self.client.get('/api/work-queue/').status_code, 403)
