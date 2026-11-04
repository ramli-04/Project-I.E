# Frontend integration checkpoint — 4 November 2026

Database-free preview: run `npm.cmd run demo` from `cabinet_frontend` and open `http://localhost:5174/static/`. The login fields are prefilled; select any portal to explore fictitious data. This explicit preview mode uses a local Axios adapter, makes no backend requests and rejects writes. Regular `npm.cmd run dev` continues to use the real backend.

## Visual redesign

Latest refinement: the application is presented as a **laboratoire de prothèses dentaires**. The sidebar search was removed. Tab and website branding share `gestion-labo-mark.svg`; the favicon path was corrected to avoid a duplicated Vite `/static/` prefix. “Stocks et lots” now contains Personnel, Matériaux (the consumables catalogue) and Stock (balances, movements and production lots). Quantities are displayed and entered with at most two decimal places; existing database precision is preserved unless a value is edited. Current validation covers thirteen browser tests plus six Node contract tests, including these refinements.

The interface now follows the supplied light dental-dashboard reference: soft gray surfaces, white rounded cards, teal navigation and a consistent light theme across the portals. The laboratory dashboard includes an interactive FDI odontogram, SVG dental illustrations, a selectable intervention map, treatment queue and workflow distribution chart. Dentist accounts can access the same overview with the “Vue clinique” button. These visuals summarize existing cases; they do not generate diagnoses.

Animations include staggered tooth reveals, page/card transitions, chart growth, sidebar movement, hover feedback and an illustrative arcade rotation. The layout supports mobile navigation and `prefers-reduced-motion`. Twelve Chromium workflow/interface tests and five Node contract tests pass; lint retains the existing fetch-effect warning. Desktop/mobile screenshots were visually checked. No new animation or graphics dependency was added.

This update follows the frontend checklist in `MODEL_HANDOFF.md`. It updates React source against the current server contracts. It does **not** establish that the backend deployment, tenant migrations or background workers are ready.

## Implemented

- Dentist intake: distinct tooth-level function, form, shade and material; verified clinic/address selection; server pricing catalogue; standard J+4, express J+2 (+30%) and manual-quote J+1. The server confirms the price. UUID submission keys survive retries within the same form and change when the submitted payload changes.
- Digital intake uploads the actual STL after creation. A failed upload retains the created case and retries the upload without creating another prescription. Creation-only delivery PIN is displayed once; an owning dentist can issue a replacement PIN from the case.
- Paginated API responses are consumed fully before displaying local pages, keeping the existing overview counts consistent. Array responses from the dentist endpoint remain supported. Completed cases include delivery, fitting and closure.
- Laboratory case panels provide private uploads/downloads, QR labels, physical/digital/model/quality inspections, photographic evidence, design requests, workstation notes, explicit pause/resume, returned-intake resubmission, measured rework and subsequent loss assessment. Server workflow steps drive the diagram; generic PATCH no longer includes pause or billing fields.
- Dentist case panels provide design decisions, fitting acceptance, linked remake requests, disputes, PIN issuance, QR labels and invoice/document downloads through ownership-scoped platform endpoints.
- Courier custody uses signed QR pickup/deposit/checkout commands and the entered four-digit delivery PIN. The obsolete passwordless courier entry and generic status PATCH have been removed.
- Stocks and lots: linked production lots, signed usage/restock movements, compensating corrections, immutable ledger display and monthly stock-loss catalogue including incomplete valuation.
- Finance: delivered-month periods, line disputes/exclusions, explicit closing review, invoices, bounded credit amounts, dispute resolution, real PDF downloads and `202 PDF_PENDING` feedback. Monthly statement/financial catalogues show refresh metadata and net/credit totals.
- Operations: durable event retry and reconciliation of ambiguous message deliveries. Workstation roles are editable in platform account administration; partner clinics can be associated with platform dentist accounts.
- Session expiry clears the parent app and tenant state. Frontend dependencies received compatible audit fixes; no external messages were sent.

## Validation

From `cabinet_frontend`:

```powershell
npm.cmd ci
npm.cmd test
npx.cmd playwright install chromium
npm.cmd run test:browser
npm.cmd run lint
npm.cmd run build
```

- Five Node contract tests cover pagination, malformed envelopes, transport retries, changed submissions, rejected PIN attempts and manual-price display.
- Eleven Chromium tests exercise the React UI using mocked API contracts: STL recovery, paginated orders, authorized workflow payloads, inspections, QR/PIN custody, closing/credit, stock usage, session expiry, design approval, zero-loss and measured remakes, pending PDFs and manual J+1 quotes.
- Lint retains the pre-existing App fetch-effect warning. The build succeeds. Browser checks use mocked responses, not a running Django/PostgreSQL environment.

## Remaining live verification

Use `OTHER_PC_SETUP.md` for the current PostgreSQL/tenant setup. The backend was not started and no database migrations were applied during this frontend task. Verify migrated disposable tenant schemas, real account/clinic associations, file validation/access, both complete production routes, worker-generated deadlines/PDFs, inventory balances and financial closing against the real API before deployment. The pre-existing backend remediation items in `MODEL_HANDOFF.md` remain open.

The frontend currently loads all pages for its overview and then paginates display locally. Large installations should replace this with server-side filter/page navigation and dedicated aggregate endpoints.

Generated assets are rebuilt into `cabinet_frontend/dist` and copied to the ignored Django `frontend_build` directory. No commit, push or live deployment is included.
