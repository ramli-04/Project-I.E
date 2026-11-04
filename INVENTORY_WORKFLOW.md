# Inventory ledger and BPMN tasks

Operational tables, audit entries, outbox events, mock invoices and stock-loss catalogs live inside each laboratory schema. Public schema holds authentication and laboratory records only. Worker entry points resolve an active laboratory before entering `tenant_context`; public, missing and inactive laboratories are rejected.

## Stock commands

`Inventory.quantity` is the current balance. The project has no `Inventory.stock` field. Quantities and thresholds now use `Decimal(20,6)`, preserving fractional discs/grams/units. Existing values that cannot convert exactly must be corrected before migration; migration refuses silent rounding.

Creating inventory records its opening balance in the ledger. Migration records existing balances as observed openings, without inventing earlier usage or historical costs. Thereafter only a new movement changes the balance. The movement insert and balance update commit or roll back together; row locks prevent concurrent overspending. PostgreSQL triggers reject updates, deletes and truncations of journal entries, as well as direct balance/unit changes. Inventory metadata, alert threshold and reference unit cost remain editable.

Authenticated laboratory endpoint:

```http
POST /api/inventory-transactions/
Content-Type: application/json

{
  "inventory_item": 1,
  "prescription": "<prescription UUID>",
  "quantity_changed": "-0.500000",
  "transaction_type": "USAGE",
  "notes": "Actual material consumed for this production attempt",
  "idempotency_key": "<new UUID for this command>"
}
```

- `USAGE`: negative quantity, prescription required, permitted during production.
- `REWORK_LOSS`: negative quantity for explicitly measured additional scrap; prescription optional.
- `RESTOCK`: positive quantity.
- `REVERSAL`: supply `reversal_of` with the original movement UUID and its `inventory_item`; quantity and prescription derive from that source. Each source can be reversed once. Opening entries and automatic rework classifications cannot be manually reversed through this API.
- `OPENING`: server-managed only.

Reuse the same idempotency UUID when retrying the same payload. A different payload using that UUID returns an error. Idempotency is local to each tenant. No endpoint permits journal updates/deletes. Use `GET /api/inventory-transactions/?inventory_item=1` or `?prescription=<UUID>` for paginated entries.

The Stock configuration form permits initial quantity on creation; existing quantity/unit are locked and deletion is disabled. Stock movement entry currently uses the API above; a dedicated movement-entry screen is not included in this backend phase. Legacy `StockItem`/`/api/stock/` remains a separate older resource; this ledger applies to `Inventory`/`/api/inventory/` only.

## Rework without double deduction

Materials must be recorded as actual `USAGE` against the prescription and its server-managed `production_attempt`. The system never guesses material allocations from free-text material names.

During material-consuming production or quality control, laboratory staff may PATCH prescription status to `A_REFAIRE`, or `RECOULER` for conventional production, with a non-empty `action_notes` reason. At least one unreversed usage in the current attempt is required. Status, immutable history, loss classification and attempt increment are one atomic operation.

For each usage already deducted, the rework signal adds a compensating `REVERSAL` and a matching `REWORK_LOSS` referencing the immutable history event. Example: 10 discs → usage -2 = 8; rework +2/-2 = 8; replacement fabrication usage -2 = 6. Rework records the loss without charging the same material twice. Event/source references and unique constraints prevent duplicate classification. Quality validation resets and `production_attempt` increments. This initial implementation classifies all unreversed usage in the failed attempt; partial salvage requires an explicit future policy.

`A_REFAIRE` resumes at CAO for digital routes or working-model preparation for conventional production. `RECOULER` resumes at conventional modelage. Existing forward-only workflow checkpoints remain enforced for normal transitions.

## Calendar and mock invoices

`calculate_automatic_calendar_task(tenant_schema_name, prescription_id)` calculates `automatic_deadline` from the local creation date in `Africa/Casablanca`: J+4 standard, J+2 express, **calendar days**. It also records `deadline_calculated_at`. It preserves the manually confirmed `delivery_date`. Creation and priority changes generate durable calculation events; retries recompute deterministically from current priority. Holidays, working days, capacity scheduling and automatic manual-date confirmation are not implemented.

The first confirmed `FACTURE` transition generates an invoice event. `generate_invoice_pdf_task(tenant_schema_name, prescription_id)` requires immutable issued billing snapshots, then creates one immutable `InvoiceArtifact` with `MOCK_READY` and a `mock://<schema>/invoices/<UUID>` reference. Two immutable dispatch logs use `SIMULATED_NOT_SENT` for EMAIL and WHATSAPP. Duplicate task delivery creates no duplicate artifact/logs. **No PDF file is produced and no email/WhatsApp message is sent.**

## Durable event delivery

Source writes persist `TaskOutbox` in the same PostgreSQL transaction. `transaction.on_commit` attempts publication with bounded Redis connection/socket timeouts. Broker failure is logged and retained in the outbox, without undoing an already committed source request. Beat dispatches pending-event recovery every 60 seconds, one task per active tenant, with batches of 100 events. Published events without completion become eligible again after five minutes. Consumer effects and `processed_at` commit together. This is at-least-once delivery with idempotent consumers.

Migration queues calendar calculations for existing active prescriptions and mock invoice generation only for invoices with verified issuance timestamps. Undated legacy invoices remain excluded. Publication failures appear in outbox `attempts`, `last_error`, and `next_attempt_at`; consumer failures appear in Celery logs and remain eligible for recovery until processed.

## Stock-loss analytics

`monthly_stock_loss_catalog` aggregates monthly loss per inventory item and unit. Quantities with different units are never combined. Each movement freezes its reference unit cost; later price changes do not revalue old losses. Known costs contribute to `valued_loss_amount`; missing costs remain explicit through `unvalued_quantity` and `complete_valuation`. This is reference-cost valuation, not FIFO or weighted-average accounting. Reversed manual losses are netted out of their original loss month.

```text
GET /api/analytics/stock-loss/?month=2026-11&inventory_item=1&page_size=50
```

The existing 15-minute billing refresh now refreshes all three catalogs concurrently in one transaction. Read requests query the precomputed catalog, with no runtime source-table joins or GROUP BY. Tenant permissions, bounded pagination and freshness metadata match billing analytics.

## Deployment and checks

From the project root, with PostgreSQL and Docker Desktop running:

```powershell
.\venv\Scripts\python.exe cabinet_backend/manage.py migrate_schemas --noinput
docker compose up -d --build redis celery_worker celery_beat
docker compose exec -T celery_worker celery -A cabinet_backend.celery:app inspect registered
docker compose logs --tail=60 celery_worker celery_beat
```

Keep one Beat instance. Keep `.env` uncommitted. No additional Python package is required. Journal history is intentionally protected; do not use `flush`, direct balance edits or destructive schema rollback to reconcile stock. Correct stock with explicit compensating entries.
