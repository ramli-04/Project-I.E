# Virtual laboratory implementation

Branch: `feat/virtual-lab-demo`. Shared production features remain in the main Django application; simulator-specific setup runs in a separate Compose project.

## Step 1 — architecture inspection (complete)

Graphify identified the existing tenant-aware workflow, planning reservations, qualifications, availability and durable outbox. The current scheduler reserves an employee for an entire equipment cycle. Its frontend `npm run demo` uses mocked browser responses and cannot prove backend behavior.

## Step 2 — reproducible real-API demonstration environment (complete)

Implement isolated PostgreSQL, Redis, migrations/bootstrap, real Django API, worker/Beat and compiled frontend. Seed synthetic laboratory accounts, personnel, equipment, clinical evidence and three legitimate cases through existing serializers/workflow guards. Never reset progress at restart or mount the native Windows database/private files. The initial device records are virtual resources, **not yet connected simulators**.

Verified clean empty-volume startup and repeated seed execution; real HTTP authentication, planning/prescription/workload reads, CORS, access denial, and Redis -> worker -> tenant catalog refresh passed. Three seed-safety tests and nine frontend unit tests passed. First milestone runs at localhost18080; see `DEMO_GUIDE.md`. Temporary synthetic volumes were intentionally reset once to verify clean initialization; native data was untouched. No claim of full browser integration or full legacy regression success.

## Step 3 — shared production resource model (next)

Represent attended setup, unattended cycle, awaiting unloading and attended unloading separately. Reserve technicians only during attended periods, retain machine reservation until unload confirmation, enforce qualification and shift rules, and keep active/locked work protected. Preserve existing task/workflow/audit behavior for operations without automation. Include meaningful PostgreSQL concurrency and resource-overlap tests before migration/deployment.

## Step 4 — shared device contract and simulator adapters

Define authenticated tenant-owned devices, stable job/case/batch/revision identities, sequenced immutable/idempotent events, heartbeat expiry and unknown/offline states. Build vendor-neutral event ingestion used by both real adapters and virtual printer/CAO adapters. Machine completion never grants clinical approval. Manual quality checks remain required. Errors trigger visible holds and durable replanning, not silent case completion or guessed inventory loss.

## Step 5 — simulation controls and acceptance scenarios

Expose clearly labelled synthetic-only scenario controls: start a virtual job, inject delay/failure/disconnect, change staffing availability, and inspect planning/audit consequences. Include deterministic event replay, duplicates, out-of-order delivery, reconnect, cross-tenant denial, unattended employee release, retained machine occupancy, batches, and manual quality gates. Virtual time must not alter application clocks indiscriminately or fabricate worker performance measurements.

## Step 6 — portable checkpoint and presentation

Verify startup from a clean source checkout, restart idempotence, browser/API/worker interaction and isolation from the native application. Document actual demonstrated capabilities and remaining hardware validation. Publish tested source, Compose configuration and synthetic seed only; exclude credentials/private uploads/database exports. Manufacturer adapters remain equipment-specific future work.

The demo uses the production planning/backend; only device-event sources and synthetic fixtures differ. No simulated UI response counts as backend integration evidence.
