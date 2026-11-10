# Application test results — 4 November 2026

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
- Existing frontend/backend contract gaps remain documented in `MODEL_HANDOFF.md`.
- Next: adapt regression fixtures/contracts, investigate reset/session case, finish frontend integration, rerun full suite and perform browser/live-worker checks.
- This report is local and uncommitted; no new push performed during testing.
