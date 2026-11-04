# BPMN remediation implementation

Frontend follow-up: [FRONTEND_INTEGRATION.md](FRONTEND_INTEGRATION.md) records implemented React workflows and mocked browser validation. Tenant migrations, full backend regression and deployment validation remain pending.

User approved the full prioritized audit roadmap. Work remains active until implementation, verification and deployment complete.

Confirmed business decisions:
- Express J+2 surcharge: 30%, calculated server-side per case.
- J+1: manual laboratory urgency quote required before production.
- Monthly statements: cases delivered during that month, Africa/Casablanca calendar.

Implemented in source, not yet fully verified:
- Public opaque hashed session tokens, password login, courier accounts, SQL login throttling, session revocation.
- Generated ignored persistent signing key; one-time missing-account passwords in ignored `.runtime/bootstrap-credentials.json` (never print or commit contents).
- Explicit tenant membership and workstation permission checks; frontend password login updated.
- Tooth-level clinical evidence, private uploads, inspections, design review/pause clock, production lots, linked measured rework, QR custody and PIN commands.
- Central source transition invariants, status versions and deferred PostgreSQL audit completeness enforcement.
- Durable cache invalidation plus database read generation; paginated case API.
- Delivery-month statement periods, immutable invoices, disputes, credits, real ReportLab PDFs and configurable email/WhatsApp adapters.
- External delivery remains disabled by default. Do not send real messages during tests or deployment checks.
- New statement/financial materialized view definitions and operational outbox/message views.

Pending:
- Finish remaining validation/consistency details, ensure migration graph and PostgreSQL functions run correctly.
- Dedicated BPMN acceptance suite added: checkpoint run 13 tests passed. Frontend lint/build passed (one lint warning). Update previous tests to the secure API contract while preserving their original mechanism coverage.
- Complete frontend workflow, stock movement, doctor actions and catalog-backed financial UI.
- Provision least-privileged runtime database role separately from migration owner; update native/Docker settings safely, without printing secrets.
- Full backend tests, frontend lint/build, migrations for labo1–labo3, rebuilt Celery images and live disposable-tenant smoke test.
- Refresh Graphify and document setup/configuration and any external-service prerequisites.

Current deployment state: only public customers migration 0004 has been applied during this remediation. Private migrations 0021–0023 are new and not applied. Existing Docker worker/Beat still use previous images. Do not start native web/frontend unless needed for verification. No Git commit/push requested.

Handoff snapshot: see `MODEL_HANDOFF.md` for authoritative current status and remaining work; see `OTHER_PC_SETUP.md` for transferring the source checkpoint, database and private files to another Windows PC. User authorized a checkpoint commit/push on `feat/labo-config-and-ui` for this transfer.
