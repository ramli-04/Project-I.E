import uuid
from django.contrib.auth.hashers import make_password
from django.db import migrations


EVIDENCE_TABLES = ('api_workflowevent', 'api_casecommandreceipt', 'api_clinicalitem', 'api_caseattachment',
                   'api_caseinspection', 'api_reworkcase', 'api_financeinvoice', 'api_invoicedocument', 'api_creditnote', 'api_creditdocument')


def install_guards(apps, schema_editor):
    connection = schema_editor.connection
    if connection.schema_name == 'public':
        return
    s = schema_editor.quote_name(connection.schema_name)
    # Historical rows are explicitly legacy, rather than inventing inspections or delivery dates.
    Prescription = apps.get_model('api', 'Prescription')
    for order in Prescription.objects.using(connection.alias).all().iterator():
        order.intake_version = 1
        order.qr_nonce = uuid.uuid4()
        order.delivery_service = 'EXPRESS' if order.is_fast_track else 'STANDARD'
        order.base_amount = order.total_price or 0
        order.delivery_pin_hash = make_password(order.delivery_pin or uuid.uuid4().hex)
        order.delivery_pin = ''
        order.save(update_fields=['intake_version', 'qr_nonce', 'delivery_service', 'base_amount', 'delivery_pin_hash', 'delivery_pin'])
    schema_editor.execute(f'''
        INSERT INTO {s}.api_tenantreadversion(name, version) VALUES ('active_orders', 1) ON CONFLICT DO NOTHING;
        CREATE FUNCTION {s}.guard_prescription_version() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF NEW.status IS DISTINCT FROM OLD.status THEN
                IF NEW.state_version <> OLD.state_version + 1 THEN
                    RAISE EXCEPTION 'Status changes require a new audited state version' USING ERRCODE='23514';
                END IF;
            ELSIF NEW.state_version IS DISTINCT FROM OLD.state_version THEN
                RAISE EXCEPTION 'Only status changes may increment state version' USING ERRCODE='23514';
            END IF;
            IF OLD.invoiced_at IS NOT NULL AND (
                NEW.invoiced_at IS DISTINCT FROM OLD.invoiced_at OR NEW.invoiced_amount IS DISTINCT FROM OLD.invoiced_amount
                OR NEW.invoiced_clinic_name IS DISTINCT FROM OLD.invoiced_clinic_name
                OR NEW.total_price IS DISTINCT FROM OLD.total_price OR NEW.partner_clinic_id IS DISTINCT FROM OLD.partner_clinic_id
                OR NEW.billing_stage IS DISTINCT FROM OLD.billing_stage OR NEW.delivery_service IS DISTINCT FROM OLD.delivery_service
                OR NEW.base_amount IS DISTINCT FROM OLD.base_amount OR NEW.express_surcharge IS DISTINCT FROM OLD.express_surcharge) THEN
                RAISE EXCEPTION 'Issued billing snapshots are immutable' USING ERRCODE='55000';
            END IF;
            IF NEW.billing_stage='FACTURE' AND OLD.billing_stage<>'FACTURE' AND NOT EXISTS(
                SELECT 1 FROM {s}.api_statementline l JOIN {s}.api_financeinvoice i ON i.period_id=l.period_id
                WHERE l.prescription_id=NEW.id AND NOT l.contested AND NOT l.excluded) THEN
                RAISE EXCEPTION 'Invoicing requires an issued monthly statement' USING ERRCODE='23514';
            END IF;
            RETURN NEW;
        END;
        $$;
        CREATE TRIGGER prescription_version_guard BEFORE UPDATE ON {s}.api_prescription
            FOR EACH ROW EXECUTE FUNCTION {s}.guard_prescription_version();

        CREATE FUNCTION {s}.require_prescription_history() RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE prior_status text;
        BEGIN
            IF TG_OP='UPDATE' AND NEW.status IS NOT DISTINCT FROM OLD.status THEN RETURN NEW; END IF;
            prior_status := CASE WHEN TG_OP='INSERT' THEN '' ELSE OLD.status END;
            IF NOT EXISTS (SELECT 1 FROM {s}.api_prescriptionhistory
                WHERE prescription_id=NEW.id AND source_version=NEW.state_version
                  AND previous_status=prior_status AND new_status=NEW.status) THEN
                RAISE EXCEPTION 'Every source status version requires matching immutable history' USING ERRCODE='23514';
            END IF;
            RETURN NEW;
        END;
        $$;
        CREATE CONSTRAINT TRIGGER prescription_history_required AFTER INSERT OR UPDATE ON {s}.api_prescription
            DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION {s}.require_prescription_history();

        CREATE FUNCTION {s}.advance_read_version() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            INSERT INTO {s}.api_tenantreadversion(name,version) VALUES ('active_orders',1)
                ON CONFLICT(name) DO UPDATE SET version={s}.api_tenantreadversion.version+1;
            RETURN NEW;
        END;
        $$;
        CREATE TRIGGER prescription_read_version AFTER INSERT OR UPDATE OR DELETE ON {s}.api_prescription
            FOR EACH STATEMENT EXECUTE FUNCTION {s}.advance_read_version();

        CREATE FUNCTION {s}.guard_closed_billing() RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE closed timestamptz; period_key uuid;
        BEGIN
            IF TG_TABLE_NAME='api_billingperiod' THEN
                IF TG_OP='DELETE' OR OLD.closed_at IS NOT NULL THEN
                    RAISE EXCEPTION 'Closed periods cannot be changed or deleted' USING ERRCODE='55000';
                END IF;
            ELSE
                period_key := CASE WHEN TG_OP='DELETE' THEN OLD.period_id ELSE NEW.period_id END;
                SELECT closed_at INTO closed FROM {s}.api_billingperiod WHERE id=period_key FOR UPDATE;
                IF closed IS NOT NULL OR TG_OP='DELETE' THEN
                    RAISE EXCEPTION 'Closed statements are immutable; use credit notes' USING ERRCODE='55000';
                END IF;
            END IF;
            IF TG_OP='DELETE' THEN RETURN OLD; END IF;
            RETURN NEW;
        END;
        $$;
        CREATE TRIGGER billing_period_guard BEFORE UPDATE OR DELETE ON {s}.api_billingperiod
            FOR EACH ROW EXECUTE FUNCTION {s}.guard_closed_billing();
        CREATE TRIGGER statement_line_guard BEFORE INSERT OR UPDATE OR DELETE ON {s}.api_statementline
            FOR EACH ROW EXECUTE FUNCTION {s}.guard_closed_billing();

        CREATE OR REPLACE FUNCTION {s}.apply_inventory_movement() RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE item RECORD; source RECORD; offset_quantity numeric;
        BEGIN
            SELECT * INTO STRICT item FROM {s}.api_inventory WHERE id=NEW.inventory_item_id FOR UPDATE;
            IF NEW.quantity_changed::text IN ('NaN','Infinity','-Infinity') THEN
                RAISE EXCEPTION 'Movement must be finite' USING ERRCODE='23514'; END IF;
            IF NEW.transaction_type='USAGE' AND NEW.prescription_id IS NULL THEN
                RAISE EXCEPTION 'Usage requires a prescription' USING ERRCODE='23514'; END IF;
            IF NEW.transaction_type='REVERSAL' AND NEW.reversal_of_id IS NULL THEN
                RAISE EXCEPTION 'Reversal requires a source' USING ERRCODE='23514'; END IF;
            IF NEW.transaction_type='LOSS_OFFSET' AND NEW.source_usage_id IS NULL THEN
                RAISE EXCEPTION 'Loss offset requires source consumption' USING ERRCODE='23514'; END IF;
            IF coalesce(NEW.reversal_of_id,NEW.reclassifies_id,NEW.source_usage_id) IS NOT NULL THEN
                SELECT * INTO STRICT source FROM {s}.api_inventorytransaction
                    WHERE id=coalesce(NEW.reversal_of_id,NEW.reclassifies_id,NEW.source_usage_id);
                IF source.inventory_item_id<>NEW.inventory_item_id OR NEW.prescription_id IS DISTINCT FROM source.prescription_id
                   OR NEW.unit_snapshot<>source.unit_snapshot OR NEW.unit_cost_snapshot IS DISTINCT FROM source.unit_cost_snapshot THEN
                    RAISE EXCEPTION 'Invalid correction snapshot' USING ERRCODE='23514'; END IF;
                IF NEW.reversal_of_id IS NOT NULL AND (NEW.transaction_type<>'REVERSAL'
                    OR source.transaction_type IN ('OPENING','REVERSAL','LOSS_OFFSET') OR source.source_history_id IS NOT NULL
                    OR NEW.quantity_changed<>-source.quantity_changed
                    OR EXISTS(SELECT 1 FROM {s}.api_inventorytransaction WHERE reclassifies_id=source.id)) THEN
                    RAISE EXCEPTION 'Invalid reversal' USING ERRCODE='23514'; END IF;
                IF NEW.source_usage_id IS NOT NULL AND (NEW.transaction_type<>'LOSS_OFFSET' OR source.transaction_type<>'USAGE'
                    OR NEW.quantity_changed<=0 OR NEW.quantity_changed > -source.quantity_changed OR NEW.source_history_id IS NULL) THEN
                    RAISE EXCEPTION 'Invalid partial-loss offset' USING ERRCODE='23514'; END IF;
                IF NEW.reclassifies_id IS NOT NULL THEN
                    SELECT quantity_changed INTO offset_quantity FROM {s}.api_inventorytransaction
                        WHERE (reversal_of_id=source.id OR source_usage_id=source.id) AND source_history_id=NEW.source_history_id;
                    IF NEW.transaction_type<>'REWORK_LOSS' OR source.transaction_type<>'USAGE'
                       OR NEW.quantity_changed<source.quantity_changed OR NEW.quantity_changed>=0
                       OR offset_quantity IS NULL OR offset_quantity<>-NEW.quantity_changed THEN
                        RAISE EXCEPTION 'Loss requires a matching reclassification offset' USING ERRCODE='23514'; END IF;
                END IF;
            ELSIF NEW.unit_snapshot<>item.unit OR NEW.unit_cost_snapshot IS DISTINCT FROM item.unit_cost THEN
                RAISE EXCEPTION 'Invalid inventory snapshot' USING ERRCODE='23514';
            END IF;
            NEW.balance_after:=item.quantity+NEW.quantity_changed;
            IF NEW.balance_after<0 THEN RAISE EXCEPTION 'Insufficient inventory' USING ERRCODE='23514'; END IF;
            UPDATE {s}.api_inventory SET quantity=NEW.balance_after WHERE id=NEW.inventory_item_id;
            RETURN NEW;
        END;
        $$;
    ''')
    for table in EVIDENCE_TABLES:
        schema_editor.execute(f'''CREATE TRIGGER evidence_immutable BEFORE UPDATE OR DELETE OR TRUNCATE ON {s}.{table}
            FOR EACH STATEMENT EXECUTE FUNCTION {s}.reject_business_ledger_mutation();''')


def uninstall_guards(apps, schema_editor):
    if schema_editor.connection.schema_name == 'public':
        return
    s = schema_editor.quote_name(schema_editor.connection.schema_name)
    for table in EVIDENCE_TABLES:
        schema_editor.execute(f'DROP TRIGGER IF EXISTS evidence_immutable ON {s}.{table}')
    for table, name in [('api_prescription','prescription_version_guard'),('api_prescription','prescription_history_required'),
                        ('api_prescription','prescription_read_version'),('api_billingperiod','billing_period_guard'),
                        ('api_statementline','statement_line_guard')]:
        schema_editor.execute(f'DROP TRIGGER IF EXISTS {name} ON {s}.{table}')
    for name in ('guard_prescription_version','require_prescription_history','advance_read_version','guard_closed_billing'):
        schema_editor.execute(f'DROP FUNCTION IF EXISTS {s}.{name}()')
    from importlib import import_module
    original = import_module('api.migrations.0019_inventory_integrity_and_opening_balances')
    original.unprotect_ledger(apps, schema_editor)
    original.protect_ledger(apps, schema_editor)


class Migration(migrations.Migration):
    dependencies = [('api', '0021_bpmn_workflow_and_accounting')]
    operations = [migrations.RunPython(install_guards, uninstall_guards)]
