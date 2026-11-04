# Cabinet 2.0 — development handoff

> Frontend follow-up on 4 November 2026: see [FRONTEND_INTEGRATION.md](FRONTEND_INTEGRATION.md). The previously missing case panels, stock/lot workspace, finance and operations screens now exist in source. Browser validation uses mocked contracts; live backend integration and the backend follow-ups below remain pending. The older frontend section describes the incoming checkpoint.

Snapshot: 4 November 2026. Latest user request was documentation for another PC/model; implementation paused at this snapshot. This file takes precedence over older progress notes where statuses differ.

## Paste this into the next coding model

> Resume Cabinet 2.0 using this repository's AGENTS.md, MODEL_HANDOFF.md and BPMN_IMPLEMENTATION_PROGRESS.md. Use Graphify before code exploration; rebuild its local graph if missing or stale. Preserve all local/untracked work. Continue the already approved BPMN remediation order, including backend consistency, frontend integration, meaningful regression tests and verified deployment. Confirmed rules: J+2 express = 30% surcharge; J+1 requires a manual laboratory quote; monthly statements include cases delivered that month in Africa/Casablanca. Never print secrets, send real email/WhatsApp, commit/push, or overwrite the original database without authorization. External delivery stays disabled. Current working tree is incomplete; inspect deployment/test caveats below before running it. Do not spawn agents unless I request them. Keep replies concise.

## Location and version

- Original project: `C:\Users\SetupGame\OneDrive\Desktop\New folder\Soutenance\Projet Innov`.
- Branch: `feat/labo-config-and-ui`, repository `https://github.com/Mouss2000/I.E`. User authorized a source checkpoint commit/push for transfer. Clone this branch, not main, to obtain that checkpoint; inspect Git status for later local edits. Private database/media/credentials remain excluded.
- Python: root `venv\Scripts\python.exe`; Django project: `cabinet_backend`; React/Vite: `cabinet_frontend`.
- Read `OTHER_PC_SETUP.md` for transfer/setup. Do not copy virtual environments or assume native Django loads Compose `.env`.
- Graphify: root `graphify.cmd`, isolated `.graphify-venv`, distribution `graphifyy==0.9.97`. Refreshed for checkpoint: 1026 nodes/2264 edges. Generated graph is ignored; recreate it on a new PC. Query before source searches as AGENTS.md requires; refresh with `graphify.cmd update .` after changes.
- Original sandbox sometimes reports protected `.codex/skills/graphify/references` as deleted. Verify actual filesystem access before treating those as intentional deletions.

## Business scope already authorized

Full audit remediation, not merely generated snippets:

1. Authentication, secret rotation, tenant/workstation authorization, restricted runtime DB role.
2. Central workflow transitions with complete immutable history.
3. Tooth-level intake, delivery service, private files, QR, physical/digital inspections, dentist design approval with suspended deadline.
4. Measured casting/fabrication losses, cause-specific QC rework, linked post-delivery remakes and alerts.
5. Delivered-month closing, authoritative prices, disputes/exclusions, credit notes, actual PDF artifacts and configurable delivery.
6. Race-safe tenant cache, pagination, catalog analytics and durable task recovery.
7. Tests, tenant migrations, frontend build, rebuilt workers and isolated live smoke.

User decisions: express J+2 surcharge **30%**; J+1 **manual lab quote**; statements **delivered cases in the month**, Africa/Casablanca. External delivery disabled until configured. A checkpoint commit/push was authorized for this transfer; subsequent publishing requires a new request.

## Deployment and validation: do not confuse source with running version

- Earlier baseline: **67 backend tests passed**, tenant worker smoke passed, real api migrations through **0020**, customers through **0003**.
- During remediation, public **customers0004** applied; `secure_platform` initialized previously blank passwords.
- New api **0021–0023 are NOT applied to the original real tenant schemas**. They were exercised in isolated PostgreSQL tests.
- Original Docker worker/Beat may still be running **older images**. Native web/frontend stopped. Rebuild only after validation; do not mix new web contracts with old schema/workers.
- New `api.test_bpmn_acceptance`: checkpoint run **13/13 passed**, 71.267s, including latest case-creation idempotency edits.
- Django system check passed during acceptance run; `makemigrations --check --dry-run` reports no changes.
- Resource suite had 5/6 passing; known failure `test_demo_laboratory_account_is_supported` assumes passwordless login, now correctly rejected.
- Entire earlier suite has not been adapted/rerun on remediation. Frontend lint passes with one existing App.jsx set-state-in-effect warning; Vite build passes. Full frontend/backend integration remains unverified. Do not claim production readiness or 100% BPMN compliance.

Useful commands, from backend directory with native PostgreSQL environment configured:

```powershell
& '..\venv\Scripts\python.exe' manage.py check
& '..\venv\Scripts\python.exe' manage.py makemigrations --check --dry-run
& '..\venv\Scripts\python.exe' manage.py test api.test_bpmn_acceptance --noinput
# After fixing contracts/fixtures, run the full suite:
& '..\venv\Scripts\python.exe' manage.py test api customers --noinput
```

Use actual PostgreSQL for trigger/materialized-view coverage. Tests require a separate disposable test database. Never disable production guards to make old fixtures pass.

## Security and runtime facts

- Public auth now uses `PlatformAccount` + hashed opaque session tokens, password checking, database login throttling and session revocation. Passwordless demo/courier access removed.
- Public schema owns auth and tenant registry; operational `api` tables live in laboratory schemas. All workers require a validated active tenant and explicit tenant context.
- Redis keys use `django_tenants.cache.make_key`; callers use base `active_orders`. Never add a second manual schema prefix.
- `.runtime/signing-key` is a persistent ignored key shared with containers. Settings generate it if absent. Never print it.
- `.runtime/bootstrap-credentials.json` contains one-time account passwords. Never print/commit it. `secure_platform` initializes blank hashes only; it does not reset restored accounts.
- `.env` is ignored and used by Compose; native PostgreSQL password comes from environment or ignored `cabinet_backend/cabinet_backend/local_settings.py`. Do not read secrets into tool output.
- `private_media/` contains private clinical files/PDFs and must be transferred separately with the DB.
- `EXTERNAL_DELIVERY_ENABLED=0` remains the default. No test should send real messages.
- Runtime database role still defaults to PostgreSQL superuser; least-privilege separation is pending.

## Source map: implemented, not all fully verified

| Area | Files and behavior |
| --- | --- |
| Public auth | `customers/authentication.py`, models/views/serializers, migration0004: hashed opaque sessions, LAB/COURIER membership, workstation roles, login throttle, password-required login, logout/reset revocation. `secure_platform` command initializes missing passwords privately. |
| Doctor API | `customers/views.py`, urls: pricing, lab dentist directory, dentist clinics, owned case commands/evidence/QR/invoice operations. Creation requires UUID `Idempotency-Key`, canonical payload hash and immutable receipt; plaintext delivery PIN returned once. |
| Central workflow | `api/domain.py`, `workflow.py`, models/save: allowed transitions, role gates, inspections, production lots, design approval, custody commands, manual J+1 quote, version increments. Legacy intake version1 preserved; new cases version2. |
| Structured intake | `api/case_serializers.py`, `pricing.py`: up to32 distinct FDI tooth entries with function/form/shade/material, explicit disinfection, verified clinic/address, server-side pricing, role-aware field access, courier restricted serialization. |
| Evidence/commands | `business_models.py`, `case_commands.py`, `documents.py`: immutable events/receipts/evidence, inspection photos, real STL/image validation, tenant-scoped private files, signed QR, custody scan, hashed PIN with attempts/lockout, pause/design/fitting/rework commands. |
| History/cache | `signals.py`, `views.py`, migration0022: status history version+metadata; deferred PostgreSQL audit completeness; durable invalidation outbox; PG tenant read generation prevents stale cache race; paginated active-case endpoint with Redis failure fallback. |
| Inventory | `models.py`, `inventory.py`: decimal append-only ledger, DB guards, measured loss bounded by original consumption, partial `LOSS_OFFSET` + loss reclassification without double deduction; linked immutable rework records and attempt numbers. |
| Background work | `tasks.py`, `outbox.py`: durable calendar/invoice/cache/catalog/credit events, retries/failure tracking/recovery, J+4/J+2/J+1 deadlines and paused seconds, actual ReportLab PDFs. Tenant context required. |
| Accounting | `billing.py`, business models/views: delivered-month periods and statement snapshots, locked monthly closing, immutable invoices, disputed/excluded lines, bounded credits, invoice/credit artifacts. |
| Messaging/operations | `messaging.py`, business views: configured email/WhatsApp adapters, persisted SENDING/UNKNOWN states for ambiguous delivery, manual reconciliation and outbox retries. Disabled by default. |
| Analytics | `analytics.py`, `analytics_views.py`, migration0023: existing billing/stock-loss MVs plus delivered statement and financial MVs; concurrent refresh, unique indexes, tenant locks/timeouts, Beat15min. |
| Infrastructure | Compose Redis/worker/Beat, Python3.13 non-root Dockerfile, pinned backend requirements, persistent signing-key mount/private-media mount, Windows PG through host.docker.internal. |

New migrations:

- `0021_bpmn_workflow_and_accounting`: schema/models/fields.
- `0022_enforce_workflow_evidence_and_read_versions`: legacy normalization, source/history version guards, deferred audit completeness, read-generation trigger, evidence/closing immutability, revised inventory integrity functions.
- `0023_delivery_statements_and_financial_catalogs`: populated statement/financial materialized views with unique/filter indexes and reverse SQL.

## Immediate backend follow-ups

1. Preserve passing acceptance coverage; inspect current implementation rather than assuming every concern below is proven. Rerun relevant tests after changes.
2. Inventory idempotency comparison does not yet include `production_lot`; compare it. Propagate original usage's lot to reclassification/reversal records.
3. Post-delivery dentist remake can legitimately declare no measured losses. A later lab loss-assessment command is still needed: target original rework attempt/usage, preserve immutable `ReworkCase`, avoid another stock deduction. Existing classifier returns on an existing rework and filters current attempt, preventing this follow-up.
4. Wire inventory-ledger loss/low-stock notifications into the current inventory system; legacy StockItem alerts alone are insufficient.
5. Review command payload type validation, malformed input handling, role/field scopes and lock order. Admin account updates currently revoke sessions when sensitive keys are present even if unchanged.
6. Doctor private attachment download route still needs ownership-safe access; lab route already exists. Confirm all doctor evidence/file paths are accessible without cross-tenant leaks.
7. Review production lot linkage/capacity validation and evidence events. Review finance dispute/closing lock order and provider reconciliation permissions.
8. Private-file cleanup after outer transaction rollback and deterministic/idempotent PDF artifact storage remain concerns; avoid orphaned files or duplicate artifacts on retries.
9. Consider tighter history-insert version validation alongside existing deferred source/history checks; preserve legitimate legacy null versions.

## Frontend: major remaining work

Only partial edits made: password login in `DemoLogin.jsx`; courier/admin account handling and temporary-password display partly updated; Axios401 interceptors clear session and dispatch `cabinet-session-expired`.

`App.jsx` remains mostly the earlier API contract:

- Case form lacks required tooth-level function/form data and verified clinic selection. Actual STL upload needs integrating. New POST requires UUID `Idempotency-Key`; old UI omits it and gets400. Reuse key for retries of the same submission; generate a new one for a changed submission.
- Server-authoritative prices must replace trusted client totals; show J+1 manual quote state.
- Case list now returns paginated envelopes, not arrays. Adapt `results`/count/navigation and completed-case handling.
- Old courier generic PATCH/PIN assumptions conflict with custody QR/PIN commands; expose proper commands and actual entered PIN, never hashes.
- Add inspection/evidence/photos, CAD approval/pause/resume, production lot/usage, measured rework, dentist fitting and linked-remake UI.
- Add stock movement UI, catalog finance/closing/disputes/credits/PDF UI and operations recovery screens.
- Existing ProductionWorkflow lists omit new statuses; generic pause controls no longer permitted. Wire actual design-request/decision commands.
- Handle `cabinet-session-expired` in parent App; expose workstation roles in admin form. Remove stale passwordless-login wording.
- Previously planned `BpmnCasePanel`, stock movement and finance dashboard components **were not created**. Do not assume they exist.
- Preserve Dentist/Courier portal separation and current lab branding; rebuild assets only after frontend source works.

## Verification and deployment completion

- Update old tests to secure API contracts while retaining their original concurrency, retry, cache, ledger and analytics coverage. Build realistic workflow fixtures; never weaken transition guards just to jump to terminal statuses.
- Acceptance must verify both tracks, failed intake with photos, approval deadline suspension, measured partial loss without duplicate stock deduction, tenant/auth isolation, PIN lockout, linked remake origin/cause, delivery-month closing/dispute/exclusion/credit limits, real PDFs and disabled external delivery.
- Verify Redis outage fallback and stale-repopulation race; worker schema isolation and durable recovery; database immutability/raw SQL guards; financial/ledger aggregation without join fanout.
- Run backend full suite, frontend `npm.cmd run lint` and `npm.cmd run build`; rebuild Django-served frontend bundle if repository deployment uses it.
- Provision least-privileged runtime DB role separately from migration owner, then verify native/Docker credentials without exposing them.
- Back up real DB/private files. Apply shared/tenant migrations only after passing checks. Rebuild worker/Beat, verify task registration and Beat schedule, perform disposable-tenant live smoke, clean up only that disposable tenant safely.
- Keep real external dispatch disabled. Report remaining prerequisites honestly; do not claim completion based only on a subset of tests.
- Update Graphify and progress documentation. This transfer checkpoint is authorized for commit/push; do not publish subsequent implementation changes without a user request.


---

## Session Progress & Status Update

### Completed Tasks
- **Item #1 (Acceptance Baseline)**: Verified `api.test_bpmn_acceptance` (13/13 passed).
- **Item #2 (Inventory Idempotency & Lot Propagation)**: Added `production_lot_id` comparison to `record_movement()` idempotency check (`api/inventory.py`); propagated original lot to `REVERSAL`/`LOSS_OFFSET`/`REWORK_LOSS` in `classify_rework()`.
- **Item #3 (Post-Delivery Lab Loss Assessment)**: Implemented `assess_rework_loss()` (`api/inventory.py`) and `assess-loss` command (`api/case_commands.py`) with role-scoping and billing lock. Net-zero stock change, immutable evidence preserved. Added test `test_post_delivery_remake_allows_subsequent_lab_loss_assessment`.
- **Item #4 (Ledger & Valuation Alerts)**: Integrated `Inventory` low-stock and `MonthlyStockLossCatalog` unvalued loss checks into `api/alerts.py`.
- **Item #5 (Admin Session Revocation)**: Updated `customers/views.py` `accounts()` to only revoke active sessions when sensitive auth fields (`is_active`, `role`, `laboratory_id`, `workstation_role`) value-diff.
- **Item #6 (Doctor Attachment Download)**: Implemented `dentist_attachment()` view and route (`customers/urls.py`, `customers/views.py`) with strict dentist ownership check.
- **Test Suite Modernization**:
  - `api.test_bpmn_acceptance`: 13/13 passed.
  - `api.test_inventory_workflow`: Rewrote fixtures for sequential BPMN transitions, statement triggers, and migration `0023` (18/18 passed).
  - `api.test_business_resources`: Updated demo account fixtures for password auth (6/6 passed).

### Paused Tasks
- **`customers/tests.py` Suite**: Added test cases for session revocation diff and attachment downloads; adapted to password auth. Paused during execution: 6 failures require minor fixture fixes (`HTTP_IDEMPOTENCY_KEY` header on dentist order creation, temporary password propagation in reset test, password hash on duplicate account test).
- **Items #7, #8, #9**:
  - Lot capacity limits and evidence validation.
  - Private file cleanup on transaction rollback (`api/documents.py`) and deterministic PDF artifact storage.
  - History version insert validation.
- **Platform Manual Testing Prep**:
  - Migrations `0021`-`0023` not yet applied to live PostgreSQL schemas (`labo1`, `labo2`, `labo3`).
  - Backend (`manage.py runserver`) and Frontend (`npm run dev`) services paused before startup.
