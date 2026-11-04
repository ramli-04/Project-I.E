# Cabinet 2.0 — Dental Prescription Management

Cabinet 2.0 is a prototype web application connecting dental practices, dental laboratories, and couriers. It tracks dental prosthesis orders from prescription through production and delivery. The interface is in French, and prices are expressed in Moroccan dirhams (MAD).

> **Current development checkpoint: PostgreSQL / django-tenants / CQRS.**
> Start with [other-PC setup](OTHER_PC_SETUP.md) and [model handoff](MODEL_HANDOFF.md).
> Clone branch `feat/labo-config-and-ui` for this checkpoint. Backend/frontend integration remains unfinished.
> Older prototype documentation below describes SQLite and obsolete workflow/pricing. Use the handoff documents for current setup and business rules.

Frontend integration now has a separate [implementation and validation checkpoint](FRONTEND_INTEGRATION.md), including browser tests and the remaining live backend checks.

## Features

- **Dentist portal:** create prescriptions with a patient reference, interactive tooth chart, shade guide, and material selection. View a calculated quote and track orders.
- **Laboratory portal:** manage orders in a Kanban dashboard, accept prescriptions, set delivery dates, and mark work ready for dispatch.
- **Courier portal:** collect ready orders and update delivery status.
- **Fast-Track option:** flag priority orders with a 200 MAD surcharge.
- **Disinfection confirmation:** the form requires confirmation before submission, and the API rejects an explicitly false disinfection value.
- **Local storage:** prescriptions are persisted in SQLite.
- **Windows packaging:** includes a Waitress launcher and PyInstaller configuration for a portable application.

## Order workflow

| Status | Meaning |
| --- | --- |
| `EN_ATTENTE` | Submitted, awaiting laboratory acceptance |
| `EN_PRODUCTION` | Accepted and being produced |
| `PRET_EXPEDITION` | Ready for dispatch |
| `EN_ROUTE` | Being delivered |
| `LIVRE` | Delivery completed |

These statuses describe the interface workflow. The API currently allows direct status updates without enforcing a transition sequence.

## Technology stack

| Component | Technologies |
| --- | --- |
| Frontend | React, Vite, Tailwind CSS, Lucide React |
| Backend | Python, Django, Django REST Framework, django-cors-headers |
| Database | SQLite |
| Local server | Waitress |
| Windows packaging | PyInstaller |

## Project structure

```text
Projet IE/
├── cabinet_frontend/
│   ├── src/                 # React portals, styles, and image assets
│   ├── public/              # Public assets
│   ├── package.json         # Dependencies and frontend commands
│   └── vite.config.js       # Vite configuration
├── cabinet_backend/
│   ├── api/                 # Prescription model, serializers, routes, migrations
│   ├── cabinet_backend/     # Django settings and URL configuration
│   ├── frontend_build/      # Compiled frontend served by Django
│   ├── dist/                # Existing packaged application artifacts
│   ├── manage.py            # Django command-line entry point
│   ├── run_server.py        # Local launcher
│   └── Cabinet2.spec        # PyInstaller configuration
├── memory.md                # Development notes and progress history
└── README.md
```

## Run locally

Install Python and a Node.js version compatible with the Vite version in `cabinet_frontend/package.json`. These PowerShell commands start from the `Projet IE` folder.

### Backend

```powershell
cd cabinet_backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install django djangorestframework django-cors-headers waitress
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8000
```

The API runs at `http://127.0.0.1:8000/api/prescriptions/`. Migrations create `cabinet_backend/db.sqlite3`. Backend dependencies are not currently pinned in a requirements file.

### Frontend

Open a second terminal in `Projet IE`:

```powershell
cd cabinet_frontend
npm ci
npm run dev
```

Open the local URL printed by Vite, including `/static/` if needed. Enter a name and select a role to access a portal. This login screen is a demonstration role selector.

The API address is defined in `cabinet_frontend/src/App.jsx` and currently points to `http://127.0.0.1:8000/api/prescriptions/`.

## Build the combined application

From `Projet IE`:

```powershell
cd cabinet_frontend
npm run build
Copy-Item -Path .\dist\* -Destination ..\cabinet_backend\frontend_build -Recurse -Force
cd ..\cabinet_backend
.\.venv\Scripts\python.exe run_server.py
```

The launcher applies pending migrations, starts Waitress at `http://127.0.0.1:8000`, and opens your browser. Keep the terminal open while using the application; press `Ctrl+C` to stop it. Rebuild and copy the frontend again after changing React code.

To generate a Windows package from `cabinet_backend` after updating the frontend build:

```powershell
.\.venv\Scripts\python.exe -m pip install pyinstaller
.\.venv\Scripts\python.exe -m PyInstaller Cabinet2.spec
```

The spec produces `dist/Cabinet2/`. Distribute the entire output folder together. In the packaged application, SQLite is stored beside the executable, so that directory must be writable.

## API

| Method | Endpoint | Action |
| --- | --- | --- |
| `GET` | `/api/prescriptions/` | List prescriptions, newest first |
| `POST` | `/api/prescriptions/` | Create a prescription |
| `GET` | `/api/prescriptions/{id}/` | Retrieve one prescription |
| `PATCH` / `PUT` | `/api/prescriptions/{id}/` | Update a prescription |
| `DELETE` | `/api/prescriptions/{id}/` | Delete a prescription |

A prescription stores the patient reference, dentist name, tooth number, shade, material, disinfection confirmation, priority option, quote, order status, delivery date, payment status, delivery PIN field, and timestamps. New prescriptions default to `EN_ATTENTE`; status and delivery date are read-only during creation.

## Prototype limitations

Role selection is held in frontend state, and the API permits unauthenticated access. Current Django settings enable debug mode, allow all CORS origins, and use a development secret key. Real authentication, role permissions, and deployment configuration are needed before using patient data.

Patient references are entered manually; the application does not anonymize them automatically. Quotes are calculated in the frontend and accepted by the API. Delivery PIN and payment fields are prototype features rather than verified delivery or payment controls.

The development history in `memory.md` describes earlier iterations and may differ from the current code.
