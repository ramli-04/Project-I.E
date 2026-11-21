# Billing analytics

Each laboratory has three materialized views:

- `monthly_billing_catalog`: one row per prescription. History is aggregated before joining, preventing duplicated amounts.
- `monthly_billing_summary`: one row per invoiced calendar month and partner clinic, including an explicit unassigned-clinic group.
- `monthly_stock_loss_catalog`: one row per loss month, inventory item and unit; see [inventory workflow](INVENTORY_WORKFLOW.md).

Billing views contain order-level invoiced totals in MAD, rather than invoice line items, tax accounting or payment reconciliation. Stock losses use a separate inventory ledger and catalog.

## Invoice data

`Prescription.partner_clinic` links directly to the tenant's `PartnerClinic`. Existing prescriptions remain unassigned; names and unrelated user/account IDs are not used to infer links.

Moving an order to `FACTURE` captures server-generated `invoiced_at`, `invoiced_amount`, and `invoiced_clinic_name`. Issued billing amount, date, stage, and clinic linkage are locked. Later operational changes do not move invoices between months. Month boundaries use `Africa/Casablanca`.

Pre-existing `FACTURE` records without dates are flagged as `legacy_invoice_without_date` in the detail catalog and excluded from monthly totals. Their number is reported in response metadata. No dates or historical audit events are invented. Reconciliation requires verified historical billing dates and amounts.

Use the standard prescription API to supply `partner_clinic` before invoicing. Do not join `PlatformAccount` IDs to Django Auth user IDs.

## Read endpoints

Laboratory authentication and tenant host routing are required:

```text
GET /api/analytics/billing-catalog/
GET /api/analytics/billing-catalog/<prescription UUID>/
GET /api/analytics/monthly-billing/
GET /api/analytics/monthly-billing/?month=2026-11&clinic=1&page_size=50
GET /api/analytics/monthly-billing/?clinic=unassigned
```

Responses are paginated (50 default, 200 maximum). Analytics queries read materialized views without request-time source-table joins or grouping. Tenant middleware and authentication still perform their normal checks.

List responses include last successful refresh, last attempt, failure/staleness flags, unknown-date invoice count, and currency. A snapshot becomes stale after 20 minutes; normal scheduling runs every 15 minutes. Queries remain available against the last successful snapshot if a refresh fails.

## Refresh pipeline

One Celery Beat scheduler dispatches `api.tasks.refresh_monthly_billing_catalog_task` every 15 minutes. It reads active tenants from `public` and dispatches one task per schema. Each task resolves the tenant, enters `tenant_context`, acquires a tenant-specific PostgreSQL advisory lock, and refreshes all three views concurrently in one transaction. Schema identifiers are quoted. SQL statement and lock timeouts bound refresh work. Database failures are logged, recorded per tenant, and retried up to three times.

`Client.is_active=False` excludes a lab from future refreshes and blocks its operational API access. Inactive labs also disappear from the login selector. Existing data is preserved.

After deploying migrations, rebuild and recreate worker and Beat:

```powershell
.\venv\Scripts\python.exe cabinet_backend/manage.py migrate_schemas --noinput
docker compose up -d --build celery_worker celery_beat
```

Run exactly one Beat instance. Its schedule file lives in a persistent, worker-owned Docker volume.

Immediate dispatch:

```powershell
docker compose exec -T celery_worker celery -A cabinet_backend.celery:app call api.tasks.refresh_monthly_billing_catalog_task
```

Materialized views initially populate during tenant migration; newly created labs get all three views automatically. Rollback drops the stock-loss catalog and billing summary before the detail billing catalog and removes their indexes with them.

Stock-loss analytics use the inventory movement ledger with explicit consumption, compensating rework entries and immutable cost snapshots. Unknown historical consumption and costs are not inferred.
