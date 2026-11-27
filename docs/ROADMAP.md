# Current implementation and remaining work

## Current v1 checkpoint — 25 November 2026

| Step | Status |
| --- | --- |
| Phases 0–7 | Complete locally |
| 8.0 decisions and backups | Complete |
| 8.1 provisional capacity | Complete |
| 8.2 payments and receivables | Complete |
| 8.2b light simulation | Implementation/tests complete; three monthly runs and generated evidence still pending |
| 8.3 dashboard | Complete |
| 8.4 laboratory identity and new PDFs | Complete |
| 8.5 product finish and additive demo cases | Complete; main frontend rebuilt, 30 unit / 83 mocked / 16 live checks passed, five fixture refusal tests |
| 8.6 deployment | Not started; explicit instruction required |
| Phase 9 full simulator | Deferred after the 9 December defense |

The running main demo is ready for owner testing at http://localhost:18080. Search **V1-** for the new stage/exception examples; see [the French user guide](GUIDE_UTILISATEUR.md) and [presenter instructions](../DEMO_GUIDE.md). MY-TEST-001 remains protected and its November period remains open. All changes remain uncommitted. Earlier checkpoint paragraphs below are historical delivery notes; the dated [test results](TEST_RESULTS.md) state what was actually run.



Checkpoint: 25 November 2026. Dated verification is in [TEST_RESULTS.md](TEST_RESULTS.md); the complete audience walkthrough is [DEMO_GUIDE.md](../DEMO_GUIDE.md).

## Completed and demonstrated

- Real Django/DRF, PostgreSQL laboratory schemas, password-authenticated public accounts, explicit laboratory/workstation ownership and signed custody/PIN commands.
- Tooth-level prescriptions, physical/digital intake, private uploads, mandatory inspections, dentist design approval and suspended deadlines, linked lots, measured rework, delivery/fitting and delivery-month statements.
- Immutable source/stock/planning evidence, UUID idempotency, tenant-aware cache generations and durable Redis/Celery recovery.
- Isolated synthetic Compose environment with restart-safe accounts/data and separate real-API verification resources.
- Shared production planning with attended setup/unloading windows, autonomous employee release, retained machine occupancy and guarded manager early starts. Demo migration0025 applied; native migration state is separate.
- Responsive clinical/action dialogs, contextual French reason dropdowns with optional free text, fixed top success/error feedback and periodic cross-portal refresh.
- MY-TEST-001 manually completed through CLOTURE and one standard 1500 MAD November statement line. Current-month closing remains unavailable until the month ends.

The integration approval gates 1-4 are complete. Step5 below remains separately scoped; the current demo has human acknowledgements, not equipment telemetry.

## UX streamlining track

The UX streamlining work ran in numbered phases. Phases 0-7 are complete locally: the baseline, workflow metadata/cache compatibility, personal queue/dentist list, shared case workspace, approved fewer-gesture actions and removal of the superseded UI. Graphify and repository reference checks confirmed the old ProductionWorkflow/ProductionCard, BPMN panel and standalone planning-progress screen had no active imports before deletion. The active workspace retains its equipment controls. Case labels now come from server metadata, including the restricted courier serializer; only non-workflow protocol labels remain in the frontend map. Read-only preview fixtures retain explicit labels, stages and planning destinations. See the dated report for verification.

Phase 6 consolidated the backend constants, labels, inspection permissions and rework restart validation around `workflow_spec`, preserving the old import names. An independent pre-refactor fixture freezes the guard values and audit spellings. All 18 commands have individual registered handlers; planning retains its prefix dispatch. The source/billing lock order, UUID receipts, validation sequence and existing error messages remain unchanged. Generated [workflow diagrams](WORKFLOW.md) show six route families and dashed exception edges; conformance tests cover all 24 option combinations and documentation freshness.

Phase 7 added the [BPMN coverage matrix](BPMN_COVERAGE.md): all 37 elements plus 20 gateway outcomes, three global rules and eleven documented differences. Every one of its 36 distinct test references resolves to a real method. Seven new acceptance tests cover physical resubmission, recasting/rescanning with measured loss, revised-design approval, manufacturing rework, failed quality returning to three possible cause steps, and accepted/rejected disputes before and after invoicing. The post-delivery test also verifies that failed fitting does not close the case or initiate rework implicitly. Application services, API contracts and migration state are unchanged.

The product owner approved the v1.0 decisions D1-D8 on 25 November (summarised in the BPMN coverage matrix). Phase 8 now implements advisory entry capacity (8.1), immutable payments/receivables (8.2), the isolated light simulator (8.2b), a manager/accounting dashboard (8.3), laboratory identity on new documents (8.4), and v1.0 finish (8.5). Step 8.0 records these decisions and protects the uncommitted tree with snapshots outside OneDrive. The product owner clarified that the initial preview compares all existing routes and labels the earliest achievable date as provisional. No application behavior has changed in Step 8.0. G7 piece inspection, new linked remake cases and lane/capability alignment are deferred to v2. Other matrix observations remain clarification items, not authorized clinical changes.

Step 8.1 is complete: advisory creation preview uses shared scheduler primitives without writes/locks/receipts, compares existing routes and preserves lab route selection. The French form offers submit-anyway/slower-service and remains usable when the preview is unknown or offline. Full results:196 backend,22 frontend unit,67 mocked and13 live tests; main demo rebuilt and protected case unchanged. Next is Step8.2 payments; the approved negative-balance handling (overpayment kept separate) is documented in BILLING_ANALYTICS. No new migration has been applied.

Handoff status: HEAD remains `42f52aa` on `feat/virtual-lab-demo`. UX Phases 0-7 are local, uncommitted and unpushed; no PR was created. Include these changes in a later authorized handoff before expecting another PC to show the current workspace.

Legacy follow-up: a read-only count of the presentation schema `simlab` on24 November found49 cases, zero with `intake_version < 2`, zero at `FRITTAGE_9H`, and zero matching either condition. The legacy quality checkbox and hardcoded frittage UI texts were therefore removed without a manager fallback. Backend legacy branches in `workflow.py`, `domain.py` and the workflow specification remain intact. Before any native-data migration or removal of those branches, perform a separately authorized read-only native inventory and agree on a compatibility/migration plan; no native database was inspected or changed in Phase 5.

The full Phase 9 simulator is deferred until after the 9 December defense; the light version belongs to Step 8.2b. Deployment, irreversible November closing and device integration retain their separate gates. Preserve backend legacy intake/frittage branches until the separately scoped native inventory and migration decision above.

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

Step8.2 is complete locally: immutable payments/allocations/reversals, live aging and restricted dentist balances. Migration0026 applied in demo and verification, with the original protected case and November period unchanged. Final suites:216 backend,27 unit,71 mocked and14 live. Next implement8.3 before final8.2b runs so dashboard isolation can be verified by the simulator. No commits or deployment.

Step8.3 is complete locally: tenant-local uncached dashboard, manager operations and finance, accounting finance only. Existing analytics and risk services reused;224backend/27unit/75mocked/15live tests pass. Main rebuilt with the protected case unchanged. Next8.2b uses this endpoint in its isolation checks;8.4/8.5 remain pending.


Step8.4 is complete locally: singleton laboratory identity, additive0027 in Docker demo/verification, manager editing/accounting read-only form, and Gestion Labo identity on new documents. Legacy financial rows/PDFs stay immutable; empty identity falls back to Client.name. The main fictitious Atlas profile was saved through the UI, with desktop/mobile/keyboard checks. All241 backend,28 unit,80 mocked and16 live tests pass. Step8.2b monthly evidence remains running on frozen pre-D4 images; Step8.5 product finish is next. No commit.
