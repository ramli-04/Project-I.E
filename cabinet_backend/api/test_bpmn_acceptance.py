import io
import tempfile
import uuid
from datetime import datetime, timedelta, timezone as utc_timezone
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth.hashers import make_password
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import DatabaseError, connection, transaction
from django.test import override_settings
from django_tenants.test.cases import TenantTestCase
from django_tenants.utils import schema_context
from rest_framework.test import APIClient, APIRequestFactory

from customers.models import PlatformAccount
from .models import (Prescription, PartnerClinic, Inventory, InventoryTransaction, ProductionLot, TaskOutbox,
    FinanceInvoice, InvoiceDocument, MonthlyFinancialCatalog, MonthlyStatementCatalog, CreditNote, ReworkCase)
from .case_commands import qr_token
from .tasks import calculate_automatic_calendar_task, generate_invoice_pdf_task, generate_credit_note_pdf_task
from .analytics import refresh_billing_catalog
from .billing import close_period, issue_credit
from .inventory import record_movement
from .views import PrescriptionViewSet


@override_settings(OUTBOX_PUBLISH_ON_COMMIT=False, EXTERNAL_DELIVERY_ENABLED=False,
    PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'],
    CACHES={'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache', 'LOCATION': 'bpmn-tests',
                        'KEY_FUNCTION': 'django_tenants.cache.make_key'}})
class BPMNAcceptanceTests(TenantTestCase):
    @classmethod
    def setup_tenant(cls, tenant):
        tenant.name = 'BPMN acceptance laboratory'

    def setUp(self):
        connection.set_tenant(self.tenant)
        self.files = tempfile.TemporaryDirectory()
        self.media = override_settings(PRIVATE_MEDIA_ROOT=self.files.name)
        self.media.enable()
        self.addCleanup(self.media.disable)
        self.addCleanup(self.files.cleanup)
        cache.clear()
        with schema_context('public'):
            self.manager = PlatformAccount.objects.create(name='Manager', login_key='manager', role='LAB', laboratory=self.tenant,
                                                           password_hash=make_password('secure-test-password'))
            self.dentist = PlatformAccount.objects.create(name='Dentist', login_key='dentist', role='DENTIST',
                                                           password_hash=make_password('secure-test-password'))
            self.courier = PlatformAccount.objects.create(name='Courier', login_key='courier', role='COURIER', laboratory=self.tenant,
                                                           password_hash=make_password('secure-test-password'))
        self.clinic = PartnerClinic.objects.create(name='Clinic', pickup_address='12 Main Street', contact_phone='+212600000000',
                                                   contact_email='clinic@example.invalid', platform_dentist=self.dentist)
        self.client = APIClient(HTTP_HOST=self.get_test_tenant_domain())
        self.client.force_authenticate(user=self.manager)

    def new_case(self, **changes):
        payload = {'patient_ref': 'BPMN', 'disinfected': True, 'dentist_name': 'Dentist', 'partner_clinic': self.clinic.pk,
                   'impression_type': 'NUMERIQUE', 'clinical_items': [{'tooth_number': 11, 'function': 'Couronne',
                   'form': 'Anatomique', 'shade': 'A2', 'material': 'Zircone'}], **changes}
        self.client.force_authenticate(user=self.dentist)
        response = self.client.post('/platform/dentist/orders/', {**payload, 'laboratory_id': self.tenant.schema_name}, format='json', HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()))
        self.assertEqual(response.status_code, 201, response.data)
        self.client.force_authenticate(user=self.manager)
        order = Prescription.objects.get(pk=response.data['id'])
        order._test_pin = response.data['delivery_pin_once']
        return order

    def patch(self, order, **attrs):
        result = self.client.patch(f'/api/prescriptions/{order.pk}/', attrs, format='json')
        self.assertEqual(result.status_code, 200, result.data)
        order.refresh_from_db()
        return result

    def command(self, order, action, data=None, *, user=None, key=None, expected=200):
        self.client.force_authenticate(user=user or self.manager)
        public = user is not None and user.role == 'DENTIST'
        url = f'/platform/dentist/orders/{self.tenant.schema_name}/{order.pk}/command/' if public else f'/api/prescriptions/{order.pk}/command/'
        response = self.client.post(url, {'action': action, 'data': data or {}}, format='json',
                                    HTTP_IDEMPOTENCY_KEY=str(key or uuid.uuid4()))
        self.assertEqual(response.status_code, expected, response.data)
        self.client.force_authenticate(user=self.manager)
        order.refresh_from_db()
        return response

    def upload(self, order, kind='STL'):
        if kind == 'STL':
            content = b'solid a\nfacet normal 0 0 1\nouter loop\nvertex 0 0 0\nvertex 1 0 0\nvertex 0 1 0\nendloop\nendfacet\nendsolid a\n'
            file = SimpleUploadedFile('scan.stl', content)
        elif kind == 'PHOTO':
            from PIL import Image
            output = io.BytesIO()
            Image.new('RGB', (2, 2), color='white').save(output, format='PNG')
            file = SimpleUploadedFile('photo.png', output.getvalue())
        else:
            from .documents import pdf_document
            file = SimpleUploadedFile('design.pdf', pdf_document('Design', ['Case design']))
        response = self.client.post(f'/api/prescriptions/{order.pk}/attachments/', {'kind': kind, 'file': file}, format='multipart')
        self.assertEqual(response.status_code, 201, response.data)
        return response.data['id']

    def to_planning(self, order):
        self.patch(order, accepted=True)
        self.patch(order, status='ANALYSE_DEMANDE')
        if order.impression_type == 'PHYSIQUE':
            self.patch(order, status='ATTENTE_RAMASSAGE', analysis_validated=True)
            self.command(order, 'pickup', {'qr_token': qr_token(order)}, user=self.courier)
            self.command(order, 'lab-deposit', {'qr_token': qr_token(order)}, user=self.courier)
            self.command(order, 'inspection', {'stage': 'PHYSICAL', 'checks': dict.fromkeys(['deformation','bubbles','limits','occlusion','hygiene'], True)})
        else:
            self.patch(order, status='A_CONFIRMER', analysis_validated=True)
            self.upload(order)
            self.command(order, 'inspection', {'stage': 'DIGITAL', 'checks': dict.fromkeys(['margins','occlusion','space','scan_quality'], True)})
        self.patch(order, status='CONTROLE_DOSSIER', reception_validated=True)
        if order.impression_type == 'PHYSIQUE':
            self.patch(order, status='COULEE_PLATRE')
            self.patch(order, status='SCAN_LABO')
            self.patch(order, status='CONTROLE_MODELE')
            self.command(order, 'inspection', {'stage': 'MODEL', 'checks': {'model': True, 'scan': True}})
        self.patch(order, status='PLANIFICATION')

    def to_cao(self, order):
        self.to_planning(order)
        self.patch(order, status='SALLE_CAO', production_method='CFAO', delivery_date='2026-10-30')

    def to_quality(self, order):
        if order.status == 'SALLE_CAO':
            self.patch(order, status='PREPARATION_CNC')
        lot = ProductionLot.objects.create(code='LOT-' + order.pk.hex)
        lot.prescriptions.add(order)
        self.patch(order, status='USINAGE_CNC')
        self.patch(order, status='FINITION')
        self.patch(order, status='CONTROLE_QUALITE')

    def deliver(self, order, *, recipient=None):
        self.command(order, 'inspection', {'stage': 'QUALITY', 'checks': dict.fromkeys(['margins','contacts','shade','occlusion','cosmetic','glazing','polishing'], True)})
        self.patch(order, status='CONDITIONNEMENT')
        self.patch(order, status='PRET_EXPEDITION')
        self.command(order, 'checkout', {'qr_token': qr_token(order)}, user=self.courier)
        self.command(order, 'confirm-delivery', {'pin': order._test_pin}, user=recipient or self.courier)

    def inspection_checkpoint(self, stage):
        """Reach a checkpoint through real commands, with no source/evidence bypass."""
        from .case_commands import CHECKS
        order = self.new_case(impression_type='PHYSIQUE' if stage in {'PHYSICAL', 'MODEL'} else 'NUMERIQUE')
        self.command(order, 'accept')
        self.command(order, 'advance', {'analysis_validated': True})
        if order.impression_type == 'PHYSIQUE':
            self.command(order, 'pickup', {'qr_token': qr_token(order)}, user=self.courier)
            self.command(order, 'lab-deposit', {'qr_token': qr_token(order)}, user=self.courier)
        else:
            self.upload(order)
        self.command(order, 'advance', {'reception_validated': True})
        if stage in {'PHYSICAL', 'DIGITAL'}:
            return order
        intake = 'PHYSICAL' if order.impression_type == 'PHYSIQUE' else 'DIGITAL'
        self.command(order, 'inspection', {'stage': intake, 'checks': dict.fromkeys(CHECKS[intake], True), 'advance': True})
        if stage == 'MODEL':
            self.command(order, 'advance')
            self.command(order, 'advance')
        else:
            self.command(order, 'advance', {'production_method': 'CFAO', 'thermal_treatment': 'AUCUN', 'delivery_date': '2026-12-01'})
            self.to_quality(order)
        return order

    def workstation_account(self, role):
        with schema_context('public'):
            return PlatformAccount.objects.create(name=role, login_key=uuid.uuid4().hex, role='LAB',
                                                   laboratory=self.tenant, workstation_role=role)

    def test_inspection_advance_checkpoints_record_evidence_audit_and_task_completion(self):
        from .case_commands import CHECKS
        from .workflow import next_status
        for stage in CHECKS:
            with self.subTest(stage=stage):
                order = self.inspection_checkpoint(stage)
                source, version, target = order.status, order.state_version, next_status(order)
                task = order.planning_tasks.get(workflow_step=source, production_attempt=order.production_attempt,
                                                intake_revision=order.intake_revision)
                user = self.workstation_account('QUALITE' if stage == 'QUALITY' else 'RECEPTION')
                data = {'stage': stage, 'checks': dict.fromkeys(CHECKS[stage], True), 'advance': True, 'notes': 'Inspection explicite'}
                key = uuid.uuid4()
                response = self.command(order, 'inspection', data, user=user, key=key)
                result = response.data['result']
                self.assertEqual(result, {'inspection_id': order.inspections.latest('pk').pk, 'passed': True,
                                          'advanced': True, 'status': target})
                self.assertEqual(order.status, target)
                self.assertEqual(order.state_version, version + 1)
                self.assertEqual(order.audit_history.latest('pk').metadata['action'], 'INSPECTION_ADVANCE')
                task.refresh_from_db()
                self.assertEqual(task.status, 'COMPLETED')
                self.assertIsNotNone(task.actual_end)
                if stage == 'QUALITY':
                    self.assertTrue(order.quality_validated)
                count, events = order.inspections.count(), order.audit_history.count()
                retry = self.command(order, 'inspection', data, user=user, key=key)
                self.assertEqual(retry.data['result'], result)
                self.assertEqual(order.state_version, version + 1)
                self.assertEqual(order.inspections.count(), count)
                self.assertEqual(order.audit_history.count(), events)

    def test_inspection_advance_wrong_owner_rejects_before_creating_evidence(self):
        from .case_commands import CHECKS
        for stage in ['PHYSICAL', 'DIGITAL', 'MODEL', 'QUALITY']:
            with self.subTest(stage=stage):
                order = self.inspection_checkpoint(stage)
                count, version = order.inspections.count(), order.state_version
                response = self.command(order, 'inspection', {'stage': stage, 'checks': dict.fromkeys(CHECKS[stage], True),
                    'advance': True}, user=self.workstation_account('CAO'), expected=400)
                self.assertIn('cannot validate and advance', str(response.data))
                self.assertEqual(order.inspections.count(), count)
                self.assertEqual(order.state_version, version)

    def test_inspection_advance_reception_records_without_skipping_confirmation(self):
        order = self.new_case()
        self.command(order, 'accept')
        self.command(order, 'advance', {'analysis_validated': True})
        self.upload(order)
        response = self.command(order, 'inspection', {'stage': 'DIGITAL',
            'checks': dict.fromkeys(['margins', 'occlusion', 'space', 'scan_quality'], True), 'advance': True})
        self.assertEqual(response.data['result']['advanced'], False)
        self.assertEqual(order.status, 'A_CONFIRMER')
        self.assertFalse(order.reception_validated)
        self.assertEqual(order.inspections.count(), 1)

    def test_inspection_advance_invalid_boolean_and_paused_case_roll_back(self):
        order = self.inspection_checkpoint('MODEL')
        data = {'stage': 'MODEL', 'checks': {'model': True, 'scan': True}}
        for value in [None, 1, 0, 'true', [], {}]:
            self.command(order, 'inspection', {**data, 'advance': value}, expected=400)
        self.assertFalse(order.inspections.filter(stage='MODEL').exists())
        self.command(order, 'pause', {'paused': True, 'notes': 'Pause explicite'})
        version = order.state_version
        self.command(order, 'inspection', {**data, 'advance': True}, expected=400)
        self.assertFalse(order.inspections.filter(stage='MODEL').exists())
        self.assertEqual(order.status, 'CONTROLE_MODELE')
        self.assertEqual(order.state_version, version)
        self.assertTrue(order.is_paused)

    def test_inspection_advance_equipment_guard_rolls_back_evidence(self):
        order = self.inspection_checkpoint('MODEL')
        task = order.planning_tasks.get(workflow_step='CONTROLE_MODELE')
        task.resource_phase = 'PLANNED'
        task.setup_minutes, task.unload_minutes = 5, 5
        task.save()
        response = self.command(order, 'inspection', {'stage': 'MODEL', 'checks': {'model': True, 'scan': True},
            'advance': True}, expected=400)
        self.assertIn('cycle autonome', str(response.data))
        self.assertFalse(order.inspections.filter(stage='MODEL').exists())
        self.assertEqual(order.status, 'CONTROLE_MODELE')

    def test_inspection_without_advance_retains_record_only_contract(self):
        order = self.inspection_checkpoint('MODEL')
        data = {'stage': 'MODEL', 'checks': {'model': True, 'scan': True}}
        response = self.command(order, 'inspection', data)
        self.assertEqual(set(response.data['result']), {'inspection_id', 'passed'})
        self.assertEqual(order.status, 'CONTROLE_MODELE')
        response = self.command(order, 'inspection', {**data, 'advance': False})
        self.assertFalse(response.data['result']['advanced'])
        self.assertEqual(order.status, 'CONTROLE_MODELE')

    def test_failed_inspection_does_not_advance_and_preserves_exception_routes(self):
        from .case_commands import CHECKS
        for stage in CHECKS:
            with self.subTest(stage=stage):
                order = self.inspection_checkpoint(stage)
                status = order.status
                data = {'stage': stage, 'checks': dict.fromkeys(CHECKS[stage], False),
                        'notes': 'Non-conformite explicite', 'advance': True}
                self.command(order, 'inspection', data, expected=400)
                data['photo'] = self.upload(order, 'PHOTO')
                response = self.command(order, 'inspection', data)
                self.assertFalse(response.data['result']['advanced'])
                self.assertFalse(response.data['result']['passed'])
                self.assertEqual(order.status, 'RETOUR_DEMANDE' if stage in {'PHYSICAL', 'DIGITAL'} else status)

    def test_accept_command_preserves_acceptance_effects_and_is_idempotent(self):
        from .models import TenantReadVersion
        order = self.new_case()
        version = TenantReadVersion.objects.get(name='active_orders').version
        self.assertFalse(order.planning_tasks.exists())
        key = uuid.uuid4()
        response = self.command(order, 'accept', {'notes': 'Prescription revue'}, user=self.workstation_account('RECEPTION'), key=key)
        self.assertEqual(response.data['result'], {'status': 'ANALYSE_DEMANDE'})
        self.assertTrue(order.accepted)
        self.assertIsNotNone(order.accepted_at)
        self.assertFalse(order.analysis_validated)
        self.assertTrue(order.planning_tasks.filter(workflow_step='ANALYSE_DEMANDE').exists())
        self.assertTrue(order.task_events.filter(event_type='PLANNING').exists())
        self.assertTrue(order.task_events.filter(event_type='CACHE').exists())
        self.assertEqual(order.audit_history.latest('pk').metadata['action'], 'ACCEPT')
        self.assertGreater(TenantReadVersion.objects.get(name='active_orders').version, version)
        history_count, tasks_count, accepted_at = order.audit_history.count(), order.planning_tasks.count(), order.accepted_at
        self.assertEqual(self.command(order, 'accept', {'notes': 'Prescription revue'}, key=key).data['result'], response.data['result'])
        self.assertEqual(order.audit_history.count(), history_count)
        self.assertEqual(order.planning_tasks.count(), tasks_count)
        self.assertEqual(order.accepted_at, accepted_at)
        self.command(order, 'accept', expected=400)

    def test_accept_command_rejects_non_reception_and_retains_patch_compatibility(self):
        order = self.new_case()
        self.command(order, 'accept', user=self.workstation_account('CAO'), expected=400)
        self.assertFalse(order.accepted)
        self.assertFalse(order.planning_tasks.exists())
        self.patch(order, accepted=True)
        self.assertIsNotNone(order.accepted_at)
        self.command(order, 'accept', expected=400)
        self.command(order, 'advance')
        self.assertEqual(order.status, 'ANALYSE_DEMANDE')

    def test_accept_command_paused_case_rolls_back_acceptance_and_planning(self):
        order = self.new_case()
        self.command(order, 'pause', {'paused': True, 'notes': 'Attente explicite'})
        self.command(order, 'accept', expected=400)
        self.assertFalse(order.accepted)
        self.assertIsNone(order.accepted_at)
        self.assertFalse(order.planning_tasks.exists())
        self.assertEqual(order.status, 'DEMANDE_RECUE')

    def test_courier_list_and_command_return_server_labels_without_clinical_fields(self):
        from .workflow import LABELS
        order = self.new_case(impression_type='PHYSIQUE')
        self.command(order, 'accept')
        self.command(order, 'advance', {'analysis_validated': True})
        self.client.force_authenticate(user=self.courier)
        response = self.client.get('/api/prescriptions/')
        self.assertEqual(response.status_code, 200, response.data)
        row = next(row for row in response.data['results'] if str(row['id']) == str(order.pk))
        self.assertEqual(row['status_label'], LABELS['ATTENTE_RAMASSAGE'])
        self.assertNotIn('clinical_items', row)
        self.assertNotIn('delivery_pin_hash', row)
        self.assertNotIn('workstation_notes', row)
        response = self.command(order, 'pickup', {'qr_token': qr_token(order)}, user=self.courier)
        self.assertEqual(response.data['case']['status_label'], LABELS['EN_ROUTE_LABO'])
        self.assertEqual(set(response.data['case']), set(row))

    def test_missing_password_unknown_token_and_cross_tenant_access_are_denied(self):
        self.client.force_authenticate(user=None)
        self.assertEqual(self.client.post('/platform/login/', {'name': 'Manager'}, format='json').status_code, 401)
        self.assertEqual(self.client.get('/api/prescriptions/').status_code, 401)
        login = self.client.post('/platform/login/', {'name': 'Manager', 'password': 'secure-test-password'}, format='json')
        self.assertEqual(login.status_code, 200, login.data)
        self.client.credentials(HTTP_AUTHORIZATION='Bearer ' + login.data['token'])
        self.assertEqual(self.client.get('/api/prescriptions/').status_code, 200)
        original = self.manager.laboratory_id
        with schema_context('public'):
            PlatformAccount.objects.filter(pk=self.manager.pk).update(laboratory=None)
        self.assertEqual(self.client.get('/api/prescriptions/').status_code, 401)

    def test_logout_revokes_opaque_session(self):
        self.client.force_authenticate(user=None)
        response = self.client.post('/platform/login/', {'name': 'Manager', 'password': 'secure-test-password'}, format='json')
        token = response.data['token']
        self.client.credentials(HTTP_AUTHORIZATION='Bearer ' + token)
        self.assertEqual(self.client.post('/platform/logout/').status_code, 204)
        self.assertEqual(self.client.get('/api/prescriptions/').status_code, 401)

    def test_pricing_items_and_secret_fields_are_server_controlled(self):
        order = self.new_case(delivery_service='EXPRESS', total_price='1')
        self.assertEqual(order.total_price, Decimal('1560'))
        response = self.client.get(f'/api/prescriptions/{order.pk}/')
        for name in ['delivery_pin','delivery_pin_hash','qr_nonce']:
            self.assertNotIn(name, response.data)
        self.assertEqual(order.delivery_pin, '')
        self.assertEqual(order.clinical_items.count(), 1)
        payload = {'patient_ref': 'BAD', 'partner_clinic': self.clinic.pk,
                   'clinical_items': [{'tooth_number': 11, 'function': 'Crown', 'form': 'A', 'shade': 'A2', 'material': 'Zircone'}]}
        self.assertEqual(self.client.post('/api/prescriptions/', payload, format='json').status_code, 400)

    def test_manual_j1_quote_and_calendar_days(self):
        order = self.new_case(delivery_service='NEXT_DAY')
        self.assertIsNone(order.total_price)
        self.command(order, 'quote', {'surcharge': '150'})
        self.assertEqual(order.total_price, Decimal('1350'))
        event = order.task_events.get(event_type='CALENDAR')
        result = calculate_automatic_calendar_task(self.tenant.schema_name, str(order.pk), str(event.pk))
        self.assertEqual(result['deadline'], (order.created_at.astimezone(timezone()).date() + timedelta(days=1)).isoformat())

    def test_physical_and_digital_intake_cannot_skip_inspections(self):
        order = self.new_case(impression_type='PHYSIQUE')
        self.to_cao(order)
        statuses = list(order.audit_history.values_list('new_status', flat=True))
        self.assertLess(statuses.index('COULEE_PLATRE'), statuses.index('SALLE_CAO'))
        self.assertIn('CONTROLE_MODELE', statuses)

    def test_failed_intake_requires_photo_and_routes_to_return(self):
        order = self.new_case()
        self.patch(order, accepted=True)
        self.patch(order, status='ANALYSE_DEMANDE')
        self.patch(order, status='A_CONFIRMER', analysis_validated=True)
        self.upload(order)
        checks = {'margins': False, 'occlusion': True, 'space': True, 'scan_quality': True}
        self.command(order, 'inspection', {'stage': 'DIGITAL', 'checks': checks, 'notes': 'Bad margins'}, expected=400)
        photo = self.upload(order, 'PHOTO')
        self.command(order, 'inspection', {'stage': 'DIGITAL', 'checks': checks, 'notes': 'Bad margins', 'photo': photo})
        self.assertEqual(order.status, 'RETOUR_DEMANDE')
        self.assertTrue(order.notifications.filter(kind='INSPECTION_FAILED').exists())
        self.command(order, 'resubmit', user=self.dentist)
        self.assertEqual(order.intake_revision, 2)

    def test_dentist_approval_suspends_and_resumes_deadline(self):
        from django.utils import timezone as django_timezone
        order = self.new_case(design_validation_requested=True)
        self.to_cao(order)
        design = self.upload(order, 'DESIGN')
        self.command(order, 'design-request', {'attachment': design})
        self.assertTrue(order.is_paused)
        start = order.pause_started_at
        review = order.design_reviews.get()
        self.command(order, 'pause', {'paused': False}, expected=400)
        with patch('django.utils.timezone.now', return_value=start + timedelta(hours=2)):
            self.command(order, 'design-decision', {'review': str(review.pk), 'decision': 'APPROVED'}, user=self.dentist)
        self.assertFalse(order.is_paused)
        self.assertEqual(order.deadline_suspended_seconds, 7200)
        self.assertEqual(order.status, 'PREPARATION_CNC')

    def test_partial_rework_and_retries_do_not_double_deduct_stock(self):
        order = self.new_case()
        self.to_cao(order)
        self.to_quality(order)
        item = Inventory.objects.create(material_name='Zircone', quantity='10', unit='GRAMMES', alert_threshold='1', unit_cost='7')
        usage = record_movement(inventory_item=item, prescription=order, transaction_type='USAGE',
                                quantity_changed=Decimal('-2.5'), idempotency_key=uuid.uuid4())
        data = {'origin': 'LAB', 'cause': 'Shade mismatch', 'corrective_action': 'Redo finishing', 'restart_status': 'FINITION',
                'losses': [{'usage_id': str(usage.pk), 'quantity': '0.5'}]}
        key = uuid.uuid4()
        self.command(order, 'rework', data, key=key)
        self.command(order, 'rework', data, key=key)
        item.refresh_from_db()
        self.assertEqual(item.quantity, Decimal('7.5'))
        self.assertEqual(order.production_attempt, 2)
        self.assertEqual(ReworkCase.objects.filter(prescription=order).count(), 1)
        self.assertEqual(item.transactions.filter(transaction_type='REWORK_LOSS').get().quantity_changed, Decimal('-0.5'))
        self.patch(order, status='FINITION')

    def test_wrong_pin_is_persisted_and_generic_delivery_update_is_rejected(self):
        order = self.new_case()
        self.to_cao(order)
        self.to_quality(order)
        self.command(order, 'inspection', {'stage': 'QUALITY', 'checks': dict.fromkeys(['margins','contacts','shade','occlusion','cosmetic','glazing','polishing'], True)})
        self.patch(order, status='CONDITIONNEMENT')
        self.patch(order, status='PRET_EXPEDITION')
        self.command(order, 'checkout', {'qr_token': qr_token(order)}, user=self.courier)
        self.assertEqual(self.client.patch(f'/api/prescriptions/{order.pk}/', {'status':'LIVRE'}, format='json').status_code, 400)
        wrong = '0000' if order._test_pin != '0000' else '1111'
        self.command(order, 'confirm-delivery', {'pin': wrong}, user=self.courier, expected=400)
        self.assertEqual(order.pin_attempts, 1)
        self.command(order, 'confirm-delivery', {'pin': order._test_pin}, user=self.courier)
        self.assertEqual(order.status, 'LIVRE')
        self.command(order, 'rework', {'origin': 'CLINIC', 'cause': 'Fitting failed', 'corrective_action': 'Revise CAD',
            'restart_status': 'SALLE_CAO', 'losses': []}, user=self.dentist)
        self.assertEqual(order.reworks.get().prescription_id, order.pk)

    def test_post_delivery_remake_allows_subsequent_lab_loss_assessment(self):
        order = self.new_case()
        self.to_cao(order)
        self.to_quality(order)
        item = Inventory.objects.create(material_name='Remake Disc', quantity='10', unit='DISQUE', alert_threshold='1', unit_cost='50')
        usage = record_movement(inventory_item=item, prescription=order, transaction_type='USAGE',
                                quantity_changed=Decimal('-2'), idempotency_key=uuid.uuid4(), changed_by='operator')
        self.deliver(order)
        self.assertEqual(order.status, 'LIVRE')
        self.command(order, 'fitting', {'passed': False}, user=self.dentist, expected=400)
        self.assertEqual(order.status, 'LIVRE')
        self.assertIsNone(order.fitting_validated_at)
        self.assertFalse(order.reworks.exists())
        # Dentist initiates remake post-delivery with no measured losses
        self.command(order, 'rework', {'origin': 'CLINIC', 'cause': 'Occlusion issue', 'corrective_action': 'Rework CAD',
                                       'restart_status': 'SALLE_CAO', 'losses': []}, user=self.dentist)
        order.refresh_from_db()
        self.assertEqual(order.production_attempt, 2)
        rework = order.reworks.get()
        self.assertEqual(rework.attempt, 1)
        self.assertEqual(rework.losses, [])

        # Dentist cannot call assess-loss
        loss_data = {'attempt': 1, 'losses': [{'usage_id': str(usage.pk), 'quantity': '1.5'}]}
        self.command(order, 'assess-loss', loss_data, user=self.dentist, expected=400)

        # Lab assesses loss for attempt 1
        key = uuid.uuid4()
        self.command(order, 'assess-loss', loss_data, user=self.manager, key=key)
        # Idempotent retry
        self.command(order, 'assess-loss', loss_data, user=self.manager, key=key)
        item.refresh_from_db()
        order.refresh_from_db()
        # Stock balance: original 10, usage was -2 -> 8; loss assessment is net 0 change -> still 8
        self.assertEqual(item.quantity, Decimal('8'))
        # REWORK_LOSS created
        self.assertEqual(item.transactions.filter(transaction_type='REWORK_LOSS').get().quantity_changed, Decimal('-1.5'))
        # Production attempt remains 2
        self.assertEqual(order.production_attempt, 2)

    def test_raw_status_writes_and_history_tampering_are_rejected(self):
        order = self.new_case()
        with self.assertRaises(DatabaseError), transaction.atomic():
            Prescription._base_manager.filter(pk=order.pk).update(status='LIVRE')
        with self.assertRaises(DatabaseError), transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute("UPDATE api_prescriptionhistory SET changed_by='forged'")

    def test_cache_generation_prevents_repopulation_race(self):
        order = self.new_case()
        cache.clear()
        original_set = cache.set
        def interleave(key, data, timeout=None):
            with self.captureOnCommitCallbacks(execute=True):
                self.patch(order, accepted=True, status='ANALYSE_DEMANDE')
            return original_set(key, data, timeout=timeout)
        with patch('api.views.cache.set', side_effect=interleave):
            self.assertEqual(self.client.get('/api/prescriptions/').status_code, 200)
        result = self.client.get('/api/prescriptions/')
        self.assertEqual(result.data['results'][0]['status'], 'ANALYSE_DEMANDE')

    def verify_complete_delivery_and_billing(self, track):
        """Real API/domain/SQL guards; historical clock only in the test database."""
        from .workflow import workflow_steps
        created=[]
        october=datetime(2026,10,10,12,tzinfo=utc_timezone.utc)
        with patch('django.utils.timezone.now',return_value=october):
            for route in ('CFAO','IMPRESSION_3D','CONVENTIONNEL'):
                with self.subTest(track=track,route=route):
                    order=self.new_case(impression_type=track,delivery_service='EXPRESS',
                        design_validation_requested=route!='CONVENTIONNEL')
                    self.to_planning(order)
                    self.command(order,'advance',{'production_method':route,'delivery_date':'2026-10-14',
                        'thermal_treatment':'FRITTAGE' if route=='CFAO' else 'AUCUN'})
                    lot=self.client.post('/api/production-lots/',{'code':'FLOW-'+order.pk.hex,
                        'prescriptions':[str(order.pk)]},format='json')
                    self.assertEqual(lot.status_code,201,lot.data)
                    if order.design_validation_requested:
                        design=self.upload(order,'DESIGN')
                        self.command(order,'design-request',{'attachment':design})
                        self.assertTrue(order.is_paused)
                        review=order.design_reviews.get()
                        self.command(order,'design-decision',{'review':str(review.pk),'decision':'APPROVED'},user=self.dentist)
                        self.assertFalse(order.is_paused)
                    for _ in range(12):
                        if order.status=='CONTROLE_QUALITE': break
                        self.command(order,'advance')
                    self.assertEqual(order.status,'CONTROLE_QUALITE')
                    self.deliver(order,recipient=self.dentist)
                    self.command(order,'fitting',{'passed':True},user=self.dentist)
                    self.assertEqual(order.status,'CLOTURE')
                    statuses=list(order.audit_history.order_by('created_at','pk').values_list('new_status',flat=True))
                    for step in workflow_steps(order):
                        if step['key'] not in {'DEMANDE_RECUE','ESSAYAGE'}:
                            self.assertIn(step['key'],statuses)
                    self.assertEqual(order.statement_line.period.month.isoformat(),'2026-10-01')
                    self.assertEqual(order.statement_line.base_amount,Decimal('1200'))
                    self.assertEqual(order.statement_line.express_surcharge,Decimal('360'))
                    created.append(order)
            period=created[0].statement_line.period
            premature=self.client.post(f'/api/billing/periods/{period.pk}/close/',{},format='json')
            self.assertEqual(premature.status_code,400,premature.data)
        with patch('django.utils.timezone.now',return_value=datetime(2026,11,15,12,tzinfo=utc_timezone.utc)):
            closed=self.client.post(f'/api/billing/periods/{period.pk}/close/',{},format='json')
            self.assertEqual(closed.status_code,200,closed.data)
            repeated=self.client.post(f'/api/billing/periods/{period.pk}/close/',{},format='json')
            self.assertEqual(repeated.status_code,200,repeated.data)
            self.assertEqual(closed.data['id'],repeated.data['id'])
        invoice=FinanceInvoice.objects.get(pk=closed.data['id'])
        self.assertEqual(invoice.total_amount,Decimal('4680'))
        self.assertEqual(len(invoice.lines),3)
        events=TaskOutbox.objects.filter(event_type='INVOICE',prescription_id__in=[order.pk for order in created])
        self.assertEqual(events.count(),3)
        for event in events:
            generated=generate_invoice_pdf_task(self.tenant.schema_name,str(event.prescription_id),str(event.pk))
            self.assertEqual(generated['status'],'PDF_READY')
        self.assertEqual(InvoiceDocument.objects.filter(invoice=invoice).count(),1)
        pdf=self.client.get(f'/api/billing/invoices/{invoice.pk}/pdf/')
        self.assertEqual(pdf.status_code,200)
        self.assertTrue(b''.join(pdf.streaming_content).startswith(b'%PDF-'))
        refresh_billing_catalog(self.tenant.schema_name)
        self.assertEqual(MonthlyFinancialCatalog.objects.get().net_amount,Decimal('4680'))

    def test_complete_physical_routes_through_delivery_and_monthly_invoice(self):
        self.verify_complete_delivery_and_billing('PHYSIQUE')

    def test_complete_digital_routes_through_delivery_and_monthly_invoice(self):
        self.verify_complete_delivery_and_billing('NUMERIQUE')

    def test_dentist_delivery_confirmation_requires_ownership_and_correct_pin(self):
        order=self.new_case()
        self.to_cao(order);self.to_quality(order)
        self.command(order,'inspection',{'stage':'QUALITY','checks':dict.fromkeys(
            ['margins','contacts','shade','occlusion','cosmetic','glazing','polishing'],True)})
        self.patch(order,status='CONDITIONNEMENT');self.patch(order,status='PRET_EXPEDITION')
        self.command(order,'checkout',{'qr_token':qr_token(order)},user=self.courier)
        with schema_context('public'):
            stranger=PlatformAccount.objects.create(name='Other dentist',login_key='other-dentist',role='DENTIST')
        self.command(order,'confirm-delivery',{'pin':order._test_pin},user=stranger,expected=404)
        self.assertEqual(order.status,'EN_ROUTE_CABINET')
        wrong='0000' if order._test_pin!='0000' else '1111'
        self.command(order,'confirm-delivery',{'pin':wrong},user=self.dentist,expected=400)
        self.assertEqual(order.pin_attempts,1)
        self.assertFalse(hasattr(order,'statement_line'))
        key=uuid.uuid4()
        self.command(order,'confirm-delivery',{'pin':order._test_pin},user=self.dentist,key=key)
        self.command(order,'confirm-delivery',{'pin':order._test_pin},user=self.dentist,key=key)
        self.assertEqual(order.status,'LIVRE')
        from .models import StatementLine
        self.assertEqual(StatementLine.objects.filter(prescription=order).count(),1)

    def test_pin_rotation_delivery_actions_and_dispute_retries_keep_existing_contract(self):
        from django.contrib.auth.hashers import check_password
        from .models import BillingDispute, CaseCommandReceipt, WorkflowEvent

        order = self.new_case()
        self.command(order, 'issue-pin', expected=400)
        key = uuid.uuid4()
        issued = self.command(order, 'issue-pin', user=self.dentist, key=key)
        pin = issued.data['result']['pin_once']
        self.assertTrue(check_password(pin, order.delivery_pin_hash))
        self.assertEqual(self.command(order, 'issue-pin', user=self.dentist, key=key).data['result'], {})
        self.assertNotIn('pin_once', CaseCommandReceipt.objects.get(pk=key).result)
        self.assertEqual(WorkflowEvent.objects.filter(prescription=order).latest('created_at').payload['action'], 'ISSUE-PIN')

        self.to_cao(order)
        self.to_quality(order)
        self.command(order, 'inspection', {'stage': 'QUALITY', 'checks': dict.fromkeys(
            ['margins', 'contacts', 'shade', 'occlusion', 'cosmetic', 'glazing', 'polishing'], True)})
        self.patch(order, status='CONDITIONNEMENT')
        self.patch(order, status='PRET_EXPEDITION')
        self.command(order, 'checkout', {'qr_token': qr_token(order)}, user=self.courier)
        wrong = '0000' if pin != '0000' else '1111'
        failed_key = uuid.uuid4()
        self.command(order, 'confirm-delivery', {'pin': wrong}, user=self.courier, key=failed_key, expected=400)
        self.command(order, 'confirm-delivery', {'pin': wrong}, user=self.courier, key=failed_key, expected=400)
        self.assertEqual(order.pin_attempts, 1)
        self.assertEqual(WorkflowEvent.objects.filter(prescription=order).latest('created_at').payload['action'], 'CONFIRM-DELIVERY')
        self.command(order, 'confirm-delivery', {'pin': pin}, user=self.courier)
        self.assertEqual(order.audit_history.latest('pk').metadata['action'], 'CONFIRM_DELIVERY')

        key = uuid.uuid4()
        payload = {'notes': 'Montant à vérifier avec le laboratoire'}
        first = self.command(order, 'dispute', payload, user=self.dentist, key=key)
        retry = self.command(order, 'dispute', payload, user=self.dentist, key=key)
        self.assertEqual(first.data['result'], retry.data['result'])
        self.assertEqual(BillingDispute.objects.filter(prescription=order).count(), 1)
        self.assertTrue(order.statement_line.contested)
        self.assertEqual(WorkflowEvent.objects.filter(prescription=order).latest('created_at').payload['action'], 'DISPUTE')

    def test_physical_return_requires_a_new_revision_inspection_after_resubmission(self):
        from .case_commands import CHECKS
        order = self.inspection_checkpoint('PHYSICAL')
        photo = self.upload(order, 'PHOTO')
        checks = dict.fromkeys(CHECKS['PHYSICAL'], True)
        checks['limits'] = False
        self.command(order, 'inspection', {'stage': 'PHYSICAL', 'checks': checks,
            'photo': photo, 'notes': 'Limites imprécises', 'advance': True})
        self.assertEqual(order.status, 'RETOUR_DEMANDE')
        failed = order.inspections.get(stage='PHYSICAL')
        self.assertFalse(failed.passed)
        self.assertTrue(order.notifications.filter(kind='INSPECTION_FAILED').exists())
        self.command(order, 'resubmit', user=self.dentist)
        self.assertEqual(order.intake_revision, 2)
        self.assertFalse(order.reception_validated)
        self.command(order, 'advance', {'reception_validated': True})
        self.command(order, 'advance', expected=400)
        self.assertEqual(order.status, 'CONTROLE_DOSSIER')
        self.command(order, 'inspection', {'stage': 'PHYSICAL',
            'checks': dict.fromkeys(CHECKS['PHYSICAL'], True), 'advance': True})
        self.assertEqual(order.status, 'COULEE_PLATRE')
        self.assertEqual(order.inspections.get(stage='PHYSICAL', passed=True).intake_revision, 2)
        failed.refresh_from_db()
        self.assertEqual(failed.intake_revision, 1)
        self.assertFalse(failed.passed)

    def test_failed_model_can_be_repoured_or_rescanned_with_measured_loss(self):
        for restart, exception in [('COULEE_PLATRE', 'RECOULER'), ('SCAN_LABO', 'RESCANNER')]:
            with self.subTest(restart=restart):
                order = self.inspection_checkpoint('MODEL')
                photo = self.upload(order, 'PHOTO')
                self.command(order, 'inspection', {'stage': 'MODEL', 'checks': {'model': False, 'scan': True},
                    'photo': photo, 'notes': 'Modèle à reprendre', 'advance': True})
                self.assertEqual(order.status, 'CONTROLE_MODELE')
                item = Inventory.objects.create(material_name='Plâtre de test', quantity='10', unit='GRAMMES',
                                                alert_threshold='1', unit_cost='2')
                usage = record_movement(inventory_item=item, prescription=order, transaction_type='USAGE',
                    quantity_changed=Decimal('-1.25'), idempotency_key=uuid.uuid4())
                data = {'origin': 'LAB', 'cause': 'Modèle non conforme', 'corrective_action': 'Reprendre le modèle',
                        'restart_status': restart, 'losses': [{'usage_id': str(usage.pk), 'quantity': '0.25'}]}
                key = uuid.uuid4()
                self.command(order, 'rework', data, key=key)
                self.command(order, 'rework', data, key=key)
                self.assertEqual(order.status, exception)
                self.assertEqual(order.production_attempt, 2)
                rework = order.reworks.get()
                self.assertEqual((rework.cause_step, rework.restart_status, rework.attempt),
                                 ('CONTROLE_MODELE', restart, 1))
                item.refresh_from_db()
                self.assertEqual(item.quantity, Decimal('8.75'))
                self.assertEqual(item.transactions.get(transaction_type='REWORK_LOSS').quantity_changed, Decimal('-0.25'))
                self.command(order, 'advance')
                self.assertEqual(order.status, restart)
                if restart == 'COULEE_PLATRE':
                    self.command(order, 'advance')
                self.command(order, 'advance')
                self.assertEqual(order.status, 'CONTROLE_MODELE')
                self.command(order, 'advance', expected=400)
                self.command(order, 'inspection', {'stage': 'MODEL', 'checks': {'model': True, 'scan': True}, 'advance': True})
                self.assertEqual(order.status, 'PLANIFICATION')

    def test_design_changes_keep_the_hold_until_a_new_version_is_approved(self):
        order = self.new_case(design_validation_requested=True)
        self.to_cao(order)
        first = self.upload(order, 'DESIGN')
        self.command(order, 'design-request', {'attachment': first})
        review = order.design_reviews.get()
        data = {'review': str(review.pk), 'decision': 'CHANGES_REQUESTED'}
        self.command(order, 'design-decision', data, user=self.dentist, expected=400)
        self.assertEqual(order.status, 'VALIDATION_CAO')
        self.command(order, 'design-decision', {**data, 'notes': 'Corriger les contacts'}, user=self.dentist)
        self.assertEqual(order.status, 'SALLE_CAO')
        self.assertTrue(order.is_paused)
        review.refresh_from_db()
        self.assertEqual(review.status, 'CHANGES_REQUESTED')
        self.assertEqual(review.response_notes, 'Corriger les contacts')
        self.command(order, 'advance', expected=400)
        second = self.upload(order, 'DESIGN')
        self.command(order, 'design-request', {'attachment': second})
        revised = order.design_reviews.get(status='PENDING')
        self.assertEqual(revised.version, 2)
        self.assertEqual(revised.production_attempt, review.production_attempt)
        self.command(order, 'design-decision', {'review': str(revised.pk), 'decision': 'APPROVED'}, user=self.dentist)
        self.assertEqual(order.status, 'PREPARATION_CNC')
        self.assertFalse(order.is_paused)
        self.assertEqual(order.design_reviews.count(), 2)
        self.assertEqual(order.notifications.filter(kind='DESIGN_DECISION').count(), 2)

    def test_manufacturing_rework_keeps_the_case_lot_and_measured_loss(self):
        order = self.new_case()
        self.to_cao(order)
        self.command(order, 'advance')
        lot = ProductionLot.objects.create(code='REWORK-' + order.pk.hex)
        lot.prescriptions.add(order)
        self.command(order, 'advance')
        self.assertEqual(order.status, 'USINAGE_CNC')
        item = Inventory.objects.create(material_name='Brut de test', quantity='10', unit='DISQUE',
                                        alert_threshold='1', unit_cost='50')
        usage = record_movement(inventory_item=item, prescription=order, transaction_type='USAGE',
            quantity_changed=Decimal('-1'), idempotency_key=uuid.uuid4())
        count = Prescription.objects.count()
        self.command(order, 'rework', {'origin': 'LAB', 'cause': 'Fracture pendant usinage',
            'corrective_action': 'Refaire le parcours outil', 'restart_status': 'PREPARATION_CNC',
            'losses': [{'usage_id': str(usage.pk), 'quantity': '1'}]})
        self.assertEqual(order.status, 'A_REFAIRE')
        self.assertEqual(Prescription.objects.count(), count)
        self.assertEqual(order.production_attempt, 2)
        self.assertEqual(order.reworks.get().cause_step, 'USINAGE_CNC')
        self.assertTrue(order.production_lots.filter(pk=lot.pk).exists())
        item.refresh_from_db()
        self.assertEqual(item.quantity, Decimal('9'))
        self.assertEqual(item.transactions.get(transaction_type='REWORK_LOSS').quantity_changed, Decimal('-1'))
        notification = order.notifications.get(kind='REWORK')
        self.assertEqual(notification.payload['original_case_id'], str(order.pk))
        self.command(order, 'advance')
        self.assertEqual(order.status, 'PREPARATION_CNC')

    def test_failed_quality_restarts_at_the_selected_cause_step_and_requires_new_evidence(self):
        from .case_commands import CHECKS
        for restart in ('SALLE_CAO', 'PREPARATION_CNC', 'FINITION'):
            with self.subTest(restart=restart):
                order = self.inspection_checkpoint('QUALITY')
                checks = dict.fromkeys(CHECKS['QUALITY'], True)
                checks['contacts'] = False
                self.command(order, 'inspection', {'stage': 'QUALITY', 'checks': checks,
                    'photo': self.upload(order, 'PHOTO'), 'notes': 'Contacts non conformes', 'advance': True})
                self.assertEqual(order.status, 'CONTROLE_QUALITE')
                self.assertFalse(order.quality_validated)
                self.command(order, 'rework', {'origin': 'LAB', 'cause': 'Contacts à corriger',
                    'corrective_action': 'Corriger au poste concerné', 'restart_status': restart, 'losses': []})
                rework = order.reworks.get()
                self.assertEqual((rework.cause_step, rework.restart_status, rework.losses),
                                 ('CONTROLE_QUALITE', restart, []))
                self.command(order, 'advance')
                self.assertEqual(order.status, restart)
                for _ in range(5):
                    if order.status == 'CONTROLE_QUALITE':
                        break
                    self.command(order, 'advance')
                self.assertEqual(order.status, 'CONTROLE_QUALITE')
                self.command(order, 'advance', expected=400)
                self.assertFalse(order.quality_validated)
                self.command(order, 'inspection', {'stage': 'QUALITY',
                    'checks': dict.fromkeys(CHECKS['QUALITY'], True), 'advance': True})
                self.assertEqual(order.status, 'CONDITIONNEMENT')
                self.assertEqual(order.inspections.get(stage='QUALITY', passed=True).production_attempt, 2)

    def test_open_statement_disputes_exclude_accepted_and_restore_rejected_lines(self):
        from .models import BillingDispute
        accountant = self.workstation_account('COMPTABILITE')
        orders = []
        with patch('django.utils.timezone.now', return_value=datetime(2026, 10, 10, 12, tzinfo=utc_timezone.utc)):
            for service in ('STANDARD', 'EXPRESS'):
                order = self.new_case(delivery_service=service)
                self.to_cao(order)
                self.to_quality(order)
                self.deliver(order)
                self.command(order, 'dispute', {'notes': 'Montant à vérifier'}, user=self.dentist)
                orders.append(order)
        excluded, restored = orders
        period = excluded.statement_line.period
        disputes = {order.pk: BillingDispute.objects.get(prescription=order) for order in orders}
        self.client.force_authenticate(user=accountant)
        with patch('django.utils.timezone.now', return_value=datetime(2026, 11, 4, 12, tzinfo=utc_timezone.utc)):
            blocked = self.client.post(f'/api/billing/periods/{period.pk}/close/', {}, format='json')
            self.assertEqual(blocked.status_code, 400, blocked.data)
            self.assertFalse(FinanceInvoice.objects.exists())
            for order, decision in [(excluded, 'ACCEPTED'), (restored, 'REJECTED')]:
                resolved = self.client.post(f'/api/billing/disputes/{disputes[order.pk].pk}/resolve/',
                    {'decision': decision, 'notes': 'Décision comptable documentée'}, format='json')
                self.assertEqual(resolved.status_code, 200, resolved.data)
                self.assertEqual(resolved.data['status'], decision)
            closed = self.client.post(f'/api/billing/periods/{period.pk}/close/', {}, format='json')
            self.assertEqual(closed.status_code, 200, closed.data)
        excluded.refresh_from_db()
        restored.refresh_from_db()
        self.assertTrue(excluded.statement_line.contested)
        self.assertTrue(excluded.statement_line.excluded)
        self.assertFalse(restored.statement_line.contested)
        self.assertFalse(restored.statement_line.excluded)
        self.assertIsNone(excluded.invoiced_at)
        self.assertIsNotNone(restored.invoiced_at)
        invoice = FinanceInvoice.objects.get(pk=closed.data['id'])
        self.assertEqual([line['case_id'] for line in invoice.lines], [str(restored.pk)])
        self.assertEqual(invoice.total_amount, Decimal('1560'))
        self.assertEqual(invoice.express_surcharge, Decimal('360'))
        self.assertFalse(CreditNote.objects.exists())
        invalid_credit = self.client.post(f'/api/billing/invoices/{invoice.pk}/credit/',
            {'prescription': str(excluded.pk), 'amount': '10', 'reason': 'Ligne exclue'},
            format='json', HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()))
        self.assertEqual(invalid_credit.status_code, 400, invalid_credit.data)
        self.assertFalse(CreditNote.objects.exists())

    def test_issued_statement_dispute_creates_one_bounded_credit_and_keeps_invoice_immutable(self):
        from copy import deepcopy
        from .models import BillingDispute
        accountant = self.workstation_account('COMPTABILITE')
        with patch('django.utils.timezone.now', return_value=datetime(2026, 10, 10, 12, tzinfo=utc_timezone.utc)):
            order = self.new_case(delivery_service='EXPRESS')
            self.to_cao(order)
            self.to_quality(order)
            self.deliver(order)
        with patch('django.utils.timezone.now', return_value=datetime(2026, 11, 4, 12, tzinfo=utc_timezone.utc)):
            invoice = close_period(order.statement_line.period_id, 'test:accountant')
        snapshot = deepcopy(invoice.lines)
        self.command(order, 'dispute', {'notes': 'Correction après émission'}, user=self.dentist)
        dispute = BillingDispute.objects.get(prescription=order)
        self.assertEqual(dispute.invoice_id, invoice.pk)
        url = f'/api/billing/disputes/{dispute.pk}/resolve/'
        decision = {'decision': 'ACCEPTED', 'notes': 'Correction approuvée', 'amount': '100'}
        self.client.force_authenticate(user=self.dentist)
        self.assertEqual(self.client.post(url, decision, format='json').status_code, 403)
        self.client.force_authenticate(user=accountant)
        for amount in ('0', '1560.01'):
            invalid = self.client.post(url, {**decision, 'amount': amount}, format='json')
            self.assertEqual(invalid.status_code, 400, invalid.data)
            dispute.refresh_from_db()
            self.assertEqual(dispute.status, 'OPEN')
            self.assertFalse(CreditNote.objects.exists())
        resolved = self.client.post(url, decision, format='json')
        self.assertEqual(resolved.status_code, 200, resolved.data)
        self.assertEqual(resolved.data['status'], 'ACCEPTED')
        self.assertEqual(self.client.post(url, decision, format='json').status_code, 400)
        credit = CreditNote.objects.get(invoice=invoice)
        self.assertEqual(credit.amount, Decimal('100'))
        repeated = self.client.post(f'/api/billing/invoices/{invoice.pk}/credit/',
            {'prescription': str(order.pk), 'amount': '100', 'reason': decision['notes']}, format='json',
            HTTP_IDEMPOTENCY_KEY=str(uuid.uuid5(uuid.NAMESPACE_URL, f'dispute:{dispute.pk}')))
        self.assertEqual(repeated.status_code, 201, repeated.data)
        self.assertEqual(str(credit.pk), repeated.data['id'])
        self.assertEqual(CreditNote.objects.filter(invoice=invoice).count(), 1)
        invoice.refresh_from_db()
        self.assertEqual(invoice.total_amount, Decimal('1560'))
        self.assertEqual(invoice.lines, snapshot)
        edited = self.client.post(f'/api/billing/statement-lines/{order.statement_line.pk}/adjust/',
            {'contested': True, 'excluded': True, 'reason': 'Émission immuable'}, format='json')
        self.assertEqual(edited.status_code, 400, edited.data)
        event = order.task_events.get(event_type='CREDIT')
        self.assertEqual(generate_credit_note_pdf_task(self.tenant.schema_name, str(order.pk), str(event.pk))['status'], 'PDF_READY')
        pdf = self.client.get(f'/api/billing/credit-notes/{credit.pk}/pdf/')
        self.assertEqual(pdf.status_code, 200)
        self.assertTrue(b''.join(pdf.streaming_content).startswith(b'%PDF-'))
        refresh_billing_catalog(self.tenant.schema_name)
        self.assertEqual(MonthlyFinancialCatalog.objects.get().net_amount, Decimal('1460'))
        self.assertTrue(order.notifications.filter(kind='CREDIT_ISSUED').exists())

    def test_monthly_closing_real_pdf_and_credit_catalog(self):
        october = datetime(2026,10,10,12,tzinfo=utc_timezone.utc)
        with patch('django.utils.timezone.now', return_value=october):
            order = self.new_case(delivery_service='EXPRESS')
            self.to_cao(order)
            self.to_quality(order)
            self.deliver(order)
            self.command(order, 'fitting', {'passed': True}, user=self.dentist)
        period = order.statement_line.period
        with patch('django.utils.timezone.now', return_value=datetime(2026,11,4,12,tzinfo=utc_timezone.utc)):
            invoice = close_period(period.pk, 'test:accountant')
        self.assertEqual(invoice.total_amount, Decimal('1560'))
        event = order.task_events.get(event_type='INVOICE')
        generated = generate_invoice_pdf_task(self.tenant.schema_name, str(order.pk), str(event.pk))
        self.assertEqual(generated['status'], 'PDF_READY')
        from .documents import private_open
        with private_open(InvoiceDocument.objects.get(invoice=invoice).storage_name) as stream:
            self.assertTrue(stream.read(5).startswith(b'%PDF-'))
        credit = issue_credit(invoice.pk, order.pk, '100', 'Approved contested line', 'test:accountant', uuid.uuid4())
        credit_event = order.task_events.get(event_type='CREDIT')
        generate_credit_note_pdf_task(self.tenant.schema_name, str(order.pk), str(credit_event.pk))
        refresh_billing_catalog(self.tenant.schema_name)
        self.assertEqual(MonthlyFinancialCatalog.objects.get().net_amount, Decimal('1460'))
        self.assertEqual(MonthlyStatementCatalog.objects.get().closing_month.month, 10)
        with self.assertRaises(ValidationError):
            issue_credit(invoice.pk, order.pk, '2000', 'Too much', 'test', uuid.uuid4())
        from .messaging import deliver_pending
        self.assertEqual(deliver_pending()['status'], 'DISABLED')


def timezone():
    from zoneinfo import ZoneInfo
    return ZoneInfo('Africa/Casablanca')
