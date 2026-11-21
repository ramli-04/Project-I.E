# Production planning and equipment phases

Current implementation: 21 November 2026. Planning uses the shared Django workflow and tenant database; the synthetic environment supplies fixtures, not an alternative scheduling backend. Dated test results are in [TEST_RESULTS.md](TEST_RESULTS.md).

## Tasks and scheduling

Accepted prescriptions generate applicable tasks from `api.workflow.workflow_steps`. Route changes preserve completed tasks and earlier attempts; inapplicable work is cancelled with history rather than deleted. No fictitious actual work timestamps are backfilled for an already advanced order.

The deterministic scheduler filters roles, structured qualifications/expiry, availability, shifts, absences, dependencies and machine capacity, then ranks eligible candidates using configured urgency, deadline slack, workload, continuity and stable identifiers. Free-text staff qualifications do not substitute for mandatory structured qualifications.

Automatic recalculation may move forecasts, but preserves started, paused, completed, manually blocked and locked work. An incompatible protected booking is reported as a conflict. Future bookings are provisional; READY does not authorize starting before the assigned time. A due late start/resume rebuilds movable forecasts around actual execution under the tenant lock. Manager-only `start_now: true` requires an explicit reason and still cannot displace protected work.

The heuristic is not an optimal solver. It handles at most 5,000 unfinished tasks with a configurable horizon of 1-90 days. Manual tasks need an available continuous attended window. Individual availability intervals are merged to avoid double-counting capacity; laboratory hours are the fallback when no individual weekly schedule is supplied.

## Technician and machine occupancy

Autonomous operation is an explicit rule for an equipment step. Ordinary laboratories default to attended/manual work; synthetic bootstrap initializes the demo's CNC, printing and furnace rules once and preserves later operator changes.

| Resource phase | Technician | Machine | Explicit next action |
| --- | --- | --- | --- |
| PLANNED | Forecast attended intervals | Forecast reservation | Start |
| SETUP | Occupied | Occupied | Launch cycle |
| CYCLE | Released | Occupied | Confirm actual cycle completion |
| AWAITING_UNLOAD | Awaiting qualified operator | Occupied | Begin unloading |
| UNLOADING | Occupied | Occupied | Confirm unloading and finish |
| FINISHED | Released | Released | Next eligible workflow step |

Manual tasks use MANUAL and ordinary start/complete commands. Total duration includes setup and unloading; the demo defaults to 10 minutes each, with the remainder as autonomous cycle time. These are synthetic estimates, not calibrated manufacturer protocols.

An active equipment hold is unbounded until actual unloading confirmation. Estimate expiry, pausing, blocking or cycle-completion acknowledgement never frees a loaded machine. Qualified operator availability is checked again before unloading; alternate-operator handoff is not implemented. Source advancement cannot skip these phases or the existing design, lot, inspection, custody and clinical gates.

## Transactions and database constraints

- Tenant advisory locking serializes reservation planning and associated changes.
- Prescription writers consistently use `FOR NO KEY UPDATE`, retaining writer serialization while permitting deferred planning foreign-key checks and avoiding the previous planner/source lock inversion.
- Migration0024 adds planning models and `btree_gist` reservation exclusions. Migration0025 uses PostgreSQL 14+ multiranges for the two attended employee windows and continuous equipment occupancy.
- Completed tasks, events and clinical/audit records retain their immutability protections. Commands carry UUID idempotency receipts; retrying the same payload is safe.
- Overlapping employee work is permitted only during an explicitly unattended cycle. Independent machine capacity slots remain independent resources; shared batch cycles are future work.
- Rolling back0025 may fail if new split-window bookings overlap under the former full-duration employee rule. Review data compatibility before a schema rollback.

Recalculation runs through the durable tenant-aware outbox/Celery pipeline. A source transition and its planning synchronization remain subject to one transactional guard path. Redis failure does not silently discard committed work. Lists poll approximately every 15 seconds, planning every 10 seconds, and tab return refreshes cases; asynchronous replanning can briefly retain a predecessor block after unloading.

## API and permissions

All planning routes require an active authenticated laboratory membership. Couriers cannot access planning. Resource changes and supervised assignments require the manager role. Ordinary task operation also requires the assigned employee/account, workflow role and current source stage.

| Route | Purpose |
| --- | --- |
| GET `/api/planning/tasks/`, `calendar/` | Paginated tasks/calendar and filters |
| GET `/api/planning/workload/` | Workload, capacity, conflicts and delivery risks |
| GET/PATCH `/api/planning/settings/` | Hours, days, horizon, weights and step rules |
| `/api/planning/availability/`, `qualifications/` | Structured availability and qualifications |
| GET `/api/planning/accounts/` | Active laboratory accounts for staff linkage |
| GET `/api/planning/events/` | Immutable task/prescription event history |
| POST `/api/planning/recalculate/` | Durable recalculation |
| POST `/api/planning/tasks/{id}/assign/`, `reschedule/`, `lock/` | Supervision with eligibility/conflict checks |
| POST `/api/prescriptions/{id}/command/` | Existing idempotent workflow command entrypoint |

Task commands include `planning-start`, `planning-pause`, `planning-block`, `planning-resume`, `planning-complete`, `planning-launch-cycle`, `planning-cycle-finished` and `planning-begin-unload`. Payloads include the task UUID and notes; `start_now` is a supervised option. Successful completion advances through the existing clinical workflow. External design, custody, PIN and fitting steps retain their specialized commands.

## User interface and time

Planning provides day/week/month calendars, Gantt, workload, filters, immutable history and supervised assignment/locking. The Gantt shows dependencies available on the page and indicates prerequisites outside it. Calendar drag/drop rescheduling is not implemented; use the validated assignment form.

The clinical dialog separates stage choices, controls/documents and current machine progress. Predefined French reasons plus optional detail/free text keep the existing notes payload. Selecting a reason performs no command. Errors remain visible at the top, including above the native dialog.

Timestamps are aware and use Africa/Casablanca. Backend-supplied timezone transitions keep browser inputs/displays aligned with scheduler tzdata; outside that provided window the browser uses its own rules. Workload/calendar lanes exclude unattended employee time while retaining equipment occupancy.

## Scope still open

No device telemetry, heartbeat/offline detection, shared-batch cycle, alternate unloader handoff or pre-cycle abort/recovery is implemented. There is no demonstrated large-laboratory latency guarantee. The read-only preview shows an explicit empty planning state and does not calculate real assignments. See [ROADMAP.md](ROADMAP.md) and the presenter [demo guide](../DEMO_GUIDE.md).
