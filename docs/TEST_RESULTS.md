# Application regression results

## UX Step 8.8 presentation readiness - 26/27 November 2026

Implements the owner's 21 remarks from the 26 Nov manual end-to-end test (TEST-2611-01) and the three owner requests, with the four approved demo-data decisions. Nothing committed.

| Remark | Outcome |
| --- | --- |
| 1 Fonction/Forme/Teinte dropdowns | Done: `ChoiceWithOther` (VITA A1–D4, "Autre…" free text); payload unchanged |
| 2 Toast after login | Done: login/logout responses no longer trigger "Action enregistrée." |
| 3 BROWSER clutter | Done: 29 open BROWSER cases paused through the normal `pause` command (0 refused, reversible). In SIMULATION builds, cases that are paused-for-test or closed >24 h are hidden behind "Afficher les dossiers de test automatisés (N)"; fresh test cases stay visible |
| 4 "À risque" on a new case | Investigated, not changed: risk is computed before the first planning pass (queue risk absent → chip now reads "Risque en cours de calcul") |
| 5 QR | Done: "Télécharger l'étiquette QR" after submission; courier "Importer l'image du QR" (jsQR 1.4.0, Apache-2.0, bundled, offline). Camera scan not done (lowest cut item) |
| 6 Stepper ✓ | Done, with hidden "(terminée)" |
| 7 Inspection form | Done: checklist → separate deviation flag → note → photo (shown only on failure/deviation) → button; note optional on pass (server already allowed it) |
| 8 Hours/backlog | Done on main: Mon–Sat 08:00–17:00, break 12–13; team shifts; backlog paused |
| 9 Supervised start | Done: "Prévu le … Le responsable peut autoriser un démarrage supervisé dès maintenant." plus a manager hint |
| 10 Dates | Done: French long dates (`labLongDate`) for computed deadlines and dentist dates |
| 11 Design upload | Done inside "Votre action"; latest version auto-selected |
| 12 Waiting messages | Done: specific per step (design version and send time, custody step, fitting) |
| 13 Problems panel | Done: collapses on step change; disabled "Reprendre le travail" hidden while a dentist review is pending |
| 14 Dentist view | Done: no risk chip or workshop instruction; "Votre dossier est à l'étape « … » … Livraison prévue : …" |
| 15 Lot from the case | Done: `LotPanel` (case preselected) driven by the new read-only descriptor `next_requires_lot`; Stocks lists only eligible cases |
| 16 Durations | Done: "n min de travail · machine réservée hh:mm–hh:mm" |
| 17 Transient "Bloquée" | Done: "Affectation en cours…" only when all dependencies are completed and the reason is a known transient planner reason |
| 18 Delivery note | Done (new PDFs only): labelled identification, contents table, dates (edited/shipped/planned), lot traceability, QR caption, two signature boxes |
| 19 Empty Facturation | Done: current month preselected; explanations for empty invoices, disputes and statements; catalogue explained |
| 20 Statement lines | Done: compact rows; form only after "Ajuster" |
| 21 Opérations | Done: moved to Configuration → "Diagnostic technique" (manager); failed/pending only by default |
| Request: billing | Done: "Commandes livrées" (réf., cabinet, date, travail, service, montant, statut, total; click opens the case) |
| Request: planning | Planner unchanged; plain-French "Pourquoi cette affectation ?" in the drawer and the case; "Par technicien (journée)". Fairness read-only on main: RECEPTION 4/7 tasks, QUALITE 5/9, FAO 6/8/11, first slots tomorrow 08:00. No weight change proposed |
| Request: stock | Done on main: 12 consumables via the real API/ledger, 2 below threshold |

**Data (main only):** `demo/prepare_v1_operations.py` (guarded, idempotent; second run changed nothing; 3 stdlib guard tests). It creates 5 synthetic accounts via the seed's own path and everything else via the API: 10 staff (2/3/3/2), 54 shift rows, settings, 12 consumables, 29 pauses. A pg_dump was taken first: `GestionLabo-snapshots/20261126-224652-before-8.8/demo-before-8.8-data.dump` (3,024,824 bytes, 538 TOC entries). The seed command was briefly edited and then restored byte-identical, because it also runs in the verification project.

**Backend changes:** `workflow_spec` adds `next_requires_lot` (cache shape `workflow-step-v3`); `documents.delivery_slip` rewritten (new `trailer` option). No migration (drift clean).

| Check | Result |
| --- | --- |
| Django `api customers` (verification images) | **242 passed**, 695.1 s |
| Frontend unit | **40 passed** (new: testCases, planningExplain, financeHelpers) |
| Lint / build | Only the permitted App.jsx warning / built |
| Mocked Playwright | **93 passed** (7 new 8.8 tests) |
| Live Playwright | 15 passed + "human starts… CAO task" failed twice at 23:3x, then **passed at 00:01** |
| Main read-only smoke (1440/390; manager, dentist, courier, technician B) | **30/30**, screenshots inspected |
| MY-TEST-001 / TEST-2611-01 | Unchanged (CLOTURE, quality validated, one 1500.00 line each); November open |

Live-suite fragility, observed and not fixed: the CAO test needs a CAD reservation that is already due. The verification data grows with every run (91 open BROWSER cases), so CAD slots drift later. At 23:33 the earliest was 00:00, beyond the test's 45-second poll. This is not related to the 8.8 code.

Existing tests changed deliberately:
- free-text fills became `selectOption` (dropdowns);
- "Créneau prévu" became "Prévu le 01/01/2099";
- "Échéance calculée : 2026-11-25" became "25 novembre 2026";
- the live capacity test now selects from the dropdowns.

No assertion was weakened. A React key collision (problems and dossier panels sharing a key) was found and fixed during testing.

## UX Step 8.7 post-test corrections - 26 November 2026

Frontend-only change requested after the first manual demo test. No backend, API, migration, persisted action or message-contract change: all 129 backend source files are byte-identical to the after-8.5 snapshot (`local_settings.py`/`memory.md` excluded before reading).

- **Lab portal:** removed **Vue d’ensemble** (`ClinicalDashboard`: an odontogram merging all cases into one mouth, a decorative 3D arch, a duplicate ring map, client-side stage bars) and its duplicate **Facturation** sub-tab. Landing is **À faire** (accounting: **Facturation**). `DashboardAlerts` now sits at the top of the landing page; the alert pop-up opens it there with focus. Unreachable laboratory branches of the old fallback layout in `App.jsx` were removed.
- **Dentist portal:** removed **Vue clinique**. Default tab is **Mes commandes** (or **Nouvelle prescription** with no cases). Each card shows the server `stages` as an accessible strip (`aria-current="step"`, text “(terminée)”) and **Livraison prévue : …** in Africa/Casablanca, or **Date à confirmer par le laboratoire**.
- **Prescription form:** new `ToothPicker.jsx` (FDI chart, real buttons with `aria-pressed`, live count). Selecting teeth creates one **Dent N** fieldset per tooth in chart order; the typed **Dent FDI** field, datalist and **Ajouter une dent** were removed; **Appliquer à toutes les dents** copies the first block only on click. No tooth is preselected and shade starts empty (previously 11/A1). Submission is disabled until a tooth is selected. Payload shape unchanged.
- **Clean-up:** `ClinicalDashboard.jsx` deleted; `DentalTooth` moved to `ToothPicker.jsx` (login page still uses it). 125 CSS rules for classes proven unused were removed or trimmed. Alert pop-up copy now reads **Voir toutes les alertes**.
- **Defect found and fixed during verification:** at 390px the outer `<fieldset>` kept its min-content width (the 520px chart), clipping the form. `min-w-0` fixes it; the test now asserts the picker, remove button and submit stay within 390px and that the chart scrolls inside its card.

| Check | Result |
| --- | --- |
| Frontend unit | 34 passed (new `toothPickerHelpers.test.js`, 4 tests) |
| Lint / production build | Passed; only the permitted `App.jsx` warning and existing bundle advisory |
| Mocked Playwright | 86 passed, 141.2 s |
| Live Playwright (`cabinet-ui-verification`, guarded env) | 16 passed, 260.6 s; project stopped without `-v` |
| Main demo read-only smoke (1440/390, Demo Manager + Demo Dentist, no submission) | 24/24 checks; screenshots inspected |
| MY-TEST-001 (read-only) | CLOTURE, quality validated, unpaused, one 1500.00 MAD line, period open |

Existing tests changed deliberately: the old dashboard test was replaced by four tests (lab landing without overview, alert pop-up focus, chart selection by click/keyboard with 390px checks, dentist stage strip/date); the lab identity test now expects the **À faire** heading; three dentist-form helpers click **Dent 11** and type shade **A1** because nothing is preselected; the live capacity test clicks **Dent 11/21** instead of typing FDI numbers. No assertion was weakened.

Observed, not changed (pre-existing): a green **Action enregistrée.** toast appears right after login.

## Step 8.2b final campaign execution mode - 25 November 2026

The normal-month run remained active on its original containers. After confirming 12 Docker CPUs and ample memory, Ramadan and mixed were started concurrently under the same cabinet-sim Compose project, each with a separate network, PostgreSQL, Redis and runtime volume. Temporary service names are ramadan_backend and mixed_backend, with loopback ports18003/18004; the original normal backend remains on18002. No original container was recreated.

The infrastructure check asserted unchanged original container IDs, distinct networks/volumes, and identical frozen backend image IDs. The future sequential wrapper joins these independent runs instead of starting duplicate datasets. The report finalizer waits for all three successful results and complete isolation proofs, then stops all simulation services without removing volumes. This changes execution orchestration only; all runs retain28days, GRAND12/day, the same seed, workflow/planner version and business guards. The guide's sequential rerun remains supported. Real elapsed durations in the final table are concurrent campaign durations, not a production latency benchmark.

Monthly results remain pending at this checkpoint; no KPI or successful monthly-isolation claim is made yet.


## UX streamlining Step 8.5 — 25 November 2026

Step 8.5 is implemented and verified locally. The main demo frontend has been rebuilt. This checkpoint does **not** declare all of Phase 8 complete: the three long monthly Step 8.2b runs still need their actual reports. Step 8.6 deployment remains gated, and full Phase 9 remains deferred after the defense.

### User-visible changes and files

- `version.js`, DemoLogin and LabAdminLayout show **Gestion Labo v1.0**. Login instructions no longer suggest unrelated sample accounts. The simulation banner in `main.jsx` now says **Aucun appareil connecté**, replacing the future-feature wording **Machines connectées : prochaine étape**.
- `FilePicker.jsx`, used by DentistPortal and CaseDetails, presents **Choisir un fichier** and **Aucun fichier sélectionné**. It retains the real labelled file input, file type/size handling, required/disabled behavior, keyboard activation and successful-upload reset. The visible button describes the input without duplicating its accessible label.
- `api/contracts.js` and FinanceDashboard keep decimal-string amounts exact with integer cents for formatting, totals and remaining credit ceilings. Existing null/J+1 behavior is retained. Boundary regressions cover amounts beyond floating-point cent precision.
- `demo/prepare_v1_cases.py` adds a new V1 clinic and twelve new synthetic cases through authenticated API commands, never ORM/SQL status edits. `demo/prepare_v1_aging.py` is refused outside Docker verification and creates its own two historical clinics/invoices through normal commands with a process-local fixture clock. `demo/test_prepare_v1_cases.py` checks their refusal guards.
- README, DEMO_GUIDE, ROADMAP and the documentation index describe v1/v2 scope and exact preparation steps. New French `GUIDE_UTILISATEUR.md` has 5–10 instructions per role. `SIMULATION_DESIGN.md` describes the implemented isolated simulator and links its time audit.
- No endpoint, migration, API field or persisted audit-action value was added in this step. Application backend source is byte-identical to the 241-test Step 8.4 checkpoint; among 127 compared Python files only the standalone simulator report's French explanatory copy changed. Machine-local settings were excluded before reading bytes.

### UI audit and fixture evidence

The unfinished-copy audit found no other active placeholder navigation or permanently disabled feature button. Disabled controls still implement working role, busy, required-input, workflow or reservation guards; these were retained. TODO/todo codes and inspection/planning protocol labels are not unfinished user copy. OperationsDashboard is valid UTF-8; its earlier apparent mojibake was terminal rendering. Existing backend strings and their French translation contract remain unchanged.

The successful verification rehearsal created all nine canonical display stages plus overdue, rework and design-pause cases in 192.880 seconds. Main preparation then succeeded in 94.109 seconds, run suffix **856684f9**: V1-COMMANDE, V1-RECEPTION, V1-CONTROLE_ENTREE, V1-MODELE, V1-CONCEPTION, V1-FABRICATION, V1-FINITION_QC, V1-LIVRAISON, V1-CLOTURE, V1-RETARD, V1-REPRISE and V1-DESIGN. All nine server display-stage descriptors were asserted. The overdue confirmed date was accepted by the existing API. The rework has a failed QUALITY inspection, fictitious photo, explicit cause/action and attempt 2 at MODELAGE. The design case is VALIDATION_CAO with its delay paused.

Later-stage snapshots/rework use the supported conventional route; the preparation FAO and design cases use CFAO. These are synthetic presentation positions, not measured manufacturing timings. The separate live suite exercises every equipment-phase acknowledgement. Failed preliminary verification fixture runs were retained: an autonomous-cycle guard rejected direct business advancement, and the fixture was corrected to use the conventional route; another rehearsal correctly stopped after the rework hold until the normal advance command was added. No server guard was bypassed or weakened.

The verification-only aging fixture succeeded with two new 500 MAD invoices in distinct 0–30 and 31–60 day overdue buckets. Dates are relative to the current business date (issued 45/85 days ago, terms 30 days); no existing case or invoice is backdated. A real browser verified the exact cells and captured desktop/mobile evidence. No main November period was closed.

### Checks

| Check | Result |
| --- | --- |
| Frontend unit | 30 passed, command 0.889 s |
| Lint / production build | Passed, 0.773 / 1.636 s; only the permitted App.jsx warning and existing bundle advisory |
| Full mocked Playwright | 83 passed, command 139.759 s |
| Full real-API Playwright | 16 passed, command 282.233 s, correctly isolated cabinet-ui-verification |
| Fixture safety tests | 5 passed, stdlib unittest; refusal occurs before Django/database use |
| Existing backend regression checkpoint | 241 passed at Step 8.4; application source continuity verified, not claimed as a new full run |
| Main Django check / migration drift | Clean; no new migration after 0027 |
| Manual real UI | 1440/390px login/sidebar version, reception queue, shared dossier, keyboard file chooser and no page overflow; no file was uploaded by the read-only smoke |
| Aging UI | Both distinct 500 MAD buckets verified in the verification project |
| Final banner-only copy change | Lint/build passed again, 0.628 / 1.634 s; main frontend rebuilt and rendered copy checked |
| Graphify AST | 2284 nodes, 6736 edges, 113 communities after the final source refresh; no semantic API cost |
| Protected case | MY-TEST-001 and its single standard 1500 MAD line match the Step 8.4 snapshot exactly; November remains open; Atlas identity unchanged |

The first full mocked run caught a duplicated accessible label in the new chooser; the component was fixed and the complete suite rerun successfully. New keyboard regression timing was stabilized by targeting the focused chooser, without weakening existing assertions. Early screenshots captured login animation before settling; stable-ancestor checks produced readable captures.

One live-suite invocation mistakenly set only the verification frontend address and an unused API-port variable, leaving API checks on the main default. It was stopped; any new synthetic BROWSER records it had created were retained. Read-only checks confirmed the protected case, line, original November period and laboratory profile remained unchanged. The final successful run explicitly set all three supported variables: VIRTUAL_LAB_FRONTEND, VIRTUAL_LAB_BACKEND and VIRTUAL_LAB_PROJECT. `playwright.live.config.js` now rejects mixed known demo/verification targets **before any test runs**; an intentional mismatched `--list` invocation verified the rejection. No historical expectation was weakened.

Private evidence is in the dated temporary Step 8.5 folder: logs, nonsecret V1 manifest, protected snapshots, source continuity and screenshots. No .env, runtime credentials/signing key, private-media source file or native PostgreSQL was read. Existing Docker volumes and all prior snapshots are retained. No commit, push or PR.

### Remaining monthly evidence

The normal 28-day run is still progressing on frozen pre-D4 simulator images; Ramadan and mixed follow sequentially. Their report generator refuses incomplete/tiny/failed runs. A guarded temporary finalizer will generate the report/raw JSON and links only after all three successful results and 189 denied cross-tenant attempts per run with zero leaks/unauthorized writes, then stop cabinet-sim without removing volumes and take a separate snapshot. Until that happens, no monthly KPI or completion claim is made. The demo itself is ready for owner testing.




## UX streamlining Step 8.4 - 25 November 2026

D4 is implemented and verified locally. Additive0027 creates the tenant LaboratoryProfile singleton with an id=1 CHECK, optional15-ASCII-digit ICE with API/model/database validation, contact and fiscal fields, and server-attributed last-update metadata. GET is read-only/no-store; MANAGER writes and COMPTABILITE reads. Existing tenant membership is required. Initial PUT creation is serialized under the owning Client row lock.

Newly generated PDFs use an escaped Gestion Labo/name/contact header and optional fiscal footer on every page. Missing or blank profiles fall back to Client.name, including schema_context/FakeTenant callers. Delivery slips retain the patient reference and signed QR; no full-name field existed, so no patient-name change/gate was needed. Stored invoice and credit rows/PDFs remain untouched: tests preserve valid legacy Cabinet 2.0 bytes through profile update, both generation tasks and downloads.

The French identity form is a collapsed section above the existing configuration tabs. It fetches only when expanded by manager/accounting, supports keyboard and390px, preserves leading ICE zeros and failed drafts, and uses the fixed top notification. The browser checks caught double translation replacing an otherwise French ICE message with a generic fallback; the new wording and unit round-trip assertions now preserve the specific explanation. New backend error ICE must contain exactly15digits has its exact French map/test. No persisted metadata action value was added.

| Check | Final result |
| --- | --- |
| New identity backend rules/PDF tests |9 passed, runner7.822s |
| Full Django api/customers |241 passed, runner711.287s / command716.778s |
| Frontend unit |28 passed, command0.820s |
| Lint |Passed,0.635s; only permitted App.jsx effect warning |
| Production build |Passed,1.876s; existing bundle-size advisory |
| Full mocked Playwright |80 passed,137.997s |
| Full real-API Playwright |16 passed,207.549s, separate verification project |
| Django check / migration drift |Clean; additive0027 only |
| Graphify AST |2214 nodes,6576 edges,101 communities |
| Main image source parity |125 files match backend/worker/Beat; machine-local files excluded |
| Protected data |MY-TEST-001 source/one1500MAD line identical; November closed_at remains null |
| Original volumes |All three still created10Nov2026 at20:53:50Z |
| Git |HEAD42f52aa unchanged; no commit/push; diff--check clean |

Main stack check: rebuilt images and applied0027 through Docker bootstrap, then logged in as Demo Manager and used Configuration ? Identité du laboratoire. Saved Laboratoire Démo Atlas, explicitly fictitious address/city, zero phone, demo@example.invalid and ICE000000000000000, leaving optional IF/RC/patente blank. Reopened by keyboard, checked persistence and390px overflow, and visually inspected settled desktop/mobile captures from a new read-only session. The first resize capture caught the off-canvas navigation mid-transition; a stable-layout check confirmed it closes fully and does not obscure fields. No product code change was needed for that capture timing.

Pre0027 dump: snapshot20261125-194810-after-8.2b-implementation/demo-before-0027.dump,2,493,343bytes, SHA2569f3a78442211a78aa9b7d996c4aad4178f8d801ec467d4b144a7c5e57eae4b13; pg_restore--list succeeded. It is outside the repository/OneDrive. Native PostgreSQL was not used.

Existing test expectations were not changed. New tests were appended; their initial contiguous-PDF-byte assertion was corrected to read adjacent WinAnsi text drawing operands. Two preexisting but disallowed frontend warnings were removed: unused sidebar map index, and dashboard mount calling a stateful loader. Dashboard now starts loading in initial state, subscribes directly to an abortable request and retains stale-response protection/manual refresh. All existing dashboard tests pass.

## Step 8.2b implementation checkpoint - monthly evidence still pending

The light simulator code is isolated in new modules/command and compose.sim.yml. Its implementation introduced no changes to existing backend/frontend files compared with the Step8.3 snapshot. Staffing is2/5/10 conception/manufacturing technicians plus one receptionist and one quality operator:4/7/12 planned people. Mini-run isolation had678 assertions and189 denied cross-tenant attempts, with0 leaks/unauthorized writes. Eight simulator tests are included in the full suites.

Longer runs exposed and corrected two synthetic-actor errors without changing production guards: refused future/conflicting starts now wait/replan normally and record diagnostics; conventional quality rework now selects the existing allowed MODELAGE restart instead of MODELE_TRAVAIL. A targeted three-route scenario explicitly exercises every applicable failed gateway and closes all three cases through real commands.

The final implementation full suite passed232 backend tests (662.034s runner/667.201s command), alongside27 frontend unit,75 mocked and15 live tests. Main simulator invocation was rejected by its project/database guard, and all121 implementation Python files matched the main three services. Snapshot20261125-194810-after-8.2b-implementation contains271 files/19,190,351bytes of source evidence.

Three28-day runs are still required before marking8.2b complete: normal, reduced hours and mixed peak/outage, GRAND reduced to12/day and disclosed. They run sequentially in separate cabinet-sim datasets with frozen pre-D4 images (source copied into images, no source bind mount). The runner checks image IDs and uses --no-build for remaining runs; independent D4 work does not enter their load evidence. Functional tiny simulator tests also pass in the latest D4 full suite. No monthly KPI report or successful monthly isolation result is claimed yet.

BPMN matrix scope correction: per the owner's Step8.0 instruction, B8 is covered once v1 payment tracking landed; counts are41 covered/15 partial/1 missing. Real external delivery remains explicitly unverified/disabled. Historical Step8.2 counts below predate this scope correction.

Backup safeguard correction: the earlier snapshot helper copied ignored machine-local settings and agent notes, and the earlier byte comparison included local settings internally. No contents were printed or committed. Future snapshots and source comparisons explicitly exclude local_settings.py and memory.md before reading; Docker already excluded local settings. Both files are untracked. Earlier snapshots remain intact under the brief's retention rule.


## UX streamlining Step8.3 - 25 November2026

Implemented D3 before the final8.2b runs because simulator isolation must cover dashboard/summary. New uncached GET endpoint composes workflow_spec stages, current task risk, delivery deadlines and30-day ReworkCase/delivery counts. Already-delivered cases remain active for fitting without false delivery risks. Current-step BLOCKED tasks and source pauses form a deduplicated total. Ratios return both counts and null when the denominator is zero. No settings are created during reads.

MANAGER gets operations+finance; COMPTABILITE only finance; every other role is denied. Finance reuses existing monthly catalogs (issue-month billed total and latest closed statement-month gross invoices), displays freshness/failure metadata, and uses live payments.receivables for positive balances, over60days and separate overpayments. Money stays exact decimal strings. The response is no-store and never touches shared active_orders cache or emits an audit/action/migration.

French Dashboard.jsx adds KPI tiles, labelled CSS stage bars and paged risk lists opening the shared CaseWorkspace. Nav is visible only to manager/accounting. Manager default remains A faire; the existing accounting billing landing is preserved. The390px layout and keyboard focus return pass. User guide click path and metric definitions are in DEMO_GUIDE and BILLING_ANALYTICS.

| Check | Final result |
| --- | --- |
| New dashboard backend tests |8 passed, command29.576s |
| Full Django api/customers |224 passed, runner544.064s / command549.132s |
| Frontend unit |27 passed, command0.847s |
| Full mocked Playwright |75 passed, command123.544s |
| Full real-API Playwright |15 passed, command180.457s |
| Lint / build |Passed,0.734s /1.677s, existing warnings only |
| Django check / migrations |Clean,0026 unchanged, no new migration |
| Graphify AST |1993nodes,5925edges,97communities |
| Main parity |110files match backend/worker/Beat |
| Protected case / November / volumes |Exact snapshot match; period open; original volumes preserved |

New fixture corrections: use the installed Casablanca offset at the January/February boundary; create/drop temporary tenants in public; evaluate deferred evidence constraints before test-only schema removal. No existing assertions were weakened. The first full mocked run had one unchanged courier timeout; that exact test passed in isolation and the complete75-test rerun passed. All15 live tests passed with no implementation change. Rebuilt main and visually inspected1440px/390px; keyboard opened/closed a case, no overflow/errors and no source or financial writes. Git diff --check passed; user brief remains byte-identical. Disposable test DB removed; verification stopped without-v. Main UI18080/API18000 remain running. No native DB, private-file access, external delivery or Git history changes.

Evidence: TEMP gestion-labo-ux-step83-20261125-_40mhjbl. End snapshot is recorded in the checkpoint. Next: isolated simulator8.2b, then laboratory identity8.4 and v1 finish8.5. Its preliminary clock audit found128 matches; automatic timestamps follow the patch, imported callable defaults need command-local treatment, SQL clocks affect refresh metadata only, QR signatures and cache TTL use wall time (explicit limits). No production clock/guard change has been made.

## UX streamlining Step 8.2 - 25 November 2026

Implemented approved D2: immutable payments, exact allocations, once-only reversals and live receivables. Additive migration0026 adds the three append-only ledgers and clinic payment terms (default60, bounded0..120). Database checks reject invalid/NaN amounts, missing non-cash references and LCN maturity; UPDATE/DELETE/TRUNCATE are blocked. Transactional writes follow clinic billing lock then sorted invoice locks; a stable UUID and body digest give exact replay or409. Concurrent over-allocation is rejected. New persisted actions are RECORD_PAYMENT and REVERSE_PAYMENT. The frozen historical contract is untouched; the sole existing-test expectation extension explicitly allows those two approved Action values.

One bulk Decimal balance function includes credits and active allocations. Negative balances preserve all evidence and appear as Trop-perçu à régulariser, separately from overdue amounts. Casablanca issue dates plus the clinic's current terms determine aging; boundaries are disjoint. Finance reads/writes are MANAGER/COMPTABILITE only; the existing owned dentist invoice path now exposes only its restricted balance fields. No shared catalog schema or clinical state changed. New backend messages have exact French translations/tests.

The French payment dialog supports all four methods, editable oldest-first allocation, optional notes, LCN maturity and a signed-receipt cash hint. A fixed key survives transport retry. After a successful write followed by a read failure, only a read retry is offered. History preserves reversals; the aging table scrolls within a labelled keyboard region at390px. The dentist can explicitly refresh the balance beside the existing PDF.

| Check | Final result |
| --- | --- |
| Full Django api/customers | **216 passed**, runner558.877s / guarded command565.920s |
| Frontend unit | **27 passed**, command0.765s |
| Full mocked Playwright | **71 passed**, command126.374s |
| Full real-API Playwright | **14 passed**, command173.903s |
| Lint / production build | Passed,0.637s /1.907s; existing App effect warning and bundle advisory only |
| Django check / migration drift | Clean;0026 applied in both Docker projects |
| Graphify AST |1956 nodes,5758 edges,97 communities; no paid semantic extraction |
| Main source parity |108 files match backend, worker and Beat |
| Protected case / November | Exact before/after match; period still open; original three volumes preserved |

Twenty new backend tests cover methods, allocation guards, immutability, raw DB checks, aging boundaries, credits/overpayment, role and tenant isolation, owned dentist reads, constant-query serialization, stored PDF bytes, UUID conflict and actual concurrent writes. New fixture mistakes (NaN ORM conversion, tenant SET query counting and public-account cleanup) were corrected; a missing clinic serializer allowlist field exposed by the tests was fixed. The final full suite passes. Four new mocked browser tests and one live test cover save/reversal, retry safety and the dentist view. The guarded standalone live fixture builds only a new historical October verification case through real APIs/commands, closes only its own October period and never runs in the main project. It never prints credentials or PINs.

Main demo rebuilt with retained volumes. Real UI inspected at1440px and390px: payment form opened/closed by keyboard, focus returned, no overflow or browser errors, **zero financial writes** in main. A temporary smoke locator initially used an abbreviated label; corrected only that script. Stored MY-TEST-001 remains CLOTURE, quality validated, one1500 MAD November line. The validated pre-migration dump remains at C:\Users\SetupGame\GestionLabo-snapshots\20261125-134149-after-8.0\demo-before-phase8-migrations.dump (2,440,440bytes). Disposable test DB removed; verification stopped without -v after checks. Main remains running. No native DB, private-file access, external delivery, commit/push/PR.

Coverage remains40 covered /16 partial /1 intentionally omitted E1 among57 BPMN rows: B8 is still partial because external invoice delivery is disabled; payment divergence D2 is resolved separately. Evidence: system TEMP gestion-labo-ux-step82-20261125-abfykkhh. End snapshot recorded in the local checkpoint. Next: implement dashboard8.3 before final simulator8.2b runs, because the simulator must check that endpoint's tenant isolation. Approved D8 staffing totals are4/7/12, including separate reception and quality operators. Deployment, November closing and full Phase9 gates remain intact.

## UX streamlining Step 8.1 - 25 November 2026

Implemented approved D1: advisory capacity before creation, with a clearly provisional earliest date over the existing routes when fabrication has not yet been chosen. `api/capacity.py` uses unsaved prescriptions/tasks and the real route, rules, calendars, qualifications, equipment phases and reservations. Shared `ordered_jobs`/`candidate_slot` were extracted from the scheduler without changing its policy. Known unreserved internal backlog is included; unknown approvals, transport, future work and clinical protocols are not invented. The preview never selects a production method, reserves resources, creates settings, locks rows, emits receipts or blocks creation. Unknown projections return null without a warning. The existing completeness rules remain blocking.

New endpoints: `POST /api/prescriptions/capacity-preview/` for case-creating lab roles/linked dentists, and the tenant-switching dentist gateway `POST /platform/dentist/capacity-preview/`. Response fields: requested_deadline, tri-state feasible, earliest_feasible_date, reason_code, message and provisional. The public gateway checks the selected active lab and the dentist's clinic link, and returns no clinic/staff/case details. The form debounces service, impression, lab and tooth changes, cancels stale results, displays French provisional dates/notices, offers submit-anyway and the next slower service, and suppresses false action-saved notifications for the read-only preview. The existing clinic-ownership error now has an explicit French mapping/test. No persisted action/status, role ownership or migration was added.

| Check | Final result |
| --- | --- |
| Capacity plus existing planning/concurrency tests | **53 passed**, runner 73.286s / command 79.047s |
| Full Django api/customers | **196 passed**, runner 433.379s / guarded command 438.400s |
| Frontend unit | **22 passed**, command 0.667s |
| Full mocked Playwright | **67 passed**, command 110.078s |
| Full real-API Playwright, isolated verification | **13 passed**, command 128.416s |
| Lint / production build | Passed, command 0.564s / 1.474s; existing App effect warning and bundle advisory only |
| Django check / migration drift | Clean on verification and rebuilt main; no new migration |
| Graphify AST update | **1827 nodes, 5289 edges, 85 communities**, no paid semantic/API extraction |
| Main source parity | **102 files** match backend, worker and Beat |
| BPMN matrix | **57 rows**, 40 covered / 16 partial / 1 intentionally omitted E1; **44 test references** validated |
| Protected case / November period | Exact before/after snapshot match; period remains open |

Added 11 backend tests covering feasible/late/closed/unknown/malformed projections, all-route fallback, read-only SQL/settings behavior, permissions, tenant isolation and normal creation despite a warning. Four new mocked browser cases cover a 390px warning/submit, J+1 to J+2 to J+4, unknown projection and transport failure. One new live browser case exercises the real dentist preview/create API on a new synthetic case. No existing test expectation was changed. The first run exposed two new fixture mistakes (hard-coded UTC offset and tenant cleanup context); both were corrected in the new tests, then the focused and complete suites passed.

Rebuilt the main Docker demo. As Demo Dentist, selected the lab/clinic, filled a physical prescription, changed to Express and received a real advisory warning; inspected desktop 1440px and mobile 390px, then submitted by keyboard. New additive case **V1-CAP-cfce0e3f**, UUID `17160bad-998f-40c3-b434-71e43fe217db`, remains on its normal new-case path with no fabrication method. No browser errors or mobile overflow. Main and mocked 390px screenshots were visually inspected. An initial temporary-smoke selector was damaged by Windows pipe encoding; fixing only that temporary script produced the passing 4.668s smoke.

Before any new migration, created and validated `C:\Users\SetupGame\GestionLabo-snapshots\20261125-134149-after-8.0\demo-before-phase8-migrations.dump`, **2,440,440 bytes**, using pg_dump custom format and pg_restore --list. Its hash is in the TEMP evidence metadata; credentials were not printed. Main MY-TEST-001 is unchanged (CLOTURE, validated quality, one standard 1500 MAD November line), its period is still open, and all original 10 November volumes remain. No native database/private-file access or external delivery. Verification is stopped without -v, and the disposable test DB was removed. Main UI 18080/API18000 remain running.

Changed/new source: api/capacity.py, test_capacity.py, planning.py, permissions.py, views.py, customers/views.py and urls.py; DentistPortal.jsx, messages.js/messages.test.js and both browser suites. Updated PLANNING, BPMN_COVERAGE, DECISIONS_V1, roadmap and demo guide. Evidence/snapshots/screenshots/logs: system TEMP `gestion-labo-ux-step81-20261125-dv4ac_ue`, pointer `gestion-labo-step81-path.txt`. The end-of-step snapshot path/size is recorded in the local checkpoint. HEAD remains42f52aa, all work uncommitted/unpushed; no PR. Next: Step8.2 payments. The owner approved preserving post-payment credits as a separate negative balance labelled Trop-perçu à régulariser, outside overdue receivables. Other Phase8 steps remain pending, with deployment/November-closing/full Phase9 gates intact.

## UX streamlining Step 8.0 - 25 November 2026

Read the updated status and approved Phase 8 instructions in `AGENT_PROMPT_UX_STREAMLINING.md`; verified that the Phase 0-7 reports and local source remain present at HEAD `42f52aa`. Recorded D1-D8 in [DECISIONS_V1.md](DECISIONS_V1.md), updated the roadmap/index and clarified the coverage matrix: existing creation completeness makes G1 partial, with advisory capacity still pending 8.1. Current BPMN totals are 40 covered, 14 partial and 3 missing. Payments B8 are not marked complete before 8.2; explicit piece inspection, linked remake cases and role alignment are deferred to v2.

The owner clarified D1 during this step: compare existing routes before a production method is chosen, show the earliest achievable date as provisional, and leave the laboratory's actual planning choice unchanged. No application code, API, action strings, roles, migrations or clinical behavior changed in Step 8.0. No commit, stash, reset, index/ref change, push or PR.

Created the pre-step snapshot outside OneDrive at `C:\Users\SetupGame\GestionLabo-snapshots\20261125-1335-before-8.1`: 236 files, 14,959,566 bytes at creation (excluding its small JSON manifest). Robocopy exit 1 means successful new copies. Secrets/private media/dependencies/build outputs/Git data were excluded; status, diffstat and a tracked patch were saved alongside the working tree. A separate end-of-step snapshot and its exact size are recorded in the local checkpoint.

Docker Desktop was initially off. Started the engine and only the existing demo PostgreSQL container; a temporary backend container executed the previous guarded read-only snapshot helper. MY-TEST-001 exactly matches the complete saved Phase 7 snapshot, including CLOTURE, validated quality and its single standard 1500 MAD November line. No migration, seed/reset, volume removal, native database access or external delivery. Read-only/static documentation checks passed. Full application suites are not claimed as rerun for this documentation-only step; the last verified counts remain 185 backend, 21 frontend unit, 63 mocked and 12 live browser tests and must be rerun for Step 8.1 before continuing to 8.2.

## UX streamlining Phase 7 - 24 November 2026

Added [BPMN_COVERAGE.md](BPMN_COVERAGE.md), linked from the documentation index, README and demo guide. It maps all 37 process elements/terminal destinations and all 20 gateway outcomes to statuses, commands, models, real test methods and the limited manual evidence from MY-TEST-001. G2 explicitly uses Physical/STL outcomes. There are 57 BPMN rows: 40 covered, 13 partial and 4 missing; these are row counts, not a feature-completion percentage. Three global rules and eleven differences have separate rows, with proposed resolutions and approval boundaries. A one-time validation checked every required element/outcome, column count and all 36 distinct file::test references against the source AST.

The matrix preserves the known gaps: no G1 entry-capacity/completeness gate or E1 loop, no payment model, implicit G7 piece conformity, remakes as attempts on the same case, extra application steps, and plaster/scan versus finishing role differences. It also records material-specific thermal enforcement, missing creation notifications/disabled external delivery, the direct resubmission path without a new collection/artifact gate, and failed fitting without a separate failure-result record. These observations did not authorize product changes. MY-TEST-001 covers only the successful physical-CFAO route with design approval, crystallisation, delivery/fitting and an open standard November line; it does not demonstrate exceptions, month closing, invoice delivery or payment.

Added seven real acceptance tests in `api/test_bpmn_acceptance.py`:

- Physical failure/resubmission requires a new revision's inspection.
- Failed model control can recast or rescan, records measured loss without double deduction and requires another model control.
- Requested design corrections retain the hold until version 2 is approved.
- Manufacturing rework keeps the case/lot and records measured waste.
- Failed quality can restart at CAO, CNC preparation or finishing, then requires new attempt-specific evidence.
- Open-period disputes can be accepted/excluded or rejected/restored, preserving urgency pricing and preventing an invoice with no included rows or a credit for an excluded, uninvoiced line.
- An issued-invoice dispute requires accounting permission and a valid bounded amount, creates one credit/PDF, updates net catalogs, rejects editing the issued line and preserves the invoice snapshot across retries.

The existing post-delivery remake test now also verifies that failed fitting neither closes the case nor creates a remake implicitly. All source transitions in these tests use the existing API/commands and guards. Comparing the Phase 6 backend manifest proved that the **only backend file changed was the acceptance-test module**. No application services, UI behavior/strings, API fields/endpoints, roles, statuses, action values or migrations changed.

| Check | Final result |
| --- | --- |
| Focused exception/accounting scenarios | **8 passed**, runner 41.911s, guarded command 46.649s |
| Full Django `api customers` | **185 passed**, runner 436.832s, guarded command 442.257s |
| Frontend `npm.cmd test` | **21 passed**, command 0.773s |
| Mocked Playwright | **63 passed**, command 106.991s |
| Real-API Playwright, separate verification project | **12 passed**, command 124.945s |
| Additional real Reception smoke | **Passed**, 12.878s; desktop 1440px and mobile 390px screenshots visually inspected |
| System checks / migration drift | Clean in verification and rebuilt main; no new migrations |
| Frontend lint / production build | Passed; only the existing App effect warning and bundle-size advisory |
| Matrix references / required rows | All **57 rows**, **20 outcomes** and **36 distinct test references** validated |
| Graphify AST update | **1762 nodes, 5059 edges, 96 communities**; no paid semantic/API extraction |
| Main source/image parity | **100** Python, requirements and contract files match backend, worker and Beat |
| Protected case | Exact before/after snapshot equality for **MY-TEST-001** |

Backend tests used a guarded `call_command('test', 'api', 'customers', interactive=False)` in `cabinet-ui-verification`, asserting simulation, external delivery disabled, database `cabinet_demo`, host `postgres` and disposable test name `test_cabinet_demo` before execution. The test database was removed afterward. Frontend commands were `npm.cmd test`, `npm.cmd run lint`, `npm.cmd run build`, `npx.cmd playwright test --reporter=list --output <TEMP>` and the real suite with `--config=playwright.live.config.js`, verification UI 18081/API 18001/project variables and TEMP artifacts.

The Reception smoke created only **DEMO-P7-f301c5cf** in the verification project, uploaded a synthetic STL and used the real UI to accept, analyse, confirm reception, select Tout conforme and record/advance the intake control. At planning it checked the prefilled date and conventional method's server destination without advancing production. Desktop/mobile screenshots show French top feedback and no horizontal overflow; no browser errors occurred. The full live suite also completed physical-CFAO and digital-3D delivery, fitting and statement flows plus equipment/courier/mobile checks. These browser checks do not claim manual coverage of every BPMN exception.

Main UI 18080/API 18000 were rebuilt and remain available in simulation mode. MY-TEST-001 is unchanged: **CLOTURE**, quality validated, unpaused, original source versions/timestamps/identities and one standard **1500.00 MAD** statement line with zero express surcharge and unchanged contest/exclusion flags. All three main volumes retain their original 10 November 2026 creation timestamps. No volume was removed/reset, no native database/private files were accessed and no external messages were sent. Verification is stopped with its volumes retained; no browser-test Vite listener remains on 5173/5174.

Changed files for Phase 7: new `docs/BPMN_COVERAGE.md`; modified `cabinet_backend/api/test_bpmn_acceptance.py`, `docs/README.md`, `docs/ROADMAP.md`, `docs/TEST_RESULTS.md`, `DEMO_GUIDE.md` and `README.md`. The ignored local checkpoint was updated. Evidence, scripts and screenshots are in system TEMP `gestion-labo-ux-phase7-20261124-osjto21a`, pointer `gestion-labo-phase7-path.txt`. Earlier phase changes and the user's untracked brief are preserved. HEAD remains `42f52aa`; Phases 0-7 are local/uncommitted/unpushed and no PR exists. Phase 8 starts with design notes and user decisions before implementation; Phase 9 remains design-only and device/external-delivery authorization is separate.

## UX streamlining Phase 6 - 24 November 2026

Consolidated the backend without changing the demo flow. `domain.ROLE_STAGES`, `REWORK_ORIGINS`, `MANUFACTURING`, `planning.EXTERNAL`, inspection permissions and `workflow.LABELS` now derive from `workflow_spec`; existing import names remain available. Rework validates the same restart set exposed by the descriptor. Before editing these guards, their literal values were captured in the independent `api/testdata/workflow_contract.json` fixture. Tests compare the consolidated values to that frozen baseline, rather than comparing two derived copies.

Added `Action(StrEnum)` for all 38 existing command-default/audit spellings, including hyphens, explicit underscore overrides, planning actions, `SAVE` and `TRANSITION`. No persisted string was renamed or introduced. In particular a failed delivery-PIN attempt retains `CONFIRM-DELIVERY`, while successful delivery retains `CONFIRM_DELIVERY`. Literal expected JSON values remain in compatibility tests deliberately.

The command registry contains 18 separate handlers; all 12 supported planning commands retain prefix dispatch. Registered roles and unchanged command bodies were compared to their previous ASTs after resolving enum members. The entire `execute_case_command` AST is unchanged, preserving transaction boundaries, billing/source lock order, digest, UUID replay, audit context and omission of a one-time PIN from saved receipts. Validation order and errors remain unchanged. New tests cover validation precedence, specialized dentist permissions, shared audit context, command-source coverage, PIN rotation/retries/disputes and planning estimate/reschedule aliases. No registered or supported planning command is exempt from source-coverage checks.

Added the DB-free `export_workflow` management command and `workflow_diagrams.py`. The generated `docs/WORKFLOW.md` contains six Mermaid route families and dashed rework, intake return/resubmission and design-change edges. Conformance covers all 24 physical/digital, method, design-review and thermal-treatment combinations (2 x 3 x 2 x 2), inspection/confirmation metadata and step ownership. A regression test compares the repository document with deterministic generated output. `compose.verify.yml` mounts documentation read-only for that check; presentation packaging is unchanged.

| Check | Final result |
| --- | --- |
| Full Django `api customers` | **178 passed**, runner 406.723s, guarded command 411.920s |
| Frontend `npm.cmd test` | **21 passed**, command 0.718s |
| Mocked Playwright | **63 passed**, command 106.360s |
| Real-API Playwright, separate verification project | **12 passed**, command 121.603s |
| Additional real Reception smoke | **Passed**, 11.604s; desktop 1440px and mobile 390px screenshots visually inspected |
| Django system checks / migration drift | Clean in verification and rebuilt main; no new migrations |
| Frontend lint / production build | Passed; only the existing App effect warning and bundle-size advisory |
| Graphify AST update | **1747 nodes, 4909 edges, 95 communities**; no semantic/API extraction |
| Main source/image parity | **100** Python, requirements and frozen-contract files match backend, worker and Beat |
| Protected case | Exact before/after snapshot equality for **MY-TEST-001** |

The first focused run passed 18/19 tests. Its new audit assertion incorrectly selected the latest UUID rather than the latest creation timestamp; correcting that test selector resolved it in the full 178-test run. No production behavior change was needed.

Backend tests ran through a guarded `call_command('test', 'api', 'customers', interactive=False)` on `cabinet-ui-verification`, asserting simulation, external delivery disabled, database `cabinet_demo`, PostgreSQL host `postgres` and disposable test name `test_cabinet_demo` before execution. The test database was removed afterward. Frontend commands were `npm.cmd test`, `npm.cmd run lint`, `npm.cmd run build`, `npx.cmd playwright test --reporter=list --output <TEMP>` and the real suite with `--config=playwright.live.config.js`, verification UI18081/API18001/project environment variables and TEMP artifacts.

The additional Reception browser smoke created only **DEMO-P6-8372afa5** in the verification project, uploaded a synthetic STL, accepted, confirmed analysis/reception, selected Tout conforme and recorded/advanced the intake control. At planning it verified a prefilled date and the conventional method's server-provided destination without advancing production. Desktop/mobile screenshots show the workspace and French top feedback; no browser errors or horizontal overflow occurred. The twelve real tests also passed physical-CFAO and digital-3D delivery/fitting/statement flows, equipment phases, courier privacy and mobile navigation.

Main UI 18080/API 18000 were rebuilt and respond in simulation mode. MY-TEST-001 remains **CLOTURE**, quality validated, unpaused, with its original version/timestamps/identities and exactly one 1500.00 MAD standard statement line, zero express surcharge and unchanged contest/exclusion flags. All three original main volumes retain their 10 November 2026 creation timestamps. No volume was deleted/reset, no native DB/private files were accessed, and external message delivery stayed disabled. Verification is stopped with its volumes retained; no browser-test Vite listener remains on 5173/5174.

Phase 6 modified backend `case_commands.py`, `domain.py`, `planning.py`, `workflow.py`, `workflow_spec.py`, `billing.py`, `signals.py`, `test_workflow_spec.py`, `test_bpmn_acceptance.py` and `test_planning.py`. New files are `api/workflow_diagrams.py`, `api/management/commands/export_workflow.py`, `api/testdata/workflow_contract.json` and `docs/WORKFLOW.md`. The verification override, README, demo guide, documentation index, planning notes and roadmap were updated. No frontend application code changed in this phase; no new API fields/endpoints, UI strings, persisted actions, roles or statuses were introduced.

Evidence and before/after snapshots: system TEMP `gestion-labo-ux-phase6-20261124-6opg5c8l`, with pointer `gestion-labo-phase6-path.txt`. The user brief is unchanged. Phases 0-6 remain local/uncommitted/unpushed at HEAD `42f52aa`; no PR. Phase 7 is the next separately requested task; Phases 8/9 and device/external-delivery gates remain unchanged.

## UX streamlining Phase 5 - 24 November 2026

Removed the unused `ProductionWorkflow`/`ProductionCard`, `BpmnCasePanel` and standalone `PlanningProgress` modules, including the old diagram and their duplicated workstation permissions, courier-stage set, advancement checks, rework/restart choices and instructions. Graphify plus repository reference searches showed that their only imports were within that obsolete group; the remaining reference was a comment. Equipment controls remain in the active CaseActions workspace. No active caller or behavioral assertion was removed.

Removed the browser case-status dictionary. Case displays now choose the server current-step, status or detailed-route label, with a French missing-label message. Non-workflow protocol/task labels remain localized. The courier serializer needed one additive read-only `status_label`, using the existing backend workflow labels; its restricted fields, permissions and command behavior remain intact. Preview fallback labels stay inside `api/preview.js`; fixtures now also include a planning example with destinations and grouped stage steps. The preview continues to reject writes.

Before deleting legacy UI, a guarded **read-only transaction** in the presentation schema `simlab` counted49 cases: **0** with `intake_version < 2`, **0** at `FRITTAGE_9H`, **0** matching either condition. Therefore the legacy quality checkbox and hardcoded frittage UI references were removed without a manager-only fallback. Backend legacy branches in `workflow.py`, `domain.py` and the workflow specification remain unchanged. ROADMAP.md records the separate native-data inventory/migration follow-up; no native database was inspected or changed.

| Check | Final result |
| --- | --- |
| Full Django `api customers` | **169 passed**, runner 409.469s, command 415.024s |
| Frontend unit | **21 passed** |
| Frontend lint / production build / preview build | Passed; only the existing App effect warning and bundle-size advisory remain |
| Mocked-API browser | **63 passed**, command 106.917s |
| Real-API browser | **12 passed**, isolated verification project, command 114.959s |
| Actual `npm.cmd run demo` browser smoke | Passed: workspace/stages/planning, French read-only rejection, retained drafts, unchecked criteria and390px layout; no real API calls |
| Obsolete exports/rules/legacy UI references | None remain in frontend source/tests |

The two new backend tests check read-only labels for every existing status, the exact restricted courier fields, and actual authenticated list/command responses without clinical/private fields. The added frontend unit test checks server label precedence and a missing-label fallback. A new mocked courier test and a new real courier screen check prove server labels reach the UI. Existing UUID/payload, explicit criteria, French notification, draft retention, QR/PIN clearing, mobile/focus and physical/digital delivery/fitting/single-line billing assertions remain. Initial courier mocks changed only `status`, leaving stale full-case descriptors; they now match the actual restricted courier response and update its label. Initial preview diagnostics counted both the stage strip and the collapsed detailed route; scoping the assertion to the strip resolved that diagnostic. No production guard or assertion was relaxed. The preview390px screenshot was inspected visually.

Commands follow the Phase 0 block below. Backend regression and real browsers used the separate verification stack with its guarded simulation-only Docker PostgreSQL/disposable `test_cabinet_demo`. Preview testing launched `npm.cmd run demo` on5174, opened the planning and quality examples, verified rejected writes/drafts/layout, then stopped only its own server. Logs/artifacts, reference proofs, read-only legacy counts and protected-case snapshots are in system TEMP under `gestion-labo-ux-phase5-20261124-*`. No application schema, role, status, command, persisted action or backend legacy rule changed in this phase.

The main demo was rebuilt with the cleanup; Django checks/migration drift, source/image hashes, service health and the protected-case comparison passed. MY-TEST-001 retains its exact closed/quality/unpaused state, single1500.00 MAD statement line, zero Express surcharge and unchanged IDs, versions, timestamps and billing flags. Main volumes retain their 10 November creation time, external delivery stays disabled and native/private data remain untouched. Verification services were stopped with volumes retained; the main demo remains running at localhost18080. Graphify was refreshed using AST-only extraction. HEAD remains42f52aa; Phases0-5 are local/uncommitted/unpushed, with no PR. Phase6 has not started.

## UX streamlining Phase 4 - 24 November 2026

Implemented the approved fewer-gesture actions. **Accepter et analyser** uses the new reception/manager `accept` command to set acceptance through the existing serializer and open analysis atomically. Acceptance timestamps, planning generation, durable planning/cache events, read-version invalidation and `ACCEPT` audit metadata are retained; PATCH acceptance and accepted legacy requests still work. Analysis/reception now use one explicit confirmation button. Reception retains a collapsed inspection/non-conformity path; its passing inspection cannot skip reception confirmation.

`inspection` accepts an optional strictly boolean `advance`. Passing intake/model/quality checkpoints can insert evidence, set final-quality validation and advance through the normal linear domain save, in one transaction/idempotency receipt. Transition ownership is checked before evidence insertion. The new persisted history/event action is **`INSPECTION_ADVANCE`**. `sync_order` completes the checkpoint's existing task. Pauses and autonomous equipment guards still reject/roll back; no migration, role/status change or guard bypass was added. Without the flag, the original record-only behavior and two-field result remain unchanged. With the flag, the result also includes `advanced` and `status`; at A_CONFIRMER it records without advancing. Failed intake returns the case; failed model/quality stays at its checkpoint.

Criteria start unchecked. **Tout conforme** changes only local criteria, sends nothing and leaves the independent photo-gap flag unchanged. Unticking switches to non-conformity; reason presets never select criteria. Passing submission includes every criterion and `advance: true`. Failed model/quality evidence offers **Documenter la reprise**, which opens/focuses the required corrective-action form without submitting it. Work keeps planning start/finish or equipment acknowledgements; manager-only forced advancement is under problems, requires a reason and uses the existing guarded command.

PLAN metadata now supplies viewer-independent `planning_options` derived from the real server route, avoiding client destination guesses or writes on selection. Cache shape `workflow-step-v2` invalidates older envelopes. Delivery-date prefill uses the backend's Casablanca timezone transitions; saved dates/user edits take precedence, an absent deadline requires manual entry, and missing J+1 quotes show a waiting notice. New server errors are mapped into French.

| Check | Final result |
| --- | --- |
| Full Django `api customers` | **167 passed**, runner 383.656s, command 388.987s |
| Django system check / migration drift | No issues / no changes detected |
| Frontend unit | **20 passed** |
| Frontend lint / production build / read-only preview build | Passed; only the pre-existing App effect warning and bundle-size advisory remain |
| Mocked-API browser | **62 passed**, command 104.886s |
| Real-API browser | **11 passed**, isolated verification project, command 97.833s |
| Main active-list/descriptor/cache smoke | Passed; shape current, closed protected case absent |
| Protected case and statement line | Exact before/after snapshot match |
| Main application images | 97 Python/requirements files matched backend, worker and Beat |
| Main HTTP/environment/volumes | Frontend200/SIMULATION; external delivery disabled; original volume creation times retained |

Eleven added backend tests cover all four inspection stages/three checkpoints, legitimate owners, non-owner rejection without evidence, strict flag typing, reception record-only behavior, paused rollback, configured autonomous-task rollback, old result compatibility, failed-inspection routes, audit/task completion, atomic acceptance effects/permissions/preconditions/retry/PATCH compatibility, and server-derived method destinations without source mutation. The twelve added mocked browser tests cover the shortcuts, local-only bulk selection and unticking, gap independence, exact criteria/UUID payloads, reception failure, explicit rework focus, backend timezone/route labels, manual-date/quote waits and manager-only forced advancement. Existing behavioral assertions remain. The real suite adds UI acceptance/analysis and runs quality validation/advancement through real browser clicks in both physical-CFAO and digital-3D end-to-end workflows, retaining delivery/fitting/single-statement-line assertions.

Reviewed migration0022's status-version/deferred-history triggers and immutable evidence triggers, plus0024's task-history trigger. Evidence inserted earlier in the same transaction satisfies the normal domain inspection lookup; passing integration tests verify the audited source/task saves under PostgreSQL. The first focused run rejected the new autonomous-task test fixture because setup+unload equalled its whole duration; the fixture was corrected to leave positive cycle time. The first real-browser run waited on destination text already present in the quality button and checked status before commit; it now waits for the committed server status. These were test setup/synchronization corrections; no production guard or assertion was relaxed. Full backend and real-browser reruns passed. The mobile shortcut/notification screenshot was inspected visually.

Commands follow the Phase 0 block below, using the separate verification stack for both backend regression and real browsers. The focused command was `python manage.py test api.test_bpmn_acceptance api.test_workflow_spec --noinput`; the final full command was `python manage.py test api customers --noinput`. Real browsers used the same three verification environment overrides with `--config=playwright.live.config.js --reporter=list` and TEMP artifacts. Logs/snapshots/artifacts are in system TEMP under `gestion-labo-ux-phase4-20261124-*`. Tests used guarded synthetic Docker PostgreSQL/disposable `test_cabinet_demo`, never native PostgreSQL/private media. The regression database was removed. Verification services were stopped with volumes retained; the main demo remains running at localhost18080.

MY-TEST-001 remains CLOTURE, quality validated and unpaused, with the identical single 1500.00 MAD statement line, zero Express surcharge and unchanged IDs, version/revision/attempt, timestamps and billing flags. All three main volumes retain their 10 November creation time. The guide, planning notes, roadmap and local checkpoint describe Phase 4; Graphify was refreshed with AST-only extraction. HEAD remains42f52aa; Phases0-4 remain local/uncommitted/unpushed, with no PR. Phase5 has not started.

## UX streamlining Phase 3 - 24 November 2026

Implemented the shared `CaseWorkspace.jsx` on the existing native ActionDialog. Queue rows, order cards, dentist cases and planning task drawers now open this workspace. Its header lists all teeth/materials/shades and case context; server metadata drives the read-only stage strip and current action. One primary action is shown for an eligible actor; ownership, assignment, dependency, future-slot, external and closed states have French explanations. Risk comes from the server queue, with an explicit unavailable/closed label when that viewer has no matching entry.

Collapsed **Signaler un problème** retains case/task pause or block, documented rework using server restart choices, measured losses and workstation remarks. Collapsed **Dossier** retains private documents, QR/PDF/PIN issuance, design history, explicit information saves, J+1 quotes, inspection evidence, the full route and planning history. The dentist uses cabinet-only controls and never fetches laboratory planning. The planning assignment drawer retains its supervision/resource/lock controls and opens the same clinical workspace. The old BPMN/production exports remain for Phase 5, but no active case entry point uses the former three-tab dialog or stage drag/drop.

Acceptance and advancement remain separate commands. Inspection criteria stay unchecked until selected; saved passing evidence is matched to its actual revision/attempt before the existing separate advancement button appears. Reinspection explicitly opens a fresh unchecked form. Design decisions, delivery PIN, fitting, cycle completion and unloading retain their explicit controls. A manager selects supervision and supplies a reason before the single start button sends the existing `start_now` option. No combined command, automatic approval, default date, source guard, role/status/action change or migration was introduced. French notifications stay above the dialog, failures preserve drafts, and a committed write followed by a refresh failure blocks another mutation until refreshed.

| Check | Final result |
| --- | --- |
| Full Django `api customers` | **156 passed**, runner 333.402s, command 337.920s |
| Focused planning concurrency | **3 passed**, runner 11.961s |
| Django system check / migration drift | No issues / no changes detected |
| Frontend unit | **20 passed** |
| Frontend lint / production build | Passed; only the existing App effect warning and bundle-size advisory remain |
| Mocked-API browser | **50 passed**, command 84.343s |
| Real-API browser, final rebuilt images | **10 passed**, separate verification project, command 79.727s |
| Read-only preview build | Passed (`npm.cmd run build -- --mode demo`) |
| Main demo HTTP / services | Frontend200, API200/SIMULATION, backend/PostgreSQL/Redis healthy |
| Protected case and statement line | Exact before/after snapshot match |
| Main application image/source match | 97 Python/requirements files matched backend, Celery worker and Beat |

Four new unit tests cover current task generations/revisions, inspection evidence, waiting/readiness reasons and descriptive step ownership. The browser suite gained 21 tests covering primary-action counts for each kind and equipment phase, collapsed exception/details sections, waiting states, all teeth and read-only stages at390px, assignee/future blocks, dentist decision/PIN flows without planning access, a committed-write/failed-refresh retry guard, unmodified free-text/empty audit notes and planning-drawer focus return. Existing UUID/payload, QR/PIN clearing, French feedback position, reason draft, unchecked inspection, desktop/mobile and real workflow assertions remain. The two former screenshot paths inside `.runtime` now use Playwright's output path. The mobile header and feedback screenshots were inspected visually.

The initial full backend run exposed an existing test-driver compatibility issue in the raw concurrent GiST insertion test: psycopg2 reports SQLSTATE through `pgcode`, while the test checked only `sqlstate`. The test now accepts the same exact expected deadlock code `40P01` through either attribute. It still requires exactly one committed insertion, one rejection and one persisted reservation. No production database/planner behavior or assertion was relaxed. The three concurrency tests and the complete 156-test suite then passed.

Commands follow the Phase 0 block below, with unit/lint/build and mocked Playwright rerun after the final navigation/history edits. Real browsers used `VIRTUAL_LAB_FRONTEND=http://localhost:18081`, `VIRTUAL_LAB_BACKEND=http://127.0.0.1:18001`, `VIRTUAL_LAB_PROJECT=cabinet-ui-verification`, `--config=playwright.live.config.js --reporter=list`, and a TEMP output directory. Logs, read-only snapshots and artifacts are in system TEMP under `gestion-labo-ux-phase3-20261124-*`. Backend tests used guarded simulation-only Docker PostgreSQL and disposable `test_cabinet_demo`, which the runner removed. Native PostgreSQL, private runtime data and media were not used for testing; external delivery remains disabled.

MY-TEST-001 remains CLOTURE, quality validated and unpaused, with the identical single 1500.00 MAD statement line, zero Express surcharge and unchanged version/revision/attempt, timestamps, line identity and billing flags. All three main volumes retain their 10 November creation timestamp. Verification services were stopped with volumes retained; the main demo remains running at localhost18080. The demo guide, planning notes, roadmap and local checkpoint now reflect Phase 3. Graphify was refreshed with AST-only extraction. HEAD remains42f52aa; Phases0-3 are local, uncommitted and unpushed, with no PR. Phase4 has not started.

## UX streamlining Phase 2 - 24 November 2026

Added uncached tenant-local `GET /api/work-queue/`, paginated with the existing BusinessPagination (50 default, 200 maximum per response). It calculates ownership, assignment, external waiting, case pauses and unquoted J+1 work per authenticated user. Manager workstation filters and patient/dentist search run on the server. Existing planning risk/deadline rules determine ordering. Case/task/dependency reads are batched; the query count stays constant from one to 13 cases and is bounded at 10 statements including tenant middleware/search-path work. GET does not write, create planning settings or cache personal permissions.

The assignment permission helper is shared with TaskSerializer. It grants the same assignment capability as before; it does not imply task readiness. Future bookings/dependencies show French explanations and a planning link. CYCLE/AWAITING_UNLOAD remain in **En attente**, with the assigned operator's explicit confirmation/unloading action still accessible. Paused cases open the controls needed to resume. Accepted legacy DEMANDE_RECUE cases retain a path to analysis. Since no subscription model exists, laboratory staff can follow their lab's external handoffs; accounting sees only its relevant unquoted J+1 cases.

New WorkQueue.jsx is the laboratory landing page, except accounting retains billing. Four groups show counts, case/stage, dentist, urgency, deadline/risk and pause/wait reasons. Each row has one primary button opening the existing case dialog on the relevant section. Search, manager filtering, 15-second/focus/visibility refresh, French feedback, empty state and 390px layout are covered. The dentist has shortcuts for design review, delivery PIN, fitting and returned intake, focused on the explicit control without submitting it. The read-only preview has static examples of the new response. Full workspace replacement and combined acceptance remain later phases; existing guards and decision/command flows are preserved.

| Check | Result |
| --- | --- |
| Full Django `api customers` | **156 passed**, runner 351.379s, command 356.387s |
| Final focused queue suite | **12 passed**, runner 53.706s, command 58.347s |
| Django system check / migration drift | No issues / no changes detected |
| Frontend unit | **16 passed** |
| Frontend lint / production build | Passed; only the existing App effect warning and bundle-size advisory remain |
| Mocked-API browser | **29 passed**, runner 49.6s |
| Final dialog/focus checks after lint cleanup | **3 passed**, runner 5.5s |
| Real-API browser | **10 passed**, separate verification project, command 76.12s |
| Main demo HTTP / permissions smoke | Queue returned 29 active rows; closed MY-TEST-001 absent; frontend200/SIMULATION |
| Protected case and statement line | Exact before/after snapshot match |
| Main images / Graphify | 97 application Python/requirements files matched all three application services; AST refresh passed |

The 12 new backend tests cover reception/legacy acceptance, CAO/quality ownership, FAO assigned/unassigned/other-account work, Django and platform employee identity, J+1 quote filtering, manager role filters, external and machine waiting, future starts, rework action hints, risk/deadline/service ordering, search/pagination, per-user responses, actual second-schema isolation, anonymous/foreign/courier denial, method restrictions, read-only behavior and constant query count. Fixtures reach source stages through real workflow commands and retain audit/evidence/immutability guards. The shared delivery fixture gained an optional stop checkpoint; its default remains LIVRE. Existing browser assertions were retained, with two dashboard tests explicitly navigating from the new landing page.

Full regression passed before the final small rework action-hint correction (ready tasks start; paused/blocked tasks resume). The complete queue suite was then rerun successfully against rebuilt images. Frontend lint cleanup was followed by production build and the affected focused browser checks. No source guard, status, role, persisted action, migration or clinical evidence requirement was changed.

Commands use the Phase 0 block below; focused backend: `python manage.py test api.test_work_queue --noinput`. Real browsers used the same three verification environment overrides. Logs/artifacts are in system TEMP under `gestion-labo-ux-phase2-20261124-*`, outside the private runtime folder. Test runs used guarded synthetic Docker PostgreSQL and disposable `test_cabinet_demo`; native PostgreSQL was not used. The verification project was stopped with its volumes retained. Main demo services remain running, all three main volumes retain their 10 November creation time, external delivery remains disabled, and no browser-test dev server remains.

MY-TEST-001 remains CLOTURE, quality validated and unpaused with the identical single 1500.00 MAD statement line, zero Express surcharge and unchanged version/revision/attempt, timestamps and billing flags. The guide, planning notes and roadmap now reflect the new entry points. Phases 0-2 remain local and uncommitted at HEAD42f52aa; no push or PR. Next is UX Phase 3.

## UX streamlining Phase 1 - 24 November 2026

Implemented the declarative `api/workflow_spec.py` alongside the existing runtime guards. It covers all 35 statuses, nine display stages, step kinds, legacy workstation ownership, inspection tracks and rework/manufacturing/external flags. Compatibility tests compare labels, role maps and guard sets with the unchanged originals, including the inspection command's actual local permission literal. Existing guard constants and `workflow.LABELS` remain in place until the planned consolidation phase.

The shared prescription serializer now adds read-only, viewer-independent `current_step`, `stages` and `rework_restart_options`. Route descriptions retain physical/digital, CFAO/3D/conventional, optional design/thermal and legacy behavior; rework grouping does not mark a future restart stage done. Existing `workflow_steps`, `next_status`, `status_label`, transitions, commands and audit action strings remain compatible. No model/status/role changes, migrations, new error strings or new persisted actions. No frontend screens or locators changed; the new French display-stage labels are metadata for later UX phases.

The tenant-shared active-list cache now requires both read generation and shape `workflow-step-v1`, refreshing envelopes with missing/older shapes. Per-user task permissions are not cached in the descriptors. The dentist portal already uses the shared serializer; passing its request context on list/create/retry responses also restores the existing internal workstation-note filtering there. New tests cover ownership and note privacy without exposing task assignments or credentials.

| Check | Result | Command wall time |
| --- | --- | --- |
| Focused workflow spec/CQRS/dentist privacy | **23 passed**, runner 28.619s | 33.997s |
| Full Django `api customers` regression | **144 passed**, runner 296.141s | 301.143s |
| Django system check | No issues | 1.575s |
| Migration drift | No changes detected | 1.782s |
| Frontend unit | **14 passed** | 0.761s |
| Frontend lint | Exit0; existing App.jsx:63 effect warning | 0.650s |
| Production frontend build | Passed; existing bundle-size advisory | 2.018s |
| Mocked-API browser | **24 passed**, runner 47.3s | 48.962s |
| Real-API browser | **9 passed**, separate verification project | 72.226s |
| Saved-demo HTTP/Redis metadata smoke | Manager and dentist descriptors/note filtering passed; cache shape current | Passed |
| Protected case/line snapshots | Exact before/after match | Passed |
| Graphify AST refresh | Passed; no LLM extraction | Passed |

Thirteen new backend tests cover guard/spec parity, applicable route stages and treatment labels, inspection-track selection, allowed rework choices, legacy/terminal cases, read-only/query-free metadata, physical-CFAO/digital-3D serialized responses, stale cache rejection, cross-viewer metadata consistency and dentist case/note privacy. No existing behavioral assertion was removed or weakened. Complete automated suites passed without application fixes after the focused run. Auxiliary diagnostic helpers were corrected for valid empty logout responses and Windows console Unicode; only those diagnostics were repeated, with no application change.

Commands follow the Phase 0 block below. The focused command ran on the dedicated `cabinet-ui-verification` backend: `python manage.py test api.test_workflow_spec api.test_cqrs customers.tests.PlatformTests.test_dentist_receives_workflow_descriptors_without_other_cases_or_workstation_notes --noinput`. Full Django regression/checks ran on the rebuilt main demo backend; both use guarded simulation-only Docker PostgreSQL and disposable `test_cabinet_demo`, never native PostgreSQL. Frontend commands were `npm.cmd test`, `npm.cmd run lint`, `npm.cmd run build`, `npx.cmd playwright test --reporter=list` and the separate-project `--config=playwright.live.config.js` run with the same three environment overrides as Phase 0. Browser outputs/logs stayed in the system temporary directory (`gestion-labo-ux-phase1-20261124-*`).

All 95 backend Python/requirements files, including the new modules, matched source in rebuilt backend/worker/Beat containers. MY-TEST-001 remains CLOTURE, quality validated, unpaused and linked to the identical single 1500.00 MAD statement line; case version/revision/attempt, timestamps, price and line flags also match the read-only baseline. Regression databases were removed by their runners. No volume was deleted or reset, native PostgreSQL/private files were untouched and external delivery remained disabled. Main HTTP200/SIMULATION/database health passed. Verification services were stopped with volumes retained; main demo stays running. No browser-test dev server remains.

New source files: `api/workflow_spec.py`, `api/test_workflow_spec.py`. Updated implementation/tests: `api/case_serializers.py`, `api/views.py`, `api/test_cqrs.py`, `customers/views.py`, `customers/tests.py`. Updated maintained docs: this report, `PLANNING.md` and `ROADMAP.md`. Presenter click paths are unchanged in this backend-only phase. HEAD remains `42f52aa`; Phase 1 changes are local and uncommitted. No push or PR. Phase 2's personal work queue is next; the later product-decision/simulator gates remain separately scoped.

## UX streamlining Phase 0 baseline - 24 November 2026

Baseline revision: `42f52aa814419d62d1786b68af49ff5c54a8df23`, branch `feat/virtual-lab-demo`. Initially the only shared working-tree addition was the untracked `AGENT_PROMPT_UX_STREAMLINING.md`. Phase 0 changes no application source, behavior, UI strings, API fields, persisted action values or migrations. This section records the baseline before Phase 1.

Started the existing `cabinet-virtual-lab` environment with its saved volumes. A read-only transaction confirmed MY-TEST-001 was CLOTURE, quality validated, unpaused and linked to exactly one 1500.00 MAD statement line with zero Express surcharge. The saved image differed from source in settings and the diagnostic command, so application images were rebuilt. All 93 tracked backend Python/requirements files then matched the working tree in backend, worker and Beat containers.

| Check | Result | Command wall time |
| --- | --- | --- |
| Django system check | No issues | 1.407s |
| Migration drift | No changes detected | 1.517s |
| Full Django `api customers` regression | **131 passed**, runner 293.392s | 298.559s |
| Frontend unit | **14 passed** | 1.027s |
| Frontend lint | Exit0; existing App.jsx:63 effect warning | 0.700s |
| Production frontend build | Passed; existing bundle-size advisory | 8.440s |
| Mocked-API Playwright | **24 passed**, runner 50.6s | 65.474s |
| Real-API Playwright | **9 passed**, separate verification project | 68.519s |
| Protected case after all tests | Exact match with the before snapshot | Passed |
| Main HTTP/environment | Frontend200, SIMULATION, database reachable | Passed |
| Graphify AST refresh | Passed, no LLM extraction | Passed |

The real suite used `cabinet-ui-verification`, frontend18081/API18001 and its own existing volumes. Both physical and digital routes reached delivery/fitting/statements; explicit equipment phases and mobile navigation passed. The mocked suite retained desktop/390px dialog, notification, focus, reason-draft and idempotency assertions. These are baseline tests of the existing interface; the proposed new UX and its manual walkthrough are not implemented in Phase 0.

Commands, from the repository root unless indicated:

```powershell
$phase0Logs = Join-Path $env:TEMP 'gestion-labo-phase0-20261124-143956'
docker compose -p cabinet-virtual-lab -f compose.demo.yml exec -T backend python manage.py check
docker compose -p cabinet-virtual-lab -f compose.demo.yml exec -T backend python manage.py makemigrations --check --dry-run
docker compose -p cabinet-virtual-lab -f compose.demo.yml exec -T backend python manage.py test api customers --noinput
# From cabinet_frontend:
npm.cmd test
npm.cmd run lint
npm.cmd run build
npx.cmd playwright test --reporter=list --output="$phase0Logs\mocked-artifacts"
# With VIRTUAL_LAB_FRONTEND=http://localhost:18081,
# VIRTUAL_LAB_BACKEND=http://127.0.0.1:18001 and VIRTUAL_LAB_PROJECT=cabinet-ui-verification:
npx.cmd playwright test --config=playwright.live.config.js --reporter=list --output="$phase0Logs\live-artifacts"
```

No application test failures occurred. The backend's logged `OSError: Broker down` was the existing intentionally mocked recovery scenario; the suite finished OK. An initial PowerShell logging wrapper treated normal Docker stderr progress as an error during rebuilding; running images were subsequently verified against source, and regression commands captured native exit codes directly. No application changes were made to obtain passing results.

Before/after read-only snapshots matched for case status, flags, attempt/revision/version, timestamps, price and statement-line identity/amounts/flags. The runner removed its disposable `test_cabinet_demo` database. No Docker volume was removed or reset; all three main volumes retain their 10 November creation timestamp. Native PostgreSQL and private files were untouched, and external delivery remained disabled. Verification services were stopped with volumes preserved; the main demo remains running at localhost18080. No browser-test dev server remains. Logs and artifacts were saved outside the repository under the system temporary directory (`gestion-labo-phase0-20261124-*`). No commit, push or PR was performed. Phase 1 is next; no baseline failure blocks it.

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
