from django.db import migrations


def create_catalog(apps, schema_editor):
    if schema_editor.connection.schema_name == 'public':
        return
    s = schema_editor.quote_name(schema_editor.connection.schema_name)
    schema_editor.execute(f'''
        CREATE MATERIALIZED VIEW {s}.monthly_stock_loss_catalog AS
        WITH losses AS (
            SELECT date_trunc('month', l.created_at AT TIME ZONE 'Africa/Casablanca')::date AS loss_month,
                   l.inventory_item_id, l.unit_snapshot AS unit, l.unit_cost_snapshot,
                   -(l.quantity_changed + coalesce(r.quantity_changed, 0)) AS net_quantity
            FROM {s}.api_inventorytransaction l
            LEFT JOIN {s}.api_inventorytransaction r ON r.reversal_of_id=l.id
            WHERE l.transaction_type='REWORK_LOSS'
        ), totals AS (
            SELECT loss_month, inventory_item_id, unit,
                   sum(net_quantity)::numeric(28,6) AS lost_quantity,
                   sum(net_quantity * unit_cost_snapshot)::numeric(44,12) AS valued_loss_amount,
                   coalesce(sum(net_quantity) FILTER (WHERE unit_cost_snapshot IS NULL), 0)::numeric(28,6) AS unvalued_quantity
            FROM losses WHERE net_quantity > 0
            GROUP BY loss_month, inventory_item_id, unit
        )
        SELECT concat(t.loss_month, ':', t.inventory_item_id, ':', t.unit)::varchar(100) AS catalog_key,
               t.loss_month, t.inventory_item_id, i.material_name, t.unit, t.lost_quantity,
               t.valued_loss_amount, t.unvalued_quantity, (t.unvalued_quantity=0) AS complete_valuation,
               'MAD'::varchar(3) AS currency, CURRENT_TIMESTAMP AS refreshed_at
        FROM totals t JOIN {s}.api_inventory i ON i.id=t.inventory_item_id WITH DATA;
        CREATE UNIQUE INDEX monthly_stock_loss_catalog_pk ON {s}.monthly_stock_loss_catalog(catalog_key);
        CREATE INDEX monthly_stock_loss_catalog_month_item ON {s}.monthly_stock_loss_catalog(loss_month, inventory_item_id);
    ''')


def drop_catalog(apps, schema_editor):
    if schema_editor.connection.schema_name != 'public':
        s = schema_editor.quote_name(schema_editor.connection.schema_name)
        schema_editor.execute(f'DROP MATERIALIZED VIEW IF EXISTS {s}.monthly_stock_loss_catalog')


class Migration(migrations.Migration):
    dependencies = [('api', '0019_inventory_integrity_and_opening_balances')]
    operations = [migrations.RunPython(create_catalog, drop_catalog)]
