# Local virtual-laboratory test review

Date: 10 November 2026. Foundation commit: `77235bf`, branch `feat/virtual-lab-demo`. Nothing published. Application behavior was not changed during this review; browser regression tests and this report were added locally.

**Result: working demo infrastructure, two confirmed application blockers before presentation/publishing.**

| Check | Result |
| --- | --- |
| Isolated demo PostgreSQL/API/Redis/worker/Beat/frontend | Running; API/PostgreSQL/Redis healthy |
| Seed rerun preserves status/history/account passwords | Passed |
| Real HTTP login, tenant reads, CORS origin and access denial | Passed |
| Real Redis -> worker -> tenant catalog refresh -> result backend | Passed |
| Planning + BPMN + seed boundary tests | **39 passed**, 87.585 seconds, separate temporary PostgreSQL test database |
| Manager browser login, cases, planning, workload and settings | Passed |
| Mobile browser login, menu and planning navigation | Passed |
| Dentist browser login and owned case list | Passed after correcting test selector |
| Select production route and advance in one request | **Failed: HTTP400** |
| Browser human start/pause/resume/complete scenario | **Blocked at start by CORS**; later actions not reached |

The initial browser run included test-selector errors; these were corrected and relevant checks rerun. They are distinct from the two confirmed application issues below. Requests went to the actual running Django API, without mocked responses.

## Blocker 1 — required idempotency header rejected by browser CORS

Preflight from `http://localhost:18080` to the tenant API returns HTTP200 and accepts the origin, but `Access-Control-Allow-Headers` contains only:

```text
accept, authorization, content-type, user-agent, x-csrftoken, x-requested-with
```

It omits `idempotency-key`. The frontend's retryable workflow commands send that header; Chromium blocks the actual write and displays `Network Error`. The task remains READY after clicking Start. Direct API clients are not subject to browser CORS, explaining why backend/smoke tests passed.

Required fix: extend Django's CORS allowed headers while retaining the standard defaults. Preserve existing authentication and tenant checks. Rerun real browser creation and workflow mutations after rebuilding the demo backend.

## Blocker 2 — production-route selection uses old route to choose next status

Reproduction: create a valid synthetic digital prescription, accept it, record intake evidence, advance to PLANIFICATION, then submit:

```json
{
  "action": "advance",
  "data": {
    "production_method": "IMPRESSION_3D",
    "delivery_date": "<valid delivery date>"
  }
}
```

Result: HTTP400, `Advance to the next workflow step or use an explicit exception command.`

In `api/case_commands.py`, `advance` calculates `next_status(order)` before applying/validating the proposed production route. An order with no production method still has a different next step. When the serializer applies IMPRESSION_3D, domain guards correctly reject the previously calculated destination.

A normal two-request workaround (PATCH route/date first, then advance) succeeds. This workaround was used only to isolate subsequent browser controls; the one-request regression remains a failing test. Required fix: compute the next step from the validated proposed route, preserving field permissions, audit evidence and all transition guards.

## Reproduce and inspect

```powershell
docker compose -f compose.demo.yml exec -T backend python manage.py check_virtual_lab
docker compose -f compose.demo.yml exec -T backend python manage.py test api.test_planning api.test_bpmn_acceptance customers.test_simulation --noinput
cd cabinet_frontend
npm.cmd ci
npx.cmd playwright install chromium --only-shell
npx.cmd playwright test --config=playwright.live.config.js
```

The live suite deliberately retains failing regression checks; expect failure until both blockers are fixed. Standard mocked browser tests exclude `*.live.spec.js`, so they do not mutate the demo unintentionally.

Private/local browser artifacts: `.runtime/live-browser-review/`, `.runtime/live-browser-dentist-results/` and `.runtime/live-browser-report/`. Screenshots show only synthetic data. Running browser tests adds labelled BROWSER cases to the isolated demo; they are retained for inspection because operational audit records are immutable. No real laboratory records were changed or deleted.

The demo remains available at http://localhost:18080. Machine-event simulation and human/machine scheduling separation remain future milestones. Full legacy regression failures documented in the earlier handoff were not retested or resolved by this targeted review.
