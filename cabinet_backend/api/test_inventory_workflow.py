import uuid
from datetime import date, datetime, timedelta, timezone as dt_timezone
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import DatabaseError, connection, transaction
from django.db.migrations.executor import MigrationExecutor
from django.test import override_settings
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from django_tenants.test.cases import TenantTestCase
from django_tenants.utils import schema_context
from rest_framework.test import APIClient

from .analytics import refresh_billing_catalog
from .inventory import classify_rework, record_movement
from .models import (Inventory, InventoryTransaction, InvoiceArtifact, InvoiceDispatchLog,
                     MonthlyStockLossCatalog, Prescription, PrescriptionHistory, TaskOutbox)
from .outbox import publish_event
from .serializers import PrescriptionSerializer
from .signals import prescription_audit_context
from .tasks import (calculate_automatic_calendar_task, generate_invoice_pdf_task,
                    publish_tenant_outbox_task)
from .workflow import next_status
from customers.models import Client


@override_settings(OUTBOX_PUBLISH_ON_COMMIT=False)
class InventoryWorkflowTests(TenantTestCase):
    @classmethod
    def setup_tenant(cls, tenant):
        tenant.name = 'Inventory workflow laboratory'

    def setUp(self):
        connection.set_tenant(self.tenant)
        with schema_context('public'):
            manager = get_user_model().objects.create_user(username='ledger-manager', is_superuser=True)
        self.client = APIClient(HTTP_HOST=self.get_test_tenant_domain())
        self.client.force_authenticate(user=manager)
        self.item = Inventory.objects.create(material_name='Zircone A2', quantity='10.125',
                                             unit='DISQUE', alert_threshold='2', unit_cost='30.50')

    def order(self, **changes):
        return Prescription.objects.create(**{
            'patient_ref': 'LEDGER', 'dentist_name': 'Clinic', 'tooth_number': 11,
            'shade': 'A2', 'material': 'Zircone', 'disinfected': True, **changes,
        })

    def production_order(self):
        """Walk through BPMN transitions to reach CONTROLE_QUALITE legitimately."""
        order = self.order(impression_type='NUMERIQUE', intake_version=1)
        with prescription_audit_context('system', 'setup', metadata={'role': 'MANAGER', 'action': 'TRANSITION'}):
            order.accepted = True
            order.save(update_fields=['accepted'])
            order.analysis_validated = True
            order.status = 'ANALYSE_DEMANDE'
            order.save(update_fields=['status', 'analysis_validated'])
            order.reception_validated = True
            order.status = 'A_CONFIRMER'
            order.save(update_fields=['status', 'reception_validated'])
            order.status = 'CONTROLE_DOSSIER'
            order.save(update_fields=['status'])
            order.production_method = 'CFAO'
            order.delivery_date = date.today() + timedelta(days=7)
            order.total_price = Decimal('500')
            order.status = 'PLANIFICATION'
            order.save(update_fields=['status', 'production_method', 'delivery_date', 'total_price'])
            for step in ['SALLE_CAO', 'PREPARATION_CNC', 'USINAGE_CNC', 'FINITION', 'CONTROLE_QUALITE']:
                order.status = step
                order.save(update_fields=['status'])
        order.quality_validated = True
        order.save(update_fields=['quality_validated'])
        return order

    def movement(self, quantity, kind='RESTOCK', **changes):
        return record_movement(inventory_item=self.item, quantity_changed=Decimal(quantity),
                               transaction_type=kind, idempotency_key=changes.pop('idempotency_key', uuid.uuid4()), **changes)

    def test_opening_balance_and_fractional_commands_are_exact_and_idempotent(self):
        opening = self.item.transactions.get()
        self.assertEqual(opening.quantity_changed, Decimal('10.125'))
        key = uuid.uuid4()
        first = self.movement('0.000001', idempotency_key=key)
        self.assertEqual(self.movement('0.000001', idempotency_key=key).pk, first.pk)
        self.item.refresh_from_db()
        self.assertEqual(self.item.quantity, Decimal('10.125001'))
        with self.assertRaises(ValidationError):
            self.movement('2', idempotency_key=key)
        self.assertEqual(self.item.transactions.count(), 2)

    def test_legacy_migration_preserves_balance_seeds_observed_opening_and_refuses_rounding(self):
        before = [('api', '0017_monthly_billing_materialized_views')]
        after = [('api', '0023_delivery_statements_and_financial_catalogs')]
        with connection.cursor() as cursor:
            cursor.execute('SET CONSTRAINTS ALL IMMEDIATE')
        executor = MigrationExecutor(connection)
        executor.migrate(before)
        old_apps = executor.loader.project_state(before).apps
        old_inventory = old_apps.get_model('api', 'Inventory')
        old_prescription = old_apps.get_model('api', 'Prescription')
        try:
            item = old_inventory.objects.get(pk=self.item.pk)
            item.quantity = 1.1234567
            item.save(update_fields=['quantity'])
            with self.assertRaisesMessage(ValueError, 'cannot be converted losslessly'):
                MigrationExecutor(connection).migrate(after)
            item.quantity = 2.125
            item.save(update_fields=['quantity'])
            legacy = old_prescription.objects.create(patient_ref='LEGACY', dentist_name='Clinic',
                                                     tooth_number=12, shade='A2', material='PMMA')
            MigrationExecutor(connection).migrate(after)
            item = Inventory.objects.get(pk=item.pk)
            opening = item.transactions.get(transaction_type='OPENING')
            self.assertEqual(item.quantity, Decimal('2.125'))
            self.assertEqual(opening.quantity_changed, item.quantity)
            self.assertEqual(opening.balance_after, item.quantity)
            self.assertIsNone(opening.unit_cost_snapshot)
            self.assertEqual(opening.changed_by, 'migration:observed-opening')
            self.assertTrue(TaskOutbox.objects.filter(prescription_id=legacy.pk, event_type='CALENDAR').exists())
        finally:
            # Restore the current schema even when a regression causes an assertion failure.
            current = MigrationExecutor(connection)
            applied = current.loader.applied_migrations
            if ('api', '0018_inventory_ledger_and_background_events') not in applied:
                old_inventory.objects.filter(pk=self.item.pk).update(quantity=2.125)
            MigrationExecutor(connection).migrate(after)

    def test_insufficient_stock_invalid_signs_and_rollback_preserve_balance(self):
        for qty, kind in [('-11', 'REWORK_LOSS'), ('0', 'RESTOCK'), ('-1', 'RESTOCK'), ('1', 'USAGE')]:
            with self.subTest(qty=qty, kind=kind), self.assertRaises(ValidationError):
                self.movement(qty, kind)
        with self.assertRaises(RuntimeError), transaction.atomic():
            self.movement('5')
            raise RuntimeError('Rollback command')
        self.item.refresh_from_db()
        self.assertEqual(self.item.quantity, Decimal('10.125'))
        self.assertEqual(self.item.transactions.count(), 1)

    def test_sql_and_orm_mutations_are_rejected(self):
        entry = self.item.transactions.get()
        for command, args in [
            ('UPDATE api_inventory SET quantity=quantity+1 WHERE id=%s', [self.item.pk]),
            ("UPDATE api_inventory SET unit='GRAMMES' WHERE id=%s", [self.item.pk]),
            ('DELETE FROM api_inventorytransaction WHERE id=%s', [entry.pk]),
            ("UPDATE api_inventorytransaction SET notes='tampered' WHERE id=%s", [entry.pk]),
            ('TRUNCATE api_inventorytransaction CASCADE', []),
        ]:
            with self.subTest(command=command), self.assertRaises(DatabaseError), transaction.atomic():
                with connection.cursor() as cursor:
                    cursor.execute(command, args)
        with self.assertRaises(ValidationError):
            InventoryTransaction.objects.filter(pk=entry.pk).update(notes='changed')
        with self.assertRaises(ValidationError):
            entry.delete()

    def test_rework_reclassifies_consumption_without_deducting_it_twice(self):
        order = self.production_order()
        usage = self.movement('-2.5', 'USAGE', prescription=order)
        self.item.refresh_from_db()
        balance = self.item.quantity
        metadata = {
            'role': 'QUALITE',
            'action': 'REWORK',
            'origin': 'LAB',
            'cause': 'Fracture during finishing',
            'corrective_action': 'Recalibrate tool',
            'restart_status': 'SALLE_CAO',
            'cause_step': 'CONTROLE_QUALITE',
            'losses': [{'usage_id': str(usage.pk), 'quantity': '2.5'}],
        }
        with prescription_audit_context('user:1:operator', 'Fracture during finishing', metadata=metadata):
            order.rework_restart_status = 'SALLE_CAO'
            order.status = 'A_REFAIRE'
            order.save(update_fields=['status'])
        self.item.refresh_from_db()
        order.refresh_from_db()
        self.assertEqual(self.item.quantity, balance)
        self.assertEqual(order.production_attempt, 2)
        self.assertFalse(order.quality_validated)
        history = order.audit_history.last()
        loss = self.item.transactions.get(transaction_type='REWORK_LOSS')
        self.assertEqual(loss.reclassifies_id, usage.pk)
        self.assertEqual(loss.unit_cost_snapshot, Decimal('30.50'))
        self.assertEqual(loss.source_history_id, history.pk)
        self.assertEqual(classify_rework(history), 2)
        self.assertEqual(self.item.transactions.filter(transaction_type='REWORK_LOSS').count(), 1)
        self.assertEqual(next_status(order), 'SALLE_CAO')
        order.status = 'SALLE_CAO'
        order.save(update_fields=['status'])
        replacement = self.movement('-1', 'USAGE', prescription=order)
        self.assertEqual(replacement.production_attempt, 2)
        self.item.refresh_from_db()
        self.assertEqual(self.item.quantity, balance - 1)

    def test_invalid_rework_rolls_back_status_history_and_outbox(self):
        order = self.production_order()
        count = order.audit_history.count()
        with self.assertRaises(ValidationError), prescription_audit_context('operator', 'Defect'):
            order.status = 'A_REFAIRE'
            order.save(update_fields=['status'])
        order.refresh_from_db()
        self.assertEqual(order.status, 'CONTROLE_QUALITE')
        self.assertEqual(order.audit_history.count(), count)
        self.assertEqual(order.production_attempt, 1)
        with self.assertRaises(ValidationError):
            PrescriptionHistory.objects.create(prescription=order, previous_status=order.status,
                                               new_status='A_REFAIRE', action_notes='No allocation')
        self.assertEqual(order.audit_history.count(), count)

    def test_rework_serializer_requires_reason_materials_and_laboratory_access(self):
        order = self.production_order()
        # Direct PATCH cannot perform rework without audited command
        response = self.client.patch(f'/api/prescriptions/{order.pk}/',
                                     {'status': 'A_REFAIRE', 'action_notes': 'Defect'}, format='json')
        self.assertEqual(response.status_code, 400)
        # Rework command requires origin, cause, corrective_action
        cmd_url = f'/api/prescriptions/{order.pk}/command/'
        bad_cmd = self.client.post(cmd_url, {'action': 'rework', 'data': {'cause': 'Defect'}}, format='json',
                                   HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()))
        self.assertEqual(bad_cmd.status_code, 400)
        # Record material usage and execute valid rework command
        usage = self.movement('-1', 'USAGE', prescription=order)
        valid_cmd = self.client.post(cmd_url, {
            'action': 'rework',
            'data': {
                'origin': 'LAB',
                'cause': 'Defect during machining',
                'corrective_action': 'Recalibrate tool',
                'restart_status': 'SALLE_CAO',
                'losses': [{'usage_id': str(usage.pk), 'quantity': '1'}],
            }
        }, format='json', HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()))
        self.assertEqual(valid_cmd.status_code, 200, valid_cmd.data)
        order.refresh_from_db()
        self.assertEqual(order.production_attempt, 2)
        self.assertEqual(order.status, 'A_REFAIRE')

    def test_reversal_copies_historical_cost_and_cannot_repeat(self):
        loss = self.movement('-1', 'REWORK_LOSS')
        self.item.unit_cost = Decimal('90')
        self.item.save(update_fields=['unit_cost'])
        reversal = self.movement('1', 'REVERSAL', reversal_of=loss)
        self.assertEqual(reversal.unit_cost_snapshot, Decimal('30.5'))
        with self.assertRaises(ValidationError):
            self.movement('1', 'REVERSAL', reversal_of=loss)
        self.item.refresh_from_db()
        self.assertEqual(self.item.quantity, Decimal('10.125'))

    def test_ledger_endpoint_balance_protection_idempotency_and_read_only_history(self):
        url = f'/api/inventory/{self.item.pk}/'
        self.assertEqual(self.client.patch(url, {'quantity': '999'}, format='json').status_code, 400)
        payload = {'inventory_item': self.item.pk, 'quantity_changed': '0.25',
                   'transaction_type': 'RESTOCK', 'idempotency_key': str(uuid.uuid4())}
        first = self.client.post('/api/inventory-transactions/', payload, format='json')
        self.assertEqual(first.status_code, 201, first.data)
        second = self.client.post('/api/inventory-transactions/', payload, format='json')
        self.assertEqual(second.status_code, 201, second.data)
        self.assertEqual(first.data['id'], second.data['id'])
        detail = f'/api/inventory-transactions/{first.data["id"]}/'
        self.assertEqual(self.client.patch(detail, {'quantity_changed': '4'}, format='json').status_code, 405)
        self.assertEqual(self.client.delete(detail).status_code, 405)
        self.assertEqual(self.client.get('/api/inventory-transactions/?prescription=bad').status_code, 400)

    def test_calendar_uses_local_creation_date_calendar_days_and_preserves_manual_date(self):
        # July UTC+1: this timestamp belongs to the following local calendar day.
        created = datetime(2026, 7, 1, 23, 30, tzinfo=dt_timezone.utc)
        for express, expected in [(False, '2026-07-06'), (True, '2026-07-04')]:
            with patch('django.utils.timezone.now', return_value=created):
                order = self.order(is_fast_track=express)
            order.delivery_date = date(2026, 7, 15)
            order.save(update_fields=['delivery_date'])
            event = order.task_events.get(event_type='CALENDAR')
            result = calculate_automatic_calendar_task(self.tenant.schema_name, str(order.pk), str(event.pk))
            self.assertEqual(result['deadline'], expected)
            order.refresh_from_db()
            self.assertEqual(order.delivery_date, date(2026, 7, 15))
            calculated_at = order.deadline_calculated_at
            calculate_automatic_calendar_task(self.tenant.schema_name, str(order.pk), str(event.pk))
            order.refresh_from_db()
            self.assertEqual(order.deadline_calculated_at, calculated_at)
            event.refresh_from_db()
            self.assertIsNotNone(event.processed_at)

    def test_invoice_mock_is_idempotent_immutable_and_never_marks_delivery_as_sent(self):
        from .models import BillingPeriod, FinanceInvoice, StatementLine, PartnerClinic
        order = self.order(total_price=500)
        with self.assertRaises(ValueError):
            generate_invoice_pdf_task(self.tenant.schema_name, str(order.pk))
        clinic = PartnerClinic.objects.create(name='Invoice Test Clinic', pickup_address='123 Main St')
        order.partner_clinic = clinic
        order.delivered_at = timezone.now()
        order.save(update_fields=['partner_clinic', 'delivered_at'])
        period = BillingPeriod.objects.create(clinic=clinic, month=timezone.now().date().replace(day=1))
        StatementLine.objects.create(period=period, prescription=order, base_amount=Decimal('500'), express_surcharge=Decimal('0'))
        FinanceInvoice.objects.create(period=period, number='INV-TEST-001', clinic_name=clinic.name, lines=[], base_amount=Decimal('500'), express_surcharge=Decimal('0'), total_amount=Decimal('500'), issued_by='test')
        period.closed_at = timezone.now()
        period.closed_by = 'test'
        period.save(update_fields=['closed_at', 'closed_by'])
        with prescription_audit_context('system', 'invoice', metadata={'role': 'MANAGER', 'action': 'ISSUE_INVOICE'}):
            order.billing_stage = 'FACTURE'
            order.invoiced_at = timezone.now()
            order.invoiced_amount = Decimal('500.00')
            order.invoiced_clinic_name = clinic.name
            order.save(update_fields=['billing_stage', 'invoiced_at', 'invoiced_amount', 'invoiced_clinic_name'])
        event = order.task_events.get(event_type='INVOICE')
        for _ in range(2):
            result = generate_invoice_pdf_task(self.tenant.schema_name, str(order.pk), str(event.pk))
            self.assertEqual(result['dispatch'], 'QUEUED')
        self.assertEqual(InvoiceArtifact.objects.count(), 1)
        self.assertEqual(InvoiceDispatchLog.objects.count(), 2)
        artifact = InvoiceArtifact.objects.get()
        self.assertEqual(artifact.snapshot['amount'], '500.00')
        self.assertEqual(artifact.status, 'PDF_READY')
        self.assertTrue(artifact.storage_name.endswith('.pdf'))
        with self.assertRaises(DatabaseError), transaction.atomic(), connection.cursor() as cursor:
            cursor.execute("UPDATE api_invoiceartifact SET status='SENT'")

    def test_tasks_reject_public_unknown_and_inactive_tenants(self):
        order = self.order()
        for schema in ['public', 'unknown_nonexistent_schema']:
            with self.assertRaises(ValueError):
                calculate_automatic_calendar_task(schema, str(order.pk))
        with schema_context('public'):
            type(self.tenant).objects.filter(pk=self.tenant.pk).update(is_active=False)
        with self.assertRaises(ValueError):
            calculate_automatic_calendar_task(self.tenant.schema_name, str(order.pk))

    def test_calendar_recalculates_on_priority_change_without_overwriting_manual_date(self):
        order = self.order()
        calculate_automatic_calendar_task(self.tenant.schema_name, str(order.pk))
        order.refresh_from_db()
        standard = order.automatic_deadline
        order.is_fast_track = True
        order.delivery_date = date(2027, 1, 1)
        order.save(update_fields=['is_fast_track', 'delivery_date'])
        self.assertEqual(order.task_events.filter(event_type='CALENDAR').count(), 2)
        calculate_automatic_calendar_task(self.tenant.schema_name, str(order.pk))
        order.refresh_from_db()
        self.assertEqual(order.automatic_deadline, standard - timedelta(days=2))
        self.assertEqual(order.delivery_date, date(2027, 1, 1))

    def test_identical_ids_and_idempotency_keys_remain_isolated_between_tenants(self):
        order = self.order()
        key = uuid.uuid4()
        self.movement('1', idempotency_key=key)
        with schema_context('public'):
            other = Client.objects.create(schema_name='ledger_other', name='Isolated ledger laboratory')
        try:
            with schema_context(other.schema_name):
                isolated = Inventory.objects.create(pk=self.item.pk, material_name='Other item',
                                                     quantity='7', unit='GRAMMES', alert_threshold='0')
                twin = Prescription.objects.create(pk=order.pk, patient_ref='OTHER', dentist_name='Other clinic', disinfected=True,
                                                    tooth_number=12, shade='A1', material='PMMA')
                record_movement(inventory_item=isolated, quantity_changed=Decimal('1'), transaction_type='RESTOCK',
                                idempotency_key=key)
                self.assertEqual(InventoryTransaction.objects.filter(idempotency_key=key).count(), 1)
                calculate_automatic_calendar_task(other.schema_name, str(twin.pk))
                self.assertEqual(Inventory.objects.get(pk=isolated.pk).quantity, Decimal('8'))
                self.assertIsNotNone(Prescription.objects.get(pk=twin.pk).automatic_deadline)
            self.item.refresh_from_db()
            order.refresh_from_db()
            self.assertEqual(self.item.quantity, Decimal('11.125'))
            self.assertIsNone(order.automatic_deadline)
        finally:
            with schema_context('public'):
                with connection.cursor() as cursor:
                    cursor.execute('SET CONSTRAINTS ALL IMMEDIATE')
                other.delete(force_drop=True)

    def test_outbox_is_created_with_source_and_rollback_removes_both(self):
        before = TaskOutbox.objects.count()
        with self.assertRaises(RuntimeError), transaction.atomic():
            order = self.order()
            self.assertTrue(order.task_events.filter(event_type='CALENDAR').exists())
            raise RuntimeError('Rollback source')
        self.assertEqual(TaskOutbox.objects.count(), before)
        self.assertEqual(Prescription.objects.count(), 0)

    def test_outbox_broker_failure_is_durable_then_periodic_recovery_republishes(self):
        order = self.order()
        # Mark concurrent CACHE event processed so this test isolates the CALENDAR outbox retry
        order.task_events.filter(event_type='CACHE').update(processed_at=timezone.now())
        event = order.task_events.get(event_type='CALENDAR')
        with patch('api.outbox.current_app.send_task', side_effect=OSError('Broker down')):
            self.assertFalse(publish_event(self.tenant.schema_name, event.pk))
        event.refresh_from_db()
        self.assertIsNone(event.processed_at)
        self.assertEqual(event.attempts, 1)
        self.assertIn('failed', event.last_error)
        event.next_attempt_at = timezone.now() - timedelta(seconds=1)
        event.save(update_fields=['next_attempt_at'])
        with patch('api.outbox.current_app.send_task') as send:
            self.assertEqual(publish_tenant_outbox_task(self.tenant.schema_name)['published'], 1)
            self.assertEqual(send.call_args.args[0], 'api.tasks.calculate_automatic_calendar_task')
            self.assertEqual(send.call_args.kwargs['args'][0], self.tenant.schema_name)
        event.refresh_from_db()
        self.assertEqual(event.attempts, 2)
        calculate_automatic_calendar_task(self.tenant.schema_name, str(order.pk), str(event.pk))
        with patch('api.outbox.current_app.send_task') as send:
            self.assertFalse(publish_event(self.tenant.schema_name, event.pk))
            send.assert_not_called()

    def test_publication_waits_for_commit_and_failure_does_not_undo_source(self):
        with override_settings(OUTBOX_PUBLISH_ON_COMMIT=True), patch('api.outbox.publish_event') as publish:
            with self.captureOnCommitCallbacks(execute=True):
                order = self.order()
                publish.assert_not_called()
            self.assertEqual(publish.call_count, 2)
            publish.assert_any_call(self.tenant.schema_name, order.task_events.get(event_type='CALENDAR').pk)
            publish.assert_any_call(self.tenant.schema_name, order.task_events.get(event_type='CACHE').pk)

    def test_stock_loss_catalog_values_known_costs_reports_unknown_and_nets_reversals(self):
        self.movement('-1.5', 'REWORK_LOSS')
        self.item.unit_cost = None
        self.item.save(update_fields=['unit_cost'])
        self.movement('-0.5', 'REWORK_LOSS')
        corrected = self.movement('-1', 'REWORK_LOSS')
        self.movement('1', 'REVERSAL', reversal_of=corrected)
        refresh_billing_catalog(self.tenant.schema_name)
        row = MonthlyStockLossCatalog.objects.get()
        self.assertEqual(row.lost_quantity, Decimal('2'))
        self.assertEqual(row.valued_loss_amount, Decimal('45.75'))
        self.assertEqual(row.unvalued_quantity, Decimal('0.5'))
        self.assertFalse(row.complete_valuation)
        with CaptureQueriesContext(connection) as queries:
            response = self.client.get('/api/analytics/stock-loss/?month=' + row.loss_month.strftime('%Y-%m'))
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data['count'], 1)
        catalog_queries = [q['sql'].upper() for q in queries if 'monthly_stock_loss_catalog' in q['sql']]
        self.assertTrue(catalog_queries)
        self.assertFalse(any('GROUP BY' in q or ' JOIN ' in q for q in catalog_queries))
        self.assertEqual(self.client.post('/api/analytics/stock-loss/', {}, format='json').status_code, 405)
        self.assertEqual(self.client.get('/api/analytics/stock-loss/?inventory_item=bad').status_code, 400)
