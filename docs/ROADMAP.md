# Current implementation and remaining work

Checkpoint: 21 November 2026. Dated verification is in [TEST_RESULTS.md](TEST_RESULTS.md); the complete audience walkthrough is [DEMO_GUIDE.md](../DEMO_GUIDE.md).

## Completed and demonstrated

- Real Django/DRF, PostgreSQL laboratory schemas, password-authenticated public accounts, explicit laboratory/workstation ownership and signed custody/PIN commands.
- Tooth-level prescriptions, physical/digital intake, private uploads, mandatory inspections, dentist design approval and suspended deadlines, linked lots, measured rework, delivery/fitting and delivery-month statements.
- Immutable source/stock/planning evidence, UUID idempotency, tenant-aware cache generations and durable Redis/Celery recovery.
- Isolated synthetic Compose environment with restart-safe accounts/data and separate real-API verification resources.
- Shared production planning with attended setup/unloading windows, autonomous employee release, retained machine occupancy and guarded manager early starts. Demo migration0025 applied; native migration state is separate.
- Responsive clinical/action dialogs, contextual French reason dropdowns with optional free text, fixed top success/error feedback and periodic cross-portal refresh.
- MY-TEST-001 manually completed through CLOTURE and one standard 1500 MAD November statement line. Current-month closing remains unavailable until the month ends.

The integration approval gates 1-4 are complete. Step5 below remains separately scoped; the current demo has human acknowledgements, not equipment telemetry.

## Next integration gate: device contract and adapters

Define tenant-owned authenticated devices and stable job/case/batch/revision identities. Ingest immutable, sequenced, idempotent events shared by real vendor adapters and synthetic adapters. Specify duplicates, out-of-order delivery, replay, heartbeat expiry, reconnect and unknown/offline states.

Equipment completion must never grant clinical approval or guess inventory loss. Failures should create explicit holds and durable replanning. Preserve manual quality gates, existing clinical commands, active reservations and tenant isolation. Start this integration step only when the user authorizes it.

## Later simulator and resource scope

- Clearly labeled synthetic-only delay/failure/disconnect and staffing scenarios using the shared event contract.
- Shared-batch equipment cycles, alternate qualified unloader handoff and pre-cycle abort/recovery.
- Deterministic replay and acceptance coverage for event ordering, reconnect, cross-tenant denial, attended/unattended occupancy and clinical gates.
- Calibrated manufacturer protocols/adapters and actual device validation. No printer/CAD/CNC/furnace connectivity has been demonstrated.

## Separate deployment and hardening work

- Reconcile native public/tenant migration state, backed-up private files, persistent signing keys and worker images before applying the new source. Synthetic success is not native deployment completion.
- Separate migration ownership from a least-privilege runtime database role; validate credential/network configuration without publishing secrets.
- Load-test the bounded scheduling heuristic, task/read pagination and large-laboratory behavior. No optimal-scheduling or low-latency production guarantee is established.
- Review the historical audit follow-ups against current source: lot-capacity/evidence edges, private-file cleanup on transaction rollback, deterministic PDF storage and immutable-history insert validation. Preserve existing guard/concurrency tests while resolving any remaining gaps.
- Configure real external delivery only through a separately authorized deployment. Simulation never sends real email or WhatsApp.
- Complete separate user-guided exception/rework and measured-stock scenarios. Preserve the already closed successful case as presentation evidence.

Completed fixes formerly listed as blockers include CORS Idempotency-Key preflight, atomic production-route selection, realistic authenticated test fixtures and planning/source lock ordering. They are not pending work. Historical test results remain labeled by date instead of being repeated as current failures.
