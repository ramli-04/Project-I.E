# Inventory, measured rework and durable tasks

Use the laboratory **Stocks et lots > Stock** workspace for movements and linked production lots. The current application provides this UI; old API-only and mock-PDF implementation notes have been removed. Backend paths are relative to `cabinet_backend/`.

## Immutable stock ledger

`Inventory` balances are maintained by append-only `InventoryTransaction` movements. Existing quantity/unit edits and destructive journal changes are not reconciliation methods. The older `StockItem` resource is separate from this ledger.

- RESTOCK adds quantity; USAGE subtracts measured material and links its prescription/production attempt and optional lot.
- Explicit measured losses and compensating corrections use server-validated movement types and references. A reversal derives its quantity and original prescription/lot from the original movement, not a second user-entered deduction.
- Opening balances are server-managed. Existing journal entries are immutable; corrections append evidence instead of rewriting history.
- Reuse an idempotency UUID only for the same payload. Changed item, quantity, case or lot must not be accepted as the original movement.

The UI accepts/displays at most two decimal places. Stored legacy precision is retained until a value is edited. Use the actual measured unit and item; free-text material names do not allocate inventory.

Relevant routes are `/api/inventory/`, `/api/inventory-transactions/`, `/api/production-lots/` and the prescription command endpoint. Reads are tenant-scoped and paginated. Clinical and role guards remain active for writes.

## Rework without duplicate deduction

Use the documented **Reprise liée au dossier d’origine** action with origin, cause, corrective action and restart stage. New workflows use the specialized `rework` command rather than a generic status PATCH. Leave losses empty for a correction with no measured stock loss.

Measured loss references an existing usage in its original production attempt. Reclassifying already consumed stock appends compensating records so the same physical consumption is not deducted twice. Example: starting balance10, usage-2 leaves8; reclassifying that same consumed quantity as a loss keeps8; a later measured replacement usage-2 leaves6. Partial measured quantities, source references and transaction/idempotency guards determine the actual journal entries.

Later laboratory assessment uses `assess-loss` against the original attempt/usage. It does not invent a second material consumption. Loss quantities are bounded by eligible measured usage. Rework preserves the original case link, actor, immutable cause/corrective evidence and attempt history; it resets the required downstream clinical validations.

The manual MY-TEST-001 demonstration linked a production lot without a consumable. It does not establish measured stock/loss behavior. That remains a separate walkthrough; backend ledger/rework regressions are recorded in [TEST_RESULTS.md](TEST_RESULTS.md).

## Loss analytics

`monthly_stock_loss_catalog` groups loss month, inventory item and unit. Different units are not added together. Movements freeze their reference unit cost, so later price changes do not revalue prior losses. Missing costs remain explicit as unvalued quantity/incomplete valuation. This is reference-cost valuation, not FIFO or weighted-average accounting.

Read the paginated `/api/analytics/stock-loss/` endpoint with month/item filters. Reversed manual losses are netted in their original loss month. Catalogs are refreshed through tenant-aware background work; read paths consume the precomputed catalog rather than regrouping source journals. See [BILLING_ANALYTICS.md](BILLING_ANALYTICS.md) for the shared refresh pipeline.

## Durable events and document generation

Source writes persist `TaskOutbox` in the same PostgreSQL transaction. Publication is attempted after commit with bounded broker timeouts. A Redis failure is retained for recovery rather than undoing an already committed business request. Beat recovers pending/published-but-unfinished events, and idempotent consumers commit effects with their processed state. Operational retry/reconciliation is visible in the app.

Deadline, catalog and PDF tasks always carry validated tenant context. Current monthly closing/credit workflows generate real private ReportLab PDFs through background tasks. Pending artifacts are presented as pending; email/WhatsApp adapters remain disabled by default and are forced off in simulation. These are distinct from older mock invoice records. Do not infer invoice issuance from an open monthly statement.

## Deployment

Use the synchronized source/schema/worker procedure in [INSTALLATION.md](INSTALLATION.md). Keep one Beat instance for an installation. Apply reviewed tenant migrations to the intended database only, rebuild workers, verify registered tasks and inspect durable recovery. Unique database/private-file backups and runtime signing keys stay outside Git. Never use `flush`, direct balance edits or destructive schema rollback to reconcile stock.
