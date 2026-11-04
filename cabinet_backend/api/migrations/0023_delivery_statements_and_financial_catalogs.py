from django.db import migrations


def create_catalogs(apps, schema_editor):
    if schema_editor.connection.schema_name == 'public':
        return
    s = schema_editor.quote_name(schema_editor.connection.schema_name)
    schema_editor.execute(f'''
        CREATE MATERIALIZED VIEW {s}.monthly_statement_catalog AS
        WITH disputes AS (
            SELECT prescription_id, bool_or(status='OPEN') AS contested
            FROM {s}.api_billingdispute GROUP BY prescription_id
        )
        SELECT p.id AS prescription_id, p.partner_clinic_id AS clinic_id,
               date_trunc('month',p.delivered_at AT TIME ZONE 'Africa/Casablanca')::date AS closing_month,
               p.patient_ref, p.delivered_at, coalesce(l.base_amount,p.base_amount) AS base_amount,
               coalesce(l.express_surcharge,p.express_surcharge) AS express_surcharge,
               coalesce(l.base_amount+l.express_surcharge,p.total_price) AS total_amount,
               (coalesce(l.contested,false) OR coalesce(d.contested,false)) AS contested,
               coalesce(l.excluded,false) AS excluded, (p.invoiced_at IS NOT NULL) AS billed,
               CURRENT_TIMESTAMP AS refreshed_at
        FROM {s}.api_prescription p
        LEFT JOIN {s}.api_statementline l ON l.prescription_id=p.id
        LEFT JOIN disputes d ON d.prescription_id=p.id
        WHERE p.delivered_at IS NOT NULL AND p.partner_clinic_id IS NOT NULL AND p.total_price IS NOT NULL WITH DATA;
        CREATE UNIQUE INDEX monthly_statement_catalog_pk ON {s}.monthly_statement_catalog(prescription_id);
        CREATE INDEX monthly_statement_catalog_month_clinic ON {s}.monthly_statement_catalog(closing_month,clinic_id);

        CREATE MATERIALIZED VIEW {s}.monthly_financial_catalog AS
        WITH credits AS (
            SELECT invoice_id,sum(amount)::numeric(16,2) AS credited_amount FROM {s}.api_creditnote GROUP BY invoice_id
        )
        SELECT i.id AS invoice_id,i.number,p.clinic_id,i.clinic_name,p.month AS closing_month,
               i.base_amount,i.express_surcharge,i.total_amount AS gross_amount,
               coalesce(c.credited_amount,0)::numeric(16,2) AS credited_amount,
               (i.total_amount-coalesce(c.credited_amount,0))::numeric(16,2) AS net_amount,
               CURRENT_TIMESTAMP AS refreshed_at
        FROM {s}.api_financeinvoice i JOIN {s}.api_billingperiod p ON p.id=i.period_id
        LEFT JOIN credits c ON c.invoice_id=i.id WITH DATA;
        CREATE UNIQUE INDEX monthly_financial_catalog_pk ON {s}.monthly_financial_catalog(invoice_id);
        CREATE INDEX monthly_financial_catalog_month_clinic ON {s}.monthly_financial_catalog(closing_month,clinic_id);
    ''')


def drop_catalogs(apps, schema_editor):
    if schema_editor.connection.schema_name != 'public':
        s = schema_editor.quote_name(schema_editor.connection.schema_name)
        schema_editor.execute(f'DROP MATERIALIZED VIEW IF EXISTS {s}.monthly_financial_catalog; DROP MATERIALIZED VIEW IF EXISTS {s}.monthly_statement_catalog;')


class Migration(migrations.Migration):
    dependencies = [('api', '0022_enforce_workflow_evidence_and_read_versions')]
    operations = [migrations.RunPython(create_catalogs, drop_catalogs)]
