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

    def to_cao(self, order):
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
        self.patch(order, status='SALLE_CAO', production_method='CFAO', delivery_date='2026-10-30')

    def to_quality(self, order):
        if order.status == 'SALLE_CAO':
            self.patch(order, status='PREPARATION_CNC')
        lot = ProductionLot.objects.create(code='LOT-' + order.pk.hex)
        lot.prescriptions.add(order)
        self.patch(order, status='USINAGE_CNC')
        self.patch(order, status='FINITION')
        self.patch(order, status='CONTROLE_QUALITE')

    def deliver(self, order):
        self.command(order, 'inspection', {'stage': 'QUALITY', 'checks': dict.fromkeys(['margins','contacts','shade','occlusion','cosmetic','glazing','polishing'], True)})
        self.patch(order, status='CONDITIONNEMENT')
        self.patch(order, status='PRET_EXPEDITION')
        self.command(order, 'checkout', {'qr_token': qr_token(order)}, user=self.courier)
        self.command(order, 'confirm-delivery', {'pin': order._test_pin}, user=self.courier)

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
