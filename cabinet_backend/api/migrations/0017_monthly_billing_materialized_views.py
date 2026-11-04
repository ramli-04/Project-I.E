from django.db import migrations


def create_catalogs(apps, schema_editor):
    connection = schema_editor.connection
    if connection.schema_name == 'public':
        return
    schema = schema_editor.quote_name(connection.schema_name)
    schema_editor.execute(f'''
        CREATE MATERIALIZED VIEW {schema}.monthly_billing_catalog AS
        WITH history AS (
            SELECT prescription_id,
                   count(*)::bigint AS audit_event_count,
                   count(*) FILTER (WHERE previous_status <> '')::bigint AS status_transition_count,
                   max(created_at) AS last_status_change_at
            FROM {schema}.api_prescriptionhistory
            GROUP BY prescription_id
        )
        SELECT p.id AS prescription_id,
               p.partner_clinic_id,
               coalesce(nullif(p.invoiced_clinic_name, ''), c.name, p.dentist_name) AS clinic_name,
               p.patient_ref, p.status, p.billing_stage, p.created_at, p.invoiced_at,
               date_trunc('month', p.invoiced_at AT TIME ZONE 'Africa/Casablanca')::date AS billing_month,
               p.invoiced_amount AS billed_amount,
               'MAD'::varchar(3) AS currency,
               coalesce(h.audit_event_count, 0)::bigint AS audit_event_count,
               coalesce(h.status_transition_count, 0)::bigint AS status_transition_count,
               h.last_status_change_at,
               (p.billing_stage = 'FACTURE' AND p.invoiced_at IS NULL) AS legacy_invoice_without_date,
               CURRENT_TIMESTAMP AS refreshed_at
        FROM {schema}.api_prescription p
        LEFT JOIN {schema}.api_partnerclinic c ON c.id = p.partner_clinic_id
        LEFT JOIN history h ON h.prescription_id = p.id
        WITH DATA;

        CREATE UNIQUE INDEX monthly_billing_catalog_pk
            ON {schema}.monthly_billing_catalog (prescription_id);
        CREATE INDEX monthly_billing_catalog_month_clinic
            ON {schema}.monthly_billing_catalog (billing_month, partner_clinic_id);
        CREATE INDEX monthly_billing_catalog_created
            ON {schema}.monthly_billing_catalog (created_at DESC, prescription_id);

        CREATE MATERIALIZED VIEW {schema}.monthly_billing_summary AS
        WITH totals AS (
            SELECT billing_month, partner_clinic_id,
                   count(*)::bigint AS invoice_count,
                   sum(billed_amount)::numeric(20, 2) AS invoiced_total,
                   count(*) FILTER (WHERE status = 'LIVRE')::bigint AS delivered_count,
                   count(*) FILTER (WHERE status <> 'LIVRE')::bigint AS in_progress_count,
                   sum(status_transition_count)::bigint AS status_transition_count,
                   count(*) FILTER (WHERE audit_event_count = 0)::bigint AS missing_audit_count
            FROM {schema}.monthly_billing_catalog
            WHERE billing_month IS NOT NULL AND billed_amount IS NOT NULL
            GROUP BY billing_month, partner_clinic_id
        )
        SELECT to_char(t.billing_month, 'YYYY-MM') || ':' ||
                   coalesce(t.partner_clinic_id::text, 'unassigned') AS catalog_key,
               t.billing_month, t.partner_clinic_id,
               coalesce(c.name, 'Unassigned clinic') AS clinic_name,
               t.invoice_count, t.invoiced_total, t.delivered_count, t.in_progress_count,
               t.status_transition_count, t.missing_audit_count,
               'MAD'::varchar(3) AS currency,
               CURRENT_TIMESTAMP AS refreshed_at
        FROM totals t
        LEFT JOIN {schema}.api_partnerclinic c ON c.id = t.partner_clinic_id
        WITH DATA;

        CREATE UNIQUE INDEX monthly_billing_summary_pk
            ON {schema}.monthly_billing_summary (catalog_key);
        CREATE INDEX monthly_billing_summary_month_clinic
            ON {schema}.monthly_billing_summary (billing_month, partner_clinic_id);

        INSERT INTO {schema}.api_analyticsrefreshstate
            (pipeline, last_attempt_at, last_success_at, last_error, undated_invoice_count)
        SELECT 'monthly_billing_catalog', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, '',
               count(*) FILTER (WHERE legacy_invoice_without_date)
        FROM {schema}.monthly_billing_catalog;
    ''')


def drop_catalogs(apps, schema_editor):
    if schema_editor.connection.schema_name == 'public':
        return
    schema = schema_editor.quote_name(schema_editor.connection.schema_name)
    # DROP MATERIALIZED VIEW also removes its indexes. Drop dependent summary first.
    schema_editor.execute(f'''
        DROP MATERIALIZED VIEW IF EXISTS {schema}.monthly_billing_summary;
        DROP MATERIALIZED VIEW IF EXISTS {schema}.monthly_billing_catalog;
        DELETE FROM {schema}.api_analyticsrefreshstate WHERE pipeline = 'monthly_billing_catalog';
    ''')


class Migration(migrations.Migration):
    dependencies = [
        ('api', '0016_billing_catalog_foundation'),
        ('customers', '0003_tenant_activity'),
    ]

    operations = [migrations.RunPython(create_catalogs, drop_catalogs)]
