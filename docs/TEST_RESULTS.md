# Application regression results

## Contributor source-only startup - 21 November 2026

Exported the staged Git tree without ignored/local files and built it in the disposable `cabinet-handoff-check` project with fresh PostgreSQL, Redis and runtime volumes. Bootstrap exited 0, PostgreSQL/Redis/backend were healthy, the frontend returned HTTP200 and the environment endpoint reported SIMULATION with a reachable database.

`check_virtual_lab` passed all three checks: reseeding preserves progress/history/passwords; real login, tenant reads, CORS and public/anonymous denial; Redis-to-Celery-to-tenant-PostgreSQL/result execution. The diagnostic now reads `DEMO_FRONTEND_ORIGIN`, defaulting to port18080; the verification override supplies port18081. Django static discovery tolerates an absent generated `frontend_build` directory in a clean clone. These two startup corrections were verified in the rebuilt source-only stack; the complete regression suites below were not rerun for them.

The publishable tree includes source, migrations, demo assets and maintained documentation, with no local environment files, databases, private uploads, generated builds, installed dependencies or machine checkpoint notes. Only the disposable handoff project's containers and volumes were removed after checking; the main demo and earlier verification data were preserved. Graphify AST refreshed to 1526 nodes, 4086 edges and 94 communities.

## Contributor-folder consolidation - 21 November 2026

Removed superseded handoff reports, duplicate test summaries, the unsupported Windows EXE launcher/spec, inactive Tailwind JS config and duplicate frontend ignore file. Maintained technical documents now live under `docs/`; root README and the presenter guide link to the documentation index. Current facts and unresolved deployment scope were retained while contradictory historical status instructions were removed from the active handoff.

Three legacy SQLite files were copied and SHA256-verified in ignored `.runtime/backups/legacy-sqlite-20261121-204727` before the obsolete executable bundle and legacy SQLite copies were removed from the active tree. Active PostgreSQL, Docker volumes, runtime keys and private uploads were untouched. Generated native frontend files were cleared; the empty build directory remains available for regeneration.

Cleanup checks: **14 frontend unit tests passed**, production build passed, lint exit0 with the existing App.jsx warning only, running-demo Django system check found no issues. All 43 Graphify-located frontend modules are reachable from runtime/test entrypoints; no missing relative imports were found. The built CSS is byte-identical to the running demo after removing the inactive config. All maintained local Markdown links resolve and removed-document references are absent. The publishable-file audit contains no private databases, backups, runtime keys or installed environments; NUL-safe positive/negative ignore checks preserve local/editor exclusions without hiding shared source. Graphify AST refreshed to 1535 nodes, 4095 edges, 82 communities. The browser suites below were not rerun for this documentation/dead-file cleanup. No commit or push performed.

## Technician reason dropdowns, presentation and cleanup - 21 November 2026

Added contextual French predefined reasons with optional details/free text for clinical actions, equipment progress and planning supervision. Existing plain-text command/audit payloads, clinical checks, role restrictions and reservation guards are retained. Seven unused frontend starter files and generated logs/build/test/bytecode artifacts removed after reference checks. No backend application source or migration change in this task.

| Check | Result |
| --- | --- |
| Frontend unit | 14 passed |
| Mocked-API browser regression | 24 passed, 44.3s |
| Real API/browser, separate cabinet-ui-verification project | 9 passed, 57.0s |
| Final production frontend build | Passed; existing bundle-size advisory |
| Lint | Exit0; existing App.jsx:63 warning only |
| Reusable synthetic STL | 4 finite triangles, 6 edges each shared by 2 faces |
| Simulation-only QR helper | Read-only smoke passed; signed content withheld from notes |
| Main served frontend | HTTP200; new reason control present in served bundle |
| Preserved user case | CLOTURE, quality validated, exactly one 1500.00 MAD statement line |
| Graphify AST | 1618 nodes /4191 edges /88 communities, no paid labeling |

New browser coverage proves that a selected reason plus detail reaches the existing command payload, inspection criteria are not auto-selected, failure retains the draft, success clears the submitted note, cycle confirmation remains explicit, free text alone works, and supervisor reasons survive a rejected assignment. Mobile width 390 remains within the viewport. The live phase test selects Cycle terminé through the real UI before its human acknowledgement. Existing live free-text locators were updated to distinguish the newly added dropdown. All 9 live checks pass on the real API/Redis/PostgreSQL stack after this selector correction.

The completed MY-TEST-001 case was not advanced or reset for verification. Main frontend was rebuilt; verification services were stopped with volumes preserved. Generated browser reports/screenshots were removed after recording results here. DEMO_GUIDE.md was rewritten as a complete presenter walkthrough and reviewed against current controls/workflow; no claim of a second full manual presenter rehearsal. Historical full Python131 results below were not rerun for this UI/documentation change.

## User-guided successful case completion - 21 November 2026

The user's manual physical-impression/CNC/crystallisation walkthrough **MY-TEST-001** reached clinical closure and its delivery-month statement through the normal UI. Screenshots showed explicit furnace cycle/unloading, finishing, quality, packaging, dispatch and billing. Final read-only ORM verification confirms **CLOTURE**, quality validated, delivery **2026-11-21 20:11:19 UTC**, fitting **20:12:46 UTC**, not paused, STANDARD total **1500.00 MAD**. Exactly one November statement line exists: base1500.00, express0.00, contestedfalse, excludedfalse. No agent state advancement, data reset or guard bypass was used for this final verification.

November statement remains open as expected before month-end; this walkthrough does not claim current-month closing or invoice issuance. Historical closing/PDF tests below remain separate. Measured stock losses, rework/exception paths and actual devices were not exercised by this successful case. No automated suite was rerun during the final read-only check. The reason-dropdown preference from this walkthrough was subsequently implemented; see the newer results above.

## UI streamlining — 21 November 2026

Implemented clinical/stage modal navigation, current-task-first progress, QR/PIN dialogs with successful-input cleanup, explicit arrival scan, French presentation messages and fixed top notifications. Wire contracts and backend BPMN/tenant/audit guards remain unchanged.

| Check | Result |
| --- | --- |
| Frontend unit | 14 passed |
| Mocked-API browser suite | 22 passed, 43.1s |
| Real HTTP/browser suite on isolated verification stack | 9 passed, 50.4s |
| Frontend production build | Passed; single-bundle size advisory |
| Lint | Passed; existing App.jsx:63 effect warning |
| Graphify AST update | 1589 nodes, 4138 edges, 84 communities |

New browser coverage proves required checks open inside a dialog without scrolling the page, French errors remain visible/hit-testable above the native modal, successful actions replace errors, dialog focus restores correctly, and QR/PIN fields close/clear after validated actions. Pickup and laboratory deposit remain separate signed commands; incorrect QR/PIN attempts are rejected without closing the input dialog. Existing command/idempotency/stock/pricing assertions remain intact.

The first live run in the user's occupied demo had4 passes and2 reservation timeouts: MY-TEST-001 was already in furnace SETUP and legitimately held the technician. No source/SQL bypass, manual case completion or volume reset was used. The complete rerun used optional `compose.verify.yml`, separate project `cabinet-ui-verification`, independent PostgreSQL/Redis/runtime volumes and frontend/API ports18081/18001. Real responses only, no interception/mocked backend. All 9 tests passed, including human machine phases and both intake tracks through delivery/fitting/statements. User case remains TRAITEMENT_THERMIQUE / IN_PROGRESS / SETUP. Full Python131 regression below was not rerun for these frontend changes.

## Step 4 — 15 November 2026

Shared attended/unattended resource separation implemented and migrated in the isolated demo. All changes remain local and uncommitted; native database untouched. Stop for approval before the device/simulator step.

| Check | Result |
| --- | --- |
| Full Django `api customers` regression | 131 passed, 291.197s |
| Final focused `api.test_planning` regression | 41 passed, 67.340s |
| Final global-horizon / synthetic seed boundary checks | 5 passed, 7.347s |
| Frontend unit tests | 11 passed |
| Mocked-browser regression | 16 passed, 27.8s |
| Real Docker HTTP/browser regression | 9 passed, 1.4min |
| Production frontend build | Passed |
| Django checks / migration consistency | No issues / no changes detected |
| Real Redis→Celery→tenant PostgreSQL/result smoke | Passed |
| Lint | Exit0; existing `App.jsx:62` warning only |

New resource tests prove attended-window employee exclusion, acceptance of other work during an autonomous interval, machine occupancy beyond estimates, unloading confirmation, absence/qualification/ownership checks, cross-shift cycles, workload exclusion of unattended time, phase sequencing, idempotency, supervisor start authorization, rollback of forbidden source advancement and concurrent machine-claim rejection. PostgreSQL may reject raw simultaneous conflicting GiST inserts with23P01 or abort a deadlock victim with40P01; the test accepts these specific safe outcomes and asserts exactly one committed claim. Normal application commands serialize reservations with the existing tenant advisory lock.

The live phase test uses real HTTP and UI controls with explicit synthetic human acknowledgements. It does not claim device connectivity, elapsed production-speed simulation or automated clinical validation. Repeated browser runs retain their synthetic cases and audit records. Start controls use explicit manager authorization to tolerate intervening forecast recalculations; tests do not reset databases or bypass workflow guards.

Commands: `docker compose -f compose.demo.yml exec -T backend python manage.py test api customers --noinput`; frontend `npm.cmd test`, `npx.cmd playwright test`, `npx.cmd playwright test --config=playwright.live.config.js`, `npm.cmd run lint`, `npm.cmd run build`. Final isolated images include current source. See `DEMO_GUIDE.md` for phase operation and migration limits. Historical results below are superseded by this checkpoint.

## Step 3 — 15 November 2026

Step3 is complete. User authorized the full regression/remediation gate after Step2. No commits or publishing performed. The production implementation is unchanged during Step3; changes repair tests and fixtures to exercise current contracts. Stop for approval before Step4 (separate technician work from unattended machine cycles).

Baseline: `manage.py test api customers --noinput` discovered121 tests and reported22 failure entries/13 errors (224.501s). Counts include unittest subtests; do not infer an exact passing-method count by subtraction.

Repairs:

- Authenticated laboratory configuration/CQRS requests using tenant manager accounts; retained explicit anonymous-denial coverage and audit-actor spoof rejection. List checks now assert paginated `results`, versioned cache envelopes and decimal strings.
- Added shared real-API workflow fixture helpers with private media isolated in temporary directories. Route tests use clinical items, intake evidence, production lots and signed QR/PIN commands, rather than assigning delivery status or quality approval directly. Tenant setup explicitly restores its schema before operational writes.
- Analytics fixtures now deliver cases into eligible past months and issue invoices through actual monthly closing. They preserve snapshot immutability, persisted-price, no-join/no-group-by read-path, failure retention, isolation and aggregate-count assertions. Unassigned, unbilled cases remain in the detailed catalog and do not acquire invented invoices.
- Legacy undated invoices are created in a disposable schema genuinely migrated back to api0015 and forward to the latest migration, then checked for preserved unknown dates. Current SQL guards are never disabled.
- Platform tests provide UUID creation keys, create clinics inside the target tenant, expect secure401 login failures, and verify old reset credentials/session rejection plus temporary-password success.
- Month-end coverage tests both sides of Casablanca local midnight using `ZoneInfo`, checking invoice and prescription timestamps as well as the PostgreSQL catalog. The previous assertion assumed UTC+1; installed Python/PostgreSQL rules both place its test instant in November. No production clock/timezone setting was changed.

| Check | Final result |
| --- | --- |
| Full `manage.py test api customers --noinput` | **122 passed**, zero failures/errors, 272.979s |
| Frontend unit tests | **9 passed** |
| Mocked-browser integration suite | **16 passed**, 30.5s |
| Live Docker HTTP/browser suite | **8 passed**, 57.1s |
| Production frontend build | Passed |
| Frontend lint | Passed; existing `App.jsx:62` effect warning |
| Django system check | Passed, no issues |
| Migration drift check | Passed, no changes detected |

Full backend verification includes the existing BPMN, inventory ledger, immutable audit, CQRS/cache, outbox/task and real PostgreSQL concurrency tests, plus the historical-schema roundtrip and both month-boundary cases. No tests were skipped or guards disabled to obtain this result. The extra test compared with the baseline explicitly checks anonymous configuration denial.

Local demo images were rebuilt to include the repaired tests. Graphify was refreshed (1514 nodes/3871 edges/95 communities). This verifies current automated functional coverage; connected printer/CAD adapters, technician-versus-machine phase separation and production load testing remain pending.

All backend runs use a disposable PostgreSQL test database. Logs remain ignored in `.runtime/step3-*.log`; no native/demo database reset was performed. Existing Step2 source changes remain uncommitted. No new application migration is required.

## Historical run — 4 November 2026

Source checkpoint: `21ac6d4`, branch `feat/labo-config-and-ui`. No application code changed during this test run.

## Results

| Check | Result |
| --- | --- |
| `manage.py test api customers --noinput` | Failed: 82 tests run, 22 failure entries, 13 errors; 181.722 seconds |
| BPMN acceptance cases within full suite | No reported failures/errors in `api.test_bpmn_acceptance` (13 cases) |
| `manage.py check` | Passed, no issues |
| `manage.py makemigrations --check --dry-run` | Passed, no changes detected |
| `npm.cmd run lint` | Passed with one `react(set-state-in-effect)` warning in `src/App.jsx:44` |
| `npm.cmd run build` | Passed, Vite production bundle generated |

Failure counts include unittest subtest entries; do not subtract them from82 to infer an exact number of passing test methods.

## Observed blockers

1. **Authentication contract:** old `api/tests.py` and some CQRS tests make unauthenticated requests. They now receive401 before reaching resource/workflow assertions. Authenticate appropriate tenant/workstation principals and retain explicit anonymous-denial tests.
2. **Workflow fixtures:** CQRS/billing fixtures directly advance unaccepted cases. Current source guards raise `Accept the case before advancing.` Prepare cases through valid transitions; preserve rollback/history coverage.
3. **Invoice fixtures:** billing tests set `billing_stage='FACTURE'` directly. ORM and PostgreSQL reject this with `Issue invoices through monthly closing.` / `Invoicing requires an issued monthly statement`. Create legitimate issued statements/invoices, with a separate intentional legacy-data migration scenario where needed.
4. **Response shape:** `api/test_cqrs.py:133` indexes case-list data as an array and raises `KeyError: 0`. Update authenticated tests to paginated `results` and current decimal serialization.
5. **Creation idempotency:** two `customers/tests.py` cases omit UUID `Idempotency-Key`, receiving400. Supply stable keys for retries of the same payload.
6. **Login/reset scenarios:** several platform tests expect400 where secure login returns401. `test_password_reset_hash_and_session_expiry` also cannot log in with its supplied credentials after reset; inspect test credential handling and implementation before classifying it as fixture-only.

These failures prevent declaring the full application verified. Several traces demonstrate stale test assumptions, but adapting fixtures may expose further application bugs. Do not remove authentication or workflow/database guards merely to make tests pass.

## Scope and next steps

- Tests used a temporary PostgreSQL database and tenant schemas; real tenant migrations were not applied.
- Migrations through api0023 succeeded in temporary tenant schemas.
- The logged `OSError: Broker down` came from an intentionally mocked broker-failure test; it is not evidence of a real broker outage.
- No browser interaction, frontend/API end-to-end verification, live worker smoke or external message delivery was performed.
- This November4 snapshot is historical; current verification and remaining limits are recorded above and in `ROADMAP.md`.
- Next: adapt regression fixtures/contracts, investigate reset/session case, finish frontend integration, rerun full suite and perform browser/live-worker checks.
- This report is local and uncommitted; no new push performed during testing.
