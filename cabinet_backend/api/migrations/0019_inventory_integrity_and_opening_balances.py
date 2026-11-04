import uuid

from django.db import migrations


def seed_balances_and_events(apps, schema_editor):
    connection = schema_editor.connection
    if connection.schema_name == 'public':
        return
    Inventory = apps.get_model('api', 'Inventory')
    Ledger = apps.get_model('api', 'InventoryTransaction')
    Prescription = apps.get_model('api', 'Prescription')
    Outbox = apps.get_model('api', 'TaskOutbox')
    using = connection.alias
    for item in Inventory.objects.using(using).all().iterator():
        Ledger.objects.using(using).get_or_create(
            inventory_item_id=item.pk, transaction_type='OPENING', defaults={
                'quantity_changed': item.quantity, 'balance_after': item.quantity,
                'unit_snapshot': item.unit, 'material_name_snapshot': item.material_name,
                'unit_cost_snapshot': item.unit_cost, 'changed_by': 'migration:observed-opening',
                'notes': 'Observed balance at ledger adoption; earlier consumption and cost history are unknown.',
                'idempotency_key': uuid.uuid5(uuid.NAMESPACE_URL, f'{connection.schema_name}:inventory:{item.pk}:opening'),
            },
        )
    for order in Prescription.objects.using(using).all().iterator():
        if order.status != 'LIVRE':
            Outbox.objects.using(using).get_or_create(event_key=f'calendar:{order.pk}', defaults={
                'event_type': 'CALENDAR', 'prescription_id': order.pk,
            })
        if order.invoiced_at is not None:
            Outbox.objects.using(using).get_or_create(event_key=f'invoice:{order.pk}', defaults={
                'event_type': 'INVOICE', 'prescription_id': order.pk,
            })


def protect_ledger(apps, schema_editor):
    if schema_editor.connection.schema_name == 'public':
        return
    s = schema_editor.quote_name(schema_editor.connection.schema_name)
    schema_editor.execute(f'''
        CREATE FUNCTION {s}.reject_business_ledger_mutation() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'Business ledger is append-only' USING ERRCODE = '55000';
        END;
        $$;
        CREATE FUNCTION {s}.apply_inventory_movement() RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE item RECORD; source RECORD;
        BEGIN
            SELECT * INTO STRICT item FROM {s}.api_inventory WHERE id=NEW.inventory_item_id FOR UPDATE;
            IF NEW.quantity_changed::text IN ('NaN', 'Infinity', '-Infinity') THEN
                RAISE EXCEPTION 'Movement must be finite' USING ERRCODE = '23514';
            END IF;
            IF NEW.transaction_type='USAGE' AND NEW.prescription_id IS NULL THEN
                RAISE EXCEPTION 'Usage requires a prescription' USING ERRCODE = '23514';
            END IF;
            IF NEW.transaction_type='REVERSAL' AND NEW.reversal_of_id IS NULL THEN
                RAISE EXCEPTION 'Reversal requires a source' USING ERRCODE = '23514';
            END IF;
            IF NEW.reversal_of_id IS NOT NULL OR NEW.reclassifies_id IS NOT NULL THEN
                SELECT * INTO STRICT source FROM {s}.api_inventorytransaction
                    WHERE id=coalesce(NEW.reversal_of_id, NEW.reclassifies_id);
                IF source.inventory_item_id <> NEW.inventory_item_id
                   OR NEW.prescription_id IS DISTINCT FROM source.prescription_id
                   OR NEW.unit_snapshot <> source.unit_snapshot
                   OR NEW.unit_cost_snapshot IS DISTINCT FROM source.unit_cost_snapshot THEN
                    RAISE EXCEPTION 'Invalid correction snapshot' USING ERRCODE = '23514';
                END IF;
                IF NEW.reversal_of_id IS NOT NULL AND (
                    NEW.transaction_type <> 'REVERSAL' OR source.transaction_type IN ('OPENING','REVERSAL')
                    OR source.source_history_id IS NOT NULL
                    OR NEW.quantity_changed <> -source.quantity_changed) THEN
                    RAISE EXCEPTION 'Invalid reversal' USING ERRCODE = '23514';
                END IF;
                IF NEW.reclassifies_id IS NOT NULL AND (
                    NEW.transaction_type <> 'REWORK_LOSS' OR source.transaction_type <> 'USAGE'
                    OR NEW.quantity_changed <> source.quantity_changed
                    OR NOT EXISTS (SELECT 1 FROM {s}.api_inventorytransaction WHERE reversal_of_id=source.id)) THEN
                    RAISE EXCEPTION 'Reclassification requires consumed material and its reversal' USING ERRCODE = '23514';
                END IF;
            ELSE
                IF NEW.unit_snapshot <> item.unit OR NEW.unit_cost_snapshot IS DISTINCT FROM item.unit_cost THEN
                    RAISE EXCEPTION 'Invalid inventory snapshot' USING ERRCODE = '23514';
                END IF;
            END IF;
            NEW.balance_after := item.quantity + NEW.quantity_changed;
            IF NEW.balance_after < 0 THEN
                RAISE EXCEPTION 'Insufficient inventory' USING ERRCODE = '23514';
            END IF;
            UPDATE {s}.api_inventory SET quantity=NEW.balance_after WHERE id=NEW.inventory_item_id;
            RETURN NEW;
        END;
        $$;
        CREATE TRIGGER inventory_apply_movement BEFORE INSERT ON {s}.api_inventorytransaction
            FOR EACH ROW EXECUTE FUNCTION {s}.apply_inventory_movement();

        CREATE FUNCTION {s}.guard_inventory_balance() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF TG_OP='INSERT' AND NEW.quantity <> 0 THEN
                RAISE EXCEPTION 'Create inventory with zero balance, then append an opening entry' USING ERRCODE = '23514';
            ELSIF TG_OP='UPDATE' THEN
                IF NEW.quantity IS DISTINCT FROM OLD.quantity AND pg_trigger_depth() <= 1 THEN
                    RAISE EXCEPTION 'Use inventory ledger movements to change balances' USING ERRCODE = '55000';
                END IF;
                IF NEW.unit IS DISTINCT FROM OLD.unit THEN
                    RAISE EXCEPTION 'Inventory units are immutable after creation' USING ERRCODE = '55000';
                END IF;
            END IF;
            RETURN NEW;
        END;
        $$;
        CREATE TRIGGER inventory_balance_guard BEFORE INSERT OR UPDATE ON {s}.api_inventory
            FOR EACH ROW EXECUTE FUNCTION {s}.guard_inventory_balance();
    ''')
    for table in ('api_inventorytransaction', 'api_invoiceartifact', 'api_invoicedispatchlog'):
        schema_editor.execute(f'''
            CREATE TRIGGER business_ledger_immutable BEFORE UPDATE OR DELETE OR TRUNCATE ON {s}.{table}
                FOR EACH STATEMENT EXECUTE FUNCTION {s}.reject_business_ledger_mutation();
        ''')


def unprotect_ledger(apps, schema_editor):
    if schema_editor.connection.schema_name == 'public':
        return
    s = schema_editor.quote_name(schema_editor.connection.schema_name)
    for table in ('api_inventorytransaction', 'api_invoiceartifact', 'api_invoicedispatchlog'):
        schema_editor.execute(f'DROP TRIGGER IF EXISTS business_ledger_immutable ON {s}.{table}')
    schema_editor.execute(f'''
        DROP TRIGGER IF EXISTS inventory_balance_guard ON {s}.api_inventory;
        DROP TRIGGER IF EXISTS inventory_apply_movement ON {s}.api_inventorytransaction;
        DROP FUNCTION IF EXISTS {s}.guard_inventory_balance();
        DROP FUNCTION IF EXISTS {s}.apply_inventory_movement();
        DROP FUNCTION IF EXISTS {s}.reject_business_ledger_mutation();
    ''')


class Migration(migrations.Migration):
    dependencies = [('api', '0018_inventory_ledger_and_background_events')]
    operations = [
        migrations.RunPython(seed_balances_and_events, migrations.RunPython.noop),
        migrations.RunPython(protect_ledger, unprotect_ledger),
    ]
