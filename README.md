# Gestion Labo

**Gestion pour les laboratoires de prothèses dentaires.**

Gestion Labo connects dental laboratories, dental practices and couriers to follow prosthesis orders from prescription to fabrication, delivery and monthly billing. The interface is in French; amounts are expressed in Moroccan dirhams (MAD).

The project was previously called **Cabinet 2.0**. Existing directory names and some backend labels retain that name.

> **Development status:** the redesigned frontend includes a database-free preview and integrations for the current backend contracts. Live Django/PostgreSQL integration, remaining backend remediation and deployment validation are still pending. Passing the frontend tests does not establish production readiness.

## Quick start: preview without a database

Requires Node.js and npm. From the repository root:

```powershell
cd cabinet_frontend
npm.cmd ci
npm.cmd run demo
```

Open **[http://localhost:5174/static/](http://localhost:5174/static/)**, or the address printed by Vite if that port is occupied.

- Login fields are prefilled. Select a portal and enter a name if you change the selected role.
- Explore sample orders, fabrication views, personnel, materials, stocks and other screens.
- The preview uses fictitious data through a local Axios adapter. It makes no backend requests and rejects writes.
- PostgreSQL, Django, Redis and Docker are **not required** for this mode.
- Keep the terminal open; press `Ctrl+C` to stop the server.

`npm.cmd run demo` explicitly selects Vite's `demo` mode. Normal development and production builds use the real backend.

## Features

| Area | Current frontend functionality |
| --- | --- |
| Laboratory workspace | Light gray and teal design, interactive FDI tooth overview, fabrication queue, workflow charts and responsive navigation |
| Dentist portal | Tooth-level function, form, shade and material; verified clinic selection; disinfection confirmation; actual STL upload with upload-retry recovery |
| Fabrication | Server-defined workflow steps, physical/digital/model/quality inspections, private evidence, design approval, pause/resume and documented rework |
| Courier portal | Signed QR pickup, laboratory deposit and checkout; delivery confirmation using the entered four-digit PIN |
| Stocks et lots | **Personnel**, **Matériaux** and **Stock** tabs; material catalogue, stock balances, usage/restock movements, compensating corrections and linked production lots |
| Finance | Delivered-month statements, contested/excluded lines, monthly closing, invoices, credits, dispute resolution and PDF downloads |
| Operations | Durable task retry, message-delivery reconciliation and catalogue refresh information |
| Administration | Password-based accounts, laboratory assignments, workstation roles and session-expiry handling |

The site and browser tab share the teal tooth logo. Animations include tooth reveals, page transitions, chart growth and illustration rotation, with support for `prefers-reduced-motion`.

Quantity entry and display use **at most two decimal places**. Existing database precision is retained until a value is edited. Dental illustrations summarize associated orders; they do not generate clinical diagnoses.

### Business rules

- **Standard J+4:** normal delivery service.
- **Express J+2:** a **30% surcharge**, calculated by the server.
- **J+1:** requires a **manual laboratory urgency quote** before production.
- **Monthly statements:** group cases delivered during the month using the **Africa/Casablanca** calendar.
- **External email/WhatsApp delivery:** disabled by default until explicitly configured.

## Technology stack

| Component | Technologies |
| --- | --- |
| Frontend | React 19, Vite 8, Tailwind CSS 4, Lucide React, Axios |
| Backend | Django, Django REST Framework, django-tenants, django-cors-headers |
| Database | PostgreSQL with laboratory-specific tenant schemas |
| Background processing | Celery worker, Celery Beat and Redis |
| Documents | ReportLab, QR codes and private file storage |
| Frontend verification | Node test runner, Playwright/Chromium and Oxlint |

Backend versions are pinned in [`cabinet_backend/requirements.txt`](cabinet_backend/requirements.txt). Frontend dependencies and commands are defined in [`cabinet_frontend/package.json`](cabinet_frontend/package.json) and its lockfile.

## Run with the real backend

All commands below use PowerShell and start from the repository root unless otherwise stated.

### Prerequisites

- Git.
- Node.js **22.12+** or a compatible newer version. The installed Vite version also supports Node `^20.19.0`.
- Python **3.13+**, compatible with the pinned backend requirements.
- A PostgreSQL server and a development database.
- Docker Desktop with Linux containers for the provided Redis/worker/Beat services, or equivalent services configured separately.

Clone this repository if you do not already have it:

```powershell
git clone https://github.com/ramli-04/Project-I.E.git
cd Project-I.E
```

### 1. Install dependencies

```powershell
python -m venv .venv
& '.\.venv\Scripts\python.exe' -m pip install -r '.\cabinet_backend\requirements.txt'
Push-Location '.\cabinet_frontend'
npm.cmd ci
Pop-Location
```

### 2. Configure PostgreSQL

The application uses **PostgreSQL, not SQLite**. PostgreSQL may run natively or in your own container. The included `docker-compose.yml` defines Redis and Celery services; it does **not** create a PostgreSQL container.

Configure the native Django terminal. Adjust the values to match your local installation and the published database port:

```powershell
$env:POSTGRES_DB = 'cabinet'
$env:POSTGRES_USER = 'postgres'
$env:POSTGRES_HOST = '127.0.0.1'
$env:POSTGRES_PORT = '5432'
$databasePassword = Read-Host 'PostgreSQL password' -AsSecureString
$databaseCredential = [System.Management.Automation.PSCredential]::new($env:POSTGRES_USER, $databasePassword)
$env:POSTGRES_PASSWORD = $databaseCredential.GetNetworkCredential().Password
Remove-Variable databasePassword, databaseCredential
$env:EXTERNAL_DELIVERY_ENABLED = '0'
```

Alternatively, native Django can read `POSTGRES_PASSWORD` from the ignored file `cabinet_backend/cabinet_backend/local_settings.py`. Do not put credentials in tracked `settings.py`.

Docker Compose reads an ignored root `.env` file. Create it from `.env.example` if it does not exist, then fill in your local connection details:

```powershell
if (-not (Test-Path '.env')) {
    Copy-Item -LiteralPath '.env.example' -Destination '.env'
}
```

**Native Django does not automatically load Compose's `.env`.** Its environment or local settings must be configured separately. The Compose workers use `host.docker.internal` to reach PostgreSQL on the Windows host; adjust the Compose connection if your database lives on a different network.

### 3. Check and initialize a development database

Use a fresh, empty PostgreSQL development database, or follow the backup/restore instructions in [`OTHER_PC_SETUP.md`](OTHER_PC_SETUP.md). Do not bootstrap over a restored installation.

```powershell
cd cabinet_backend
& '..\.venv\Scripts\python.exe' manage.py check
& '..\.venv\Scripts\python.exe' manage.py makemigrations --check --dry-run
```

For a **fresh development installation only**, initialize shared tables, sample laboratories and account passwords, then ensure tenant migrations are applied:

```powershell
& '..\.venv\Scripts\python.exe' manage.py migrate_schemas --shared --noinput
& '..\.venv\Scripts\python.exe' manage.py bootstrap_demo
& '..\.venv\Scripts\python.exe' manage.py migrate_schemas --tenant --noinput
& '..\.venv\Scripts\python.exe' manage.py secure_platform
```

`bootstrap_demo` creates the public platform, Labo 1–3 and sample accounts. `secure_platform` initializes accounts whose password hashes are blank and saves credentials privately in `.runtime/bootstrap-credentials.json`. It does not reset existing passwords. Normal backend login requires a real account password; the preview's prefilled login is separate.

Configure partner clinics and their pickup addresses before submitting dentist prescriptions. Associate each clinic with its platform dentist account.

For an existing database, review the handoff's migration and validation requirements before applying changes.

### 4. Start Redis and background workers

After Django checks have created the persistent signing key and the database schemas are ready, run from the repository root:

```powershell
docker compose up -d --build redis celery_worker celery_beat
docker compose ps
```

Native Django and the containers share the ignored `.runtime/signing-key` and private media directory. Keep external delivery disabled during development. Workers are required for queued work such as deadline calculation, PDF generation and catalogue refresh.

### 5. Start Django and Vite

In the configured backend terminal, from `cabinet_backend`:

```powershell
& '..\.venv\Scripts\python.exe' manage.py runserver 127.0.0.1:8000
```

In a second terminal, from the repository root:

```powershell
cd cabinet_frontend
npm.cmd run dev -- --host 127.0.0.1
```

Open **[http://localhost:5173/static/](http://localhost:5173/static/)**. Use `localhost` for browser access to match the configured development CORS origins. If Vite selects a different port, check the backend's allowed origins before using it.

The platform API defaults to `http://localhost:8000/platform/`. Laboratory API requests use tenant hosts such as `http://labo1.localhost:8000/api/`. Configure `VITE_API_ORIGIN` when using a different API origin; client configuration lives in `src/api/client.js` and `src/api/platform.js`.

Stop native servers with `Ctrl+C`. Stop background services without deleting data:

```powershell
docker compose stop celery_worker celery_beat redis
```

## Production planning and manual progress

The laboratory workspace includes **Planning** with day, week, month, employee and order calendars, a Gantt view with dependencies and actual timings, workload, filters, history and supervisor assignment forms. **Progression de fabrication** in each order starts, pauses, resumes, blocks or completes its current production task through the existing idempotent case-command endpoint.

Accepted orders generate tasks from their applicable workflow. The deterministic scheduler enforces employee roles, mandatory qualifications and expiry, working hours, absences, dependencies and equipment capacity before ranking eligible candidates. Supervisors can configure durations and weights, manage availability and qualifications, link personnel to laboratory login accounts, and lock assignments. Started, completed and locked work is preserved; conflicts and delivery risks are reported.

Planning uses PostgreSQL and the existing Celery outbox. The database-free preview keeps this page available with an explicit empty state; it does not calculate real assignments. Production progress continues to require the existing design, inspection, inventory and QR/PIN evidence.

For a development database, migration **`api.0024_production_planning`** is additive and installs `btree_gist` in `public` for reservation exclusion constraints. The migration account needs permission to install that extension. Apply tenant migrations and rebuild the workers after installing this code:

```powershell
cd cabinet_backend
& '..\.venv\Scripts\python.exe' manage.py migrate_schemas --tenant --noinput
cd ..
docker compose up -d --build celery_worker celery_beat
```

In **Planning → Paramètres et équipe**, configure laboratory hours, production rules, mandatory qualifications and personnel. Then use **Replanifier** to enqueue existing accepted orders for synchronization. This also backfills eligible tasks for orders that predate the planning module. Keep Redis, the worker and Beat running for automatic recalculation and outbox recovery.

The first version reserves continuous, non-preemptive slots within a configurable horizon and recalculates movable tasks across the laboratory. A task longer than every available continuous window remains blocked. Future assignments are provisional until business prerequisites are satisfied. The interface uses timezone transitions supplied by the backend to keep browser displays and manual inputs consistent with the scheduler's Africa/Casablanca rules.

See [Planning implementation](PLANNING_IMPLEMENTATION.md) for the audit, assumptions, API, migration details, file list and verification results.

## Workflow and API

The server enforces role-specific transitions and evidence requirements. The physical and digital intake routes differ; fabrication follows the selected CFAO/CNC, 3D-printing or conventional route.

| Phase | Example statuses/actions |
| --- | --- |
| Intake | `DEMANDE_RECUE`, `ANALYSE_DEMANDE`, QR collection for physical impressions, reception and dossier inspection |
| Physical preparation | `COULEE_PLATRE`, `SCAN_LABO`, `CONTROLE_MODELE` |
| Planning and fabrication | `PLANIFICATION`, `SALLE_CAO`, optional dentist design approval, route-specific production steps |
| Finishing and dispatch | `FINITION`, `CONTROLE_QUALITE`, `CONDITIONNEMENT`, `PRET_EXPEDITION` |
| Delivery and fitting | QR checkout, `EN_ROUTE_CABINET`, PIN confirmation, `LIVRE`, fitting acceptance and `CLOTURE` |
| Exceptions | Returned intake, documented rework, measured material losses and billing disputes |

Main API groups:

| Endpoint | Purpose |
| --- | --- |
| `/platform/login/`, `/platform/logout/` | Password login and session revocation |
| `/platform/accounts/`, `/platform/laboratories/` | Platform administration |
| `/platform/pricing/` | Server pricing catalogue |
| `/platform/dentist/orders/`, `/platform/dentist/clinics/` | Dentist-owned prescriptions and clinics |
| `/api/prescriptions/` | Tenant case lists and authorized case updates |
| `/api/prescriptions/{id}/command/` | Evidence, approval, custody, PIN, rework and other workflow commands |
| `/api/inventory/`, `/api/inventory-transactions/`, `/api/production-lots/` | Materials, immutable stock ledger and lots |
| `/api/billing/` | Statements, closing, invoices, disputes and credits |
| `/api/analytics/`, `/api/operations/` | Monthly catalogues and background operations |

Tenant case lists are paginated. Creation through the dentist API and case commands require a UUID `Idempotency-Key`; retries must reuse the key for the same payload. Use the ownership-scoped platform routes for dentist file access and commands.

## Verification

From `cabinet_frontend`:

```powershell
npm.cmd test
npx.cmd playwright install chromium
npm.cmd run test:browser
npm.cmd run lint
npm.cmd run build
```

The browser test configuration starts Vite on port 5173, or reuses the server already there. These tests mock the API and do not require a database.

Frontend planning verification includes Node contract/timezone tests and Chromium tests for calendar data, filters, Gantt, workload, assignment errors and manual progression. The browser tests use API fixtures; they do not establish live browser-to-Django integration. Current executed counts and backend regression comparison are recorded in [Planning implementation](PLANNING_IMPLEMENTATION.md). Oxlint reports one existing App fetch-effect warning.

Backend verification requires PostgreSQL and permission to create a separate disposable test database. With native database configuration set, from `cabinet_backend`:

```powershell
& '..\.venv\Scripts\python.exe' manage.py check
& '..\.venv\Scripts\python.exe' manage.py makemigrations --check --dry-run
& '..\.venv\Scripts\python.exe' manage.py test api.test_bpmn_acceptance --noinput
& '..\.venv\Scripts\python.exe' manage.py test api customers --noinput
```

Full backend regression, live frontend/backend verification and deployment remain pending; see the handoff for known fixture and consistency work.

## Build frontend assets

From the repository root:

```powershell
Push-Location '.\cabinet_frontend'
npm.cmd run build
Pop-Location
New-Item -ItemType Directory -Force -Path '.\cabinet_backend\frontend_build' | Out-Null
Copy-Item -Path '.\cabinet_frontend\dist\*' -Destination '.\cabinet_backend\frontend_build' -Recurse -Force
```

The build uses the `/static/` base path. Generated bundles are ignored by Git and must be rebuilt after source changes. Serving them through Django also requires suitable static-file configuration.

`run_server.py` and `Cabinet2.spec` are legacy launcher/packaging files. The old SQLite portable-application instructions do not describe the current PostgreSQL/tenant setup; that packaging path has not been revalidated for it.

## Project structure

```text
Project-I.E/
├── cabinet_frontend/
│   ├── src/                 # Portals, lab dashboard, stock/finance/workflow UI
│   │   └── api/             # Tenant/platform clients, contracts and preview adapter
│   ├── public/              # Shared website logo and browser favicon
│   ├── tests/               # Playwright browser tests
│   └── package.json
├── cabinet_backend/
│   ├── api/                 # Tenant workflow, evidence, stock, finance and tasks
│   ├── customers/           # Tenant registry, platform accounts and authentication
│   ├── cabinet_backend/     # Django/Celery settings
│   ├── frontend_build/      # Generated assets, ignored by Git
│   ├── requirements.txt
│   └── manage.py
├── docker-compose.yml       # Redis, Celery worker and Beat
├── .env.example             # Compose database configuration template
├── FRONTEND_INTEGRATION.md
├── MODEL_HANDOFF.md
└── README.md
```

## Data and deployment notes

Credentials, database exports, `.runtime/`, `private_media/`, virtual environments and generated assets are excluded from Git. Source clones do not include the database, uploaded files or account passwords. Preserve the signing key when transferring an existing installation so its signed QR labels remain valid.

Patient references are entered manually; they are not automatically anonymized. Review the remaining backend consistency, database-role, tenant migration and deployment work before using real clinical data.

The overview loads all API pages and paginates its display locally. Planning tasks, events and workload use server pagination; resource selectors load their available pages. The planning heuristic currently caps recalculation at 5,000 unfinished tasks per laboratory.

## Further documentation

| Document | Purpose |
| --- | --- |
| [Frontend integration](FRONTEND_INTEGRATION.md) | Implemented UI, preview mode and validation scope |
| [Model handoff](MODEL_HANDOFF.md) | Backend checkpoint, open remediation and deployment caveats |
| [Other-PC setup](OTHER_PC_SETUP.md) | Database/private-file transfer and detailed Windows setup |
| [BPMN progress](BPMN_IMPLEMENTATION_PROGRESS.md) | Workflow remediation progress |
| [Inventory workflow](INVENTORY_WORKFLOW.md) | Stock ledger and loss-classification rules |
| [Billing analytics](BILLING_ANALYTICS.md) | Billing catalogue implementation |
| [Graphify setup](GRAPHIFY.md) | Local codebase knowledge graph |
| [Planning implementation](PLANNING_IMPLEMENTATION.md) | Production planning, manual progress, migrations and test results |

The transfer/handoff documents contain historical repository and branch names. Use the clone command in this README for the current `ramli-04/Project-I.E` repository. Older entries in `memory.md` describe previous iterations and may differ from the current code.
