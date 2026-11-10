# Resume here — virtual laboratory checkpoint

Paused at the user's request on 10 November 2026. **Do not publish anything until the user requests it again.**

## Current branch and source

- Branch: `feat/virtual-lab-demo`, based on collaborator main `d5a8c7f`.
- Foundation commit: `77235bf` (isolated Docker demo).
- A subsequent local checkpoint saves browser tests, test reports and this resume note. Neither checkpoint was pushed; the attempted foundation push was declined.
- Earlier `MODEL_HANDOFF.md` describes the November4 remediation baseline. This note, `VIRTUAL_LAB_PLAN.md` and `DEMO_TEST_RESULTS.md` describe the current simulation work.
- Use root `graphify.cmd` before code exploration and update the local graph after code changes. Graphify is isolated in `.graphify-venv`; current local graph has1463 nodes/3713 edges.

## User's intended architecture

Demonstrate the real application's production planning with synthetic equipment events, then replace simulator adapters with vendor adapters later. Shared workflow, scheduling, audit and validation belong to the production app. Only synthetic fixtures, scenario controls and device-event sources are demo-specific.

Steps1–2 complete: architecture inspection and reproducible real-API Docker environment. Steps3–6 remain: separate human/machine resource periods, shared device-event contract/adapters, simulator scenarios and verified portable presentation.

## Fix these two confirmed blockers first

1. **CORS:** browser workflow writes include `Idempotency-Key`, but Django's allowed CORS headers omit it. Preflight returns200 while Chromium blocks the actual POST and UI displays `Network Error`. Extend allowed headers while preserving defaults. The live preflight regression should become green.
2. **Route selection:** `api/case_commands.py` calculates `next_status(order)` before applying proposed `production_method`. At PLANIFICATION, selecting IMPRESSION_3D and advancing in a single request produces a destination inconsistent with the new route; domain guards return400. Derive the destination from validated proposed route fields while retaining permissions, audit and transition guards. PATCH route/date then advance works as a two-request workaround, but the normal combined command remains broken.

Do not weaken tests/guards to make these pass. User authorized testing, not fixing, in the last testing turn; ask/receive a continuation instruction before implementation.

## Verification already completed

- 39 targeted backend tests passed: `api.test_planning`, `api.test_bpmn_acceptance`, `customers.test_simulation`. Tests used a separate temporary database inside the isolated demo PostgreSQL service.
- Real demo smoke command passed: seed idempotence, HTTP authentication/tenant reads/access denial, CORS origin and live Redis/Celery/catalog refresh/result retrieval.
- Actual Chromium checks passed for manager cases/planning/workload/settings, mobile menu/planning and dentist-owned case list.
- Browser route-selection test fails with400; browser human start/pause/resume/complete scenario is blocked at start by the missing CORS header. Remaining operator actions were not reached. Explicit preflight regression also fails as expected.
- Initial selector errors were corrected and relevant scenarios rerun. Do not present those test mistakes as application defects.
- No mocked API responses were used in the new live suite. Existing browser contract tests use mocks and are separate.
- Full legacy regression suite was not rerun or fixed. Earlier failures remain documented in historical `TEST_RESULTS.md`.

## Demo and local runtime

At pause, Docker demo services were left running. Frontend: http://localhost:18080, API: http://localhost:18000. Select SIMULATION Laboratory; login Demo Manager with the intentionally public synthetic password in `DEMO_GUIDE.md`. Same initial password for Demo Dentist and other demo accounts.

Compose project `cabinet-virtual-lab` uses isolated PostgreSQL18, Redis, bootstrap, real Django/Waitress, Celery worker/Beat and nginx frontend. Dedicated volumes contain synthetic DB, media and key. Native Windows PostgreSQL/private files are not mounted. External messaging is forced disabled in simulation mode.

Original native app may also still run on port8000 with its own `projetinnov` containers. Do not stop/reset/migrate those while testing the isolated demo unless requested. Native laboratories were migrated through api0024 earlier, with a private backup in `.runtime/backups/`.

Tests added labelled BROWSER cases to the demo. Immutable audit data stays available for inspection. Do not delete records or reset volumes merely to hide failures. A documented deliberate reset affects only verified demo volumes.

## Commands after fixes

From repository root:

```powershell
docker compose -f compose.demo.yml up -d --build
docker compose -f compose.demo.yml exec -T backend python manage.py check_virtual_lab
docker compose -f compose.demo.yml exec -T backend python manage.py test api.test_planning api.test_bpmn_acceptance customers.test_simulation --noinput
cd cabinet_frontend
npx.cmd playwright test --config=playwright.live.config.js
```

Local npm dependencies and Chromium headless shell have been installed. On another PC: `npm.cmd ci`, then `npx.cmd playwright install chromium --only-shell`. Browser tests require the running real demo and deliberately fail until the blockers are fixed. Standard config excludes `*.live.spec.js`.

Screenshots/reports are ignored under `.runtime/live-browser-review/`, `.runtime/live-browser-dentist-results/`, `.runtime/live-browser-preflight-results/` and `.runtime/live-browser-report/`. Read `DEMO_TEST_RESULTS.md` for findings and exact scope. Native secrets, private media, database backups, virtual environments and generated artifacts must stay out of Git.

After both fixes, rerun real browser workflow actions to completion, then continue Step3. A machine cycle completing must never imply human quality acceptance. Started/locked tasks remain protected during replanning, and machine occupancy must persist until unloading is confirmed.
