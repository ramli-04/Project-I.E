import json
import uuid
from datetime import date, datetime, timedelta, timezone as utc
from decimal import Decimal
from unittest.mock import patch
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import DatabaseError, connection, connections, transaction
from django.test import override_settings, TransactionTestCase
from django.test.utils import CaptureQueriesContext
from django_tenants.test.cases import TenantTestCase
from django_tenants.utils import schema_context, tenant_context
from rest_framework.test import APIClient, APIRequestFactory, force_authenticate

from customers.models import Client, Domain, PlatformAccount
from .billing import close_period, issue_credit
from .business_views import InvoiceSerializer
from .models import (PartnerClinic, Prescription, BillingPeriod, FinanceInvoice, Payment, PaymentAllocation,
                     PaymentReversal, WorkflowEvent, InvoiceDocument)
from .payments import invoice_balances, receivables, TZ
from .test_support import WorkflowFixtures
from .tasks import generate_invoice_pdf_task

NOW = datetime(2026, 11, 25, 12, tzinfo=utc.utc)


@override_settings(OUTBOX_PUBLISH_ON_COMMIT=False, EXTERNAL_DELIVERY_ENABLED=False,
    PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class PaymentTests(WorkflowFixtures, TenantTestCase):
    @classmethod
    def setup_tenant(cls, tenant):
        tenant.name = 'Payment tests lab'

    def setUp(self):
        super().setUp()
        connection.set_tenant(self.tenant)
        clock = patch('django.utils.timezone.now', return_value=NOW)
        clock.start()
        self.addCleanup(clock.stop)
        with schema_context('public'):
            self.manager = get_user_model().objects.create_user(username='payment-manager', is_superuser=True)
            self.dentist = PlatformAccount.objects.create(name='Payment dentist', login_key='payment-dentist', role='DENTIST')
        self.client = APIClient(HTTP_HOST=self.get_test_tenant_domain())
        self.client.force_authenticate(self.manager)
        self.clinic = PartnerClinic.objects.create(name='Payment clinic', pickup_address='Test address',
            contact_phone='000', platform_dentist=self.dentist)
        self.invoice = self.make_invoice()

    def make_invoice(self, clinic=None, amount='1000.00'):
        clinic = clinic or self.clinic
        delivery = date(2026, 10, 10)
        while BillingPeriod.objects.filter(clinic=clinic, month=delivery.replace(day=1)).exists():
            delivery = (delivery.replace(day=1)-timedelta(days=1)).replace(day=10)
        with patch('django.utils.timezone.now', return_value=datetime(2026, 1, 1, 12, tzinfo=utc.utc)):
            order = Prescription.objects.create(patient_ref='PAY-'+uuid.uuid4().hex[:8], dentist_name='Test dentist',
                tooth_number=11, shade='A2', material='Zircone', disinfected=True, total_price=amount,
                base_amount=amount, partner_clinic=clinic, dentist_account=clinic.platform_dentist, accepted=True, impression_type='NUMERIQUE', intake_version=1)
        with patch('django.utils.timezone.now', return_value=datetime.combine(delivery, datetime.min.time(), tzinfo=utc.utc)+timedelta(hours=12)):
            self.deliver_case(order, pin=order._new_delivery_pin)
        return close_period(order.statement_line.period_id, 'test:accountant')

    def body(self, amount='400.00', **changes):
        return {'clinic': self.clinic.pk, 'method': 'CHEQUE', 'amount': amount, 'received_on': '2026-11-25',
            'reference': 'CH-001', 'bank': 'Synthetic bank',
            'allocations': [{'invoice': str(self.invoice.pk), 'amount': amount}], **changes}

    def pay(self, body=None, key=None, status=201):
        result = self.client.post('/api/billing/payments/', body or self.body(), format='json',
                                  HTTP_IDEMPOTENCY_KEY=str(key or uuid.uuid4()))
        self.assertEqual(result.status_code, status, result.data)
        return result

    def summary(self, invoice=None):
        invoice = invoice or self.invoice
        return invoice_balances([invoice])[invoice.pk]

    def test_partial_full_and_multi_invoice_allocations(self):
        self.pay()
        self.assertEqual(self.summary()['balance'], Decimal('600'))
        self.assertEqual(self.summary()['payment_status'], 'PARTIELLE')
        other = self.make_invoice(amount='500')
        self.pay(self.body('1100', allocations=[{'invoice': str(self.invoice.pk), 'amount': '600'},
                                              {'invoice': str(other.pk), 'amount': '500'}]))
        self.assertEqual(self.summary()['balance'], 0)
        self.assertEqual(self.summary()['payment_status'], 'PAYEE')
        self.assertEqual(self.summary(other)['balance'], 0)
        self.assertEqual(PaymentAllocation.objects.count(), 3)

    def test_overallocation_sum_mismatch_duplicates_and_cross_clinic_are_atomic(self):
        other_clinic = PartnerClinic.objects.create(name='Other clinic', pickup_address='Other address', contact_phone='111')
        foreign = self.make_invoice(other_clinic)
        invalid = [self.body('1000.01'), self.body('500', allocations=[{'invoice': str(self.invoice.pk), 'amount': '400'}]),
            self.body('400', allocations=[{'invoice': str(foreign.pk), 'amount': '400'}]),
            self.body('400', allocations=[{'invoice': str(self.invoice.pk), 'amount': '200'}, {'invoice': str(self.invoice.pk), 'amount': '200'}])]
        for body in invalid:
            with self.subTest(body=body):
                self.pay(body, status=400)
                self.assertEqual(Payment.objects.count(), 0)
                self.assertEqual(PaymentAllocation.objects.count(), 0)
        self.assertEqual(self.summary()['balance'], 1000)

    def test_reference_and_lcn_maturity_requirements_per_method(self):
        for method in ['CHEQUE', 'LCN', 'VIREMENT']:
            self.pay(self.body('10', method=method, reference=''), status=400)
        self.pay(self.body('10', method='LCN'), status=400)
        for method in ['CHEQUE', 'VIREMENT', 'ESPECES', 'LCN']:
            self.pay(self.body('10', method=method, reference='' if method == 'ESPECES' else 'REF',
                               due_on='2027-01-25' if method == 'LCN' else None))
        self.assertEqual(Payment.objects.count(), 4)

    def test_invalid_amounts_and_malformed_reversal_do_not_write(self):
        for value in ['0', '-1', 'NaN', 'Infinity', '0.001', '100000000000000.00']:
            self.pay(self.body(value), status=400)
        self.assertFalse(Payment.objects.exists())
        payment = self.pay().data['id']
        response = self.client.post(f'/api/billing/payments/{payment}/reverse/', {'reason': {}}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertFalse(PaymentReversal.objects.exists())

    def test_reversal_reopens_all_allocated_invoices_and_double_reversal_is_rejected(self):
        other = self.make_invoice(amount='500')
        payment = self.pay(self.body('700', allocations=[{'invoice': str(self.invoice.pk), 'amount': '400'},
            {'invoice': str(other.pk), 'amount': '300'}])).data['id']
        response = self.client.post(f'/api/billing/payments/{payment}/reverse/', {'reason': 'IMPAYE', 'notes': 'Returned cheque'}, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(self.summary()['balance'], 1000)
        self.assertEqual(self.summary(other)['balance'], 500)
        self.assertEqual(self.summary()['payment_status'], 'IMPAYEE')
        self.assertEqual(self.client.post(f'/api/billing/payments/{payment}/reverse/', {'reason': 'ANNULE'}, format='json').status_code, 400)
        self.assertEqual(PaymentReversal.objects.count(), 1)
        self.assertTrue(WorkflowEvent.objects.filter(kind='REVERSE_PAYMENT', payload__action='REVERSE_PAYMENT').exists())

    def test_only_cheque_or_lcn_can_be_marked_unpaid_but_any_method_can_be_cancelled(self):
        for method in ['VIREMENT', 'ESPECES']:
            payment = self.pay(self.body('10', method=method)).data['id']
            self.assertEqual(self.client.post(f'/api/billing/payments/{payment}/reverse/', {'reason': 'IMPAYE'}, format='json').status_code, 400)
            self.assertEqual(self.client.post(f'/api/billing/payments/{payment}/reverse/', {'reason': 'ANNULE'}, format='json').status_code, 201)

    def test_idempotent_same_body_replay_and_changed_body_409(self):
        key = uuid.uuid4()
        first = self.pay(key=key)
        count = WorkflowEvent.objects.filter(kind='RECORD_PAYMENT').count()
        second = self.pay(key=key)
        self.assertEqual(first.data, second.data)
        self.pay(self.body('401'), key=key, status=409)
        self.assertEqual(Payment.objects.count(), 1)
        self.assertEqual(PaymentAllocation.objects.count(), 1)
        self.assertEqual(WorkflowEvent.objects.filter(kind='RECORD_PAYMENT').count(), count)
        self.assertTrue(WorkflowEvent.objects.filter(kind='RECORD_PAYMENT', payload__action='RECORD_PAYMENT').exists())

    def test_credit_notes_reduce_balance_and_overpayment_is_separate_not_overdue(self):
        self.pay(self.body('1000'))
        source = self.invoice.lines[0]['case_id']
        issue_credit(self.invoice.pk, source, '100', 'Post-payment adjustment', 'test:accountant', uuid.uuid4())
        self.assertEqual(self.summary()['paid_amount'], 1000)
        self.assertEqual(self.summary()['credited_amount'], 100)
        self.assertEqual(self.summary()['balance'], -100)
        self.assertEqual(self.summary()['payment_status'], 'TROP_PERCU')
        row = receivables(today=date(2027, 10, 1))[0]
        self.assertEqual(row['total_due'], 0)
        self.assertEqual(row['overpaid_amount'], 100)
        self.assertTrue(all(amount == 0 for amount in row['buckets'].values()))
        self.pay(self.body('1'), status=400)

    def test_credit_before_payment_limits_allocation_to_net(self):
        issue_credit(self.invoice.pk, self.invoice.lines[0]['case_id'], '100', 'Adjustment', 'test:accountant', uuid.uuid4())
        self.pay(self.body('901'), status=400)
        self.pay(self.body('900'))
        self.assertEqual(self.summary()['balance'], 0)
        self.assertEqual(self.summary()['payment_status'], 'PAYEE')

    def test_aging_boundaries_are_disjoint_and_sum_to_total_due(self):
        due = self.summary()['due_date']
        self.assertEqual(due, NOW.astimezone(TZ).date()+timedelta(days=60))
        for days, bucket in [(0, None), (1, '0_30'), (30, '0_30'), (31, '31_60'), (60, '31_60'), (61, '61_90'), (90, '61_90'), (91, '90_plus')]:
            with self.subTest(days=days):
                row = receivables(today=due+timedelta(days=days))[0]
                self.assertEqual(row['not_due'], 1000 if bucket is None else 0)
                self.assertEqual(row['oldest_overdue_days'], days)
                self.assertEqual(sum(row['buckets'].values())+row['not_due'], row['total_due'])
                for name, amount in row['buckets'].items(): self.assertEqual(amount, 1000 if name == bucket else 0)

    def test_today_uses_casablanca_and_terms_are_bounded_at_db_and_api(self):
        at = datetime(2027, 6, 1, 23, 30, tzinfo=utc.utc)
        with patch('django.utils.timezone.now', return_value=at):
            self.assertEqual(self.summary()['days_overdue'], max(0, (at.astimezone(TZ).date()-self.summary()['due_date']).days))
        for days in [-1, 121]:
            with self.assertRaises(DatabaseError), transaction.atomic():
                PartnerClinic.objects.filter(pk=self.clinic.pk).update(payment_terms_days=days)
            response = self.client.patch(f'/api/partner-clinics/{self.clinic.pk}/', {'payment_terms_days': days}, format='json')
            self.assertEqual(response.status_code, 400)
        response = self.client.patch(f'/api/partner-clinics/{self.clinic.pk}/', {'payment_terms_days': 0}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(self.summary()['terms_days'], 0)

    def test_payment_and_allocations_require_positive_values_reference_and_maturity_at_db(self):
        values = dict(clinic=self.clinic, method='CHEQUE', amount='10', received_on=date(2026, 11, 25),
            reference='REF', recorded_by='test', payload_digest='0'*64)
        for changes in [{'amount': '0'}, {'amount': '-1'}, {'reference': '  '}, {'method': 'LCN', 'due_on': None}]:
            with self.subTest(changes=changes), self.assertRaises(DatabaseError), transaction.atomic():
                Payment.objects.create(**{**values, **changes}, idempotency_key=uuid.uuid4())
        payment = Payment.objects.get(pk=self.pay().data['id'])
        other_invoice = self.make_invoice()
        for amount in ['0', '-1']:
            with self.assertRaises(DatabaseError), transaction.atomic():
                PaymentAllocation.objects.create(payment=payment, invoice=other_invoice, amount=amount)
        # NaN is rejected by Django's DecimalField before SQL; test the DB guard directly.
        with self.assertRaises(DatabaseError), transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute("INSERT INTO api_payment (id,clinic_id,method,amount,received_on,reference,bank,notes,recorded_by,idempotency_key,payload_digest,created_at) VALUES (%s,%s,'CHEQUE','NaN',%s,'REF','','','test',%s,%s,%s)",
                    [uuid.uuid4(), self.clinic.pk, date(2026,11,25), uuid.uuid4(), '0'*64, NOW])
        with self.assertRaises(DatabaseError), transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute("INSERT INTO api_paymentallocation (payment_id,invoice_id,amount) VALUES (%s,%s,'NaN')", [payment.pk,other_invoice.pk])


    def test_all_three_ledgers_block_model_and_raw_sql_update_delete(self):
        payment = Payment.objects.get(pk=self.pay().data['id'])
        allocation = payment.allocations.get()
        response = self.client.post(f'/api/billing/payments/{payment.pk}/reverse/', {'reason': 'ANNULE'}, format='json')
        reversal = PaymentReversal.objects.get(pk=response.data['id'])
        for obj in [payment, allocation, reversal]:
            with self.subTest(model=type(obj).__name__):
                with self.assertRaises(ValidationError): obj.save()
                with self.assertRaises(ValidationError): obj.delete()
                for statement in ['UPDATE {table} SET id=id WHERE id=%s', 'DELETE FROM {table} WHERE id=%s']:
                    with self.assertRaises(DatabaseError), transaction.atomic():
                        with connection.cursor() as cursor:
                            cursor.execute(statement.format(table=connection.ops.quote_name(obj._meta.db_table)), [obj.pk])
        self.assertEqual(Payment.objects.count(), 1)
        self.assertEqual(PaymentAllocation.objects.count(), 1)
        self.assertEqual(PaymentReversal.objects.count(), 1)

    def test_original_invoice_fields_and_stored_pdf_bytes_never_change(self):
        source = Prescription.objects.get(pk=self.invoice.lines[0]['case_id'])
        generate_invoice_pdf_task(self.tenant.schema_name, source.pk)
        before = FinanceInvoice.objects.values().get(pk=self.invoice.pk)
        doc_before = InvoiceDocument.objects.values().get(invoice=self.invoice)
        response = self.client.get(f'/api/billing/invoices/{self.invoice.pk}/pdf/')
        pdf = b''.join(response.streaming_content)
        self.pay()
        self.assertEqual(FinanceInvoice.objects.values().get(pk=self.invoice.pk), before)
        self.assertEqual(InvoiceDocument.objects.values().get(invoice=self.invoice), doc_before)
        self.assertEqual(b''.join(self.client.get(f'/api/billing/invoices/{self.invoice.pk}/pdf/').streaming_content), pdf)

    def test_bulk_invoice_balance_serialization_has_constant_query_count(self):
        self.pay()
        one = list(FinanceInvoice.objects.all())
        with CaptureQueriesContext(connection) as first:
            data = InvoiceSerializer(one, many=True).data
        self.assertEqual(data[0]['balance'], '600.00')
        for _ in range(3): self.make_invoice()
        many = list(FinanceInvoice.objects.all())
        with CaptureQueriesContext(connection) as second:
            InvoiceSerializer(many, many=True).data
        self.assertEqual(len(first), len(second))
        self.assertEqual(sum(item['sql'].lstrip().upper().startswith('SELECT') for item in second.captured_queries), 3)

    def test_finance_roles_can_record_reverse_and_read_other_roles_cannot(self):
        target = self.pay(self.body('10')).data['id']
        with schema_context('public'):
            accounts = [PlatformAccount.objects.create(name='Payments '+role, login_key='payments-'+role.lower(),
                role='LAB', workstation_role=role, laboratory=self.tenant)
                for role in ['MANAGER', 'COMPTABILITE', 'RECEPTION', 'CAO', 'FAO', 'QUALITE']]
        for account in accounts:
            self.client.force_authenticate(account)
            allowed = account.workstation_role in {'MANAGER', 'COMPTABILITE'}
            self.assertEqual(self.client.get('/api/billing/payments/').status_code, 200 if allowed else 403)
            self.assertEqual(self.client.get('/api/billing/receivables/').status_code, 200 if allowed else 403)
            response = self.pay(self.body('10'), status=201 if allowed else 403)
            if allowed:
                self.assertEqual(self.client.post(f"/api/billing/payments/{response.data['id']}/reverse/", {'reason': 'ANNULE'}, format='json').status_code, 201)
            else:
                self.assertEqual(self.client.post(f'/api/billing/payments/{target}/reverse/', {'reason': 'ANNULE'}, format='json').status_code, 403)
        self.client.force_authenticate(self.dentist)
        self.assertEqual(self.client.get('/api/billing/payments/').status_code, 403)

    def test_dentist_reads_only_owned_invoice_balance_on_existing_invoice_path(self):
        self.pay()
        source = self.invoice.lines[0]['case_id']
        self.client.force_authenticate(self.dentist)
        path = f'/platform/dentist/orders/{self.tenant.schema_name}/{source}/invoice-balance/'
        result = self.client.get(path)
        self.assertEqual(result.status_code, 200, result.data)
        self.assertEqual(result.data['balance'], '600.00')
        self.assertNotIn('lines', result.data)
        self.assertNotIn('recorded_by', result.data)
        with schema_context('public'):
            other = PlatformAccount.objects.create(name='Other payment dentist', login_key='other-payment-dentist', role='DENTIST')
        self.client.force_authenticate(other)
        self.assertEqual(self.client.get(path).status_code, 404)

    def test_tenant_isolation_hides_invoices_payments_and_receivables(self):
        payment = self.pay().data['id']
        with schema_context('public'):
            other = Client.objects.create(schema_name='payment_isolation_lab', name='Other payment lab')
        def cleanup():
            with schema_context('public'):
                PlatformAccount.objects.filter(laboratory=other).update(laboratory=None)
                other.delete(force_drop=True)
        self.addCleanup(cleanup)
        with tenant_context(other):
            self.assertEqual(receivables(), [])
            self.assertFalse(Payment.objects.filter(pk=payment).exists())
            self.assertFalse(FinanceInvoice.objects.filter(pk=self.invoice.pk).exists())

        from .payment_views import PaymentViewSet, receivables_view
        from .business_views import FinanceInvoiceViewSet
        with schema_context('public'):
            account = PlatformAccount.objects.create(name='Other payment manager', login_key='other-payment-manager',
                role='LAB', workstation_role='MANAGER', laboratory=other)
        factory = APIRequestFactory()
        with tenant_context(other):
            for view in [PaymentViewSet, FinanceInvoiceViewSet]:
                request = factory.get('/api/billing/')
                request.tenant = other
                force_authenticate(request, account)
                response = view.as_view({'get': 'list'})(request)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.data['count'], 0)
            for view, identity, operation in [(PaymentViewSet, payment, 'retrieve'),
                (FinanceInvoiceViewSet, str(self.invoice.pk), 'retrieve'), (PaymentViewSet, payment, 'reverse')]:
                request = factory.post('/api/billing/', {'reason': 'ANNULE'}, format='json') if operation == 'reverse' else factory.get('/api/billing/')
                request.tenant = other
                force_authenticate(request, account)
                response = view.as_view({'post' if operation == 'reverse' else 'get': operation})(request, pk=identity)
                self.assertEqual(response.status_code, 404)
            request = factory.get('/api/billing/receivables/')
            request.tenant = other
            force_authenticate(request, account)
            response = receivables_view(request)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.data, [])
            self.assertEqual(PaymentReversal.objects.count(), 0)
        self.assertEqual(Payment.objects.count(), 1)
        self.assertEqual(PaymentReversal.objects.count(), 0)


@override_settings(OUTBOX_PUBLISH_ON_COMMIT=False, EXTERNAL_DELIVERY_ENABLED=False,
    PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class PaymentConcurrencyTests(WorkflowFixtures, TransactionTestCase):
    make_invoice = PaymentTests.make_invoice
    body = PaymentTests.body

    def setUp(self):
        super().setUp()
        connection.set_schema_to_public()
        self.tenant = Client.objects.create(schema_name='payment_race_'+uuid.uuid4().hex[:8], name='Payment race lab')
        self.domain = 'payment-race.localhost'
        Domain.objects.create(tenant=self.tenant, domain=self.domain, is_primary=True)
        self.manager = get_user_model().objects.create_user(username='race-manager', is_superuser=True)
        self.dentist = PlatformAccount.objects.create(name='Race dentist', login_key='race-dentist', role='DENTIST')
        connection.set_tenant(self.tenant)
        self.client = APIClient(HTTP_HOST=self.domain)
        self.client.force_authenticate(self.manager)
        self.clinic = PartnerClinic.objects.create(name='Race clinic', pickup_address='Test', contact_phone='0', platform_dentist=self.dentist)
        clock = patch('django.utils.timezone.now', return_value=NOW)
        clock.start()
        self.addCleanup(clock.stop)
        self.invoice = self.make_invoice()

    def tearDown(self):
        connection.set_schema_to_public()
        self.tenant.delete(force_drop=True)
        super().tearDown()

    def run_pair(self, same_key=False):
        from .payments import record_payment
        from rest_framework.exceptions import ValidationError as APIValidationError
        barrier = Barrier(2)
        key = uuid.uuid4()
        body = self.body('700')
        tenant = self.tenant
        def pay():
            connections.close_all()
            try:
                with tenant_context(tenant):
                    barrier.wait(timeout=20)
                    try:
                        return str(record_payment(body, 'test:race', key if same_key else uuid.uuid4()).pk)
                    except (ValidationError, APIValidationError):
                        return None
            finally:
                connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(pay), pool.submit(pay)]
            return [future.result(timeout=40) for future in futures]

    def test_concurrent_allocations_cannot_overdraw_an_invoice(self):
        results = self.run_pair()
        self.assertEqual(sum(value is not None for value in results), 1)
        self.assertEqual(Payment.objects.count(), 1)
        self.assertEqual(invoice_balances([self.invoice])[self.invoice.pk]['balance'], 300)

    def test_concurrent_identical_replay_creates_one_payment(self):
        results = self.run_pair(same_key=True)
        self.assertIsNotNone(results[0])
        self.assertEqual(results[0], results[1])
        self.assertEqual(Payment.objects.count(), 1)
        self.assertEqual(PaymentAllocation.objects.count(), 1)
