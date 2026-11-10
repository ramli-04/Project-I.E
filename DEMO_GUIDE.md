# Virtual laboratory — first milestone

This milestone packages the **real application with synthetic fixtures**. Machine telemetry, unattended-cycle scheduling and failure-control simulation are subsequent steps in `VIRTUAL_LAB_PLAN.md`; the interface explicitly labels that limitation.

## Start on another PC

Install Git and Docker Desktop with Linux containers. From this branch's checkout:

```powershell
git clone --branch feat/virtual-lab-demo https://github.com/ramli-04/Project-I.E.git CabinetVirtualLab
cd CabinetVirtualLab
docker compose -f compose.demo.yml up -d --build
docker compose -f compose.demo.yml ps -a
```

Initial startup downloads/builds images, applies migrations and seeds the synthetic laboratory. `bootstrap` should finish with exit0; backend becomes healthy before frontend starts. Open **http://localhost:18080/**. Use Chrome or Edge, which support `*.localhost` loopback names for tenant API requests.

Select laboratory **SIMULATION Laboratory**. Sign in as **Demo Manager**, password **Demo-Lab-2026!**. These are intentionally public demonstration credentials, used only inside the isolated localhost-bound environment. Other accounts use the same initial demo password:

- Laboratory: Demo Reception, Demo CAD A, Demo CAD B, Demo Fabrication, Demo Quality.
- Dentist portal: Demo Dentist.
- Courier portal: Demo Courier, assigned to SIMULATION Laboratory.

Inspect three synthetic cases, two CAD technicians with different proficiency, a fabrication technician, reception/quality personnel and virtual equipment records. Cases include standard and express printing plus a CNC case requiring dentist design approval. All initial cases are at CAO, reached through the normal intake guards with a synthetic STL and inspection evidence. This establishes reproducible setup, not yet physical-machine simulation.

For demonstrations outside working hours, initial seed deliberately defines artificial 00:00–23:59 working windows every day with no lunch break. These are synthetic settings, not proposed real laboratory shifts. Change shifts/qualifications in the normal planning interface to exercise those constraints. Restart preserves changes and case progress.

## Isolation and storage

- PostgreSQL and Redis run inside project `cabinet-virtual-lab`; neither exposes a host database port.
- API binds localhost port18000, frontend localhost18080.
- Separate named volumes store demo database, Redis, signing key and private synthetic files.
- The native application's `.env`, `.runtime`, `private_media` and Windows PostgreSQL are not mounted.
- No real email/WhatsApp delivery: simulation mode forces dispatch disabled.
- Frontend is built normally with the simulation label; **Vite's mocked `--mode demo` is not used**.
- Database login is deliberately fixed for the isolated demo; no production credentials are needed.

## Diagnose and stop

```powershell
docker compose -f compose.demo.yml logs --tail=80 bootstrap backend celery_worker
docker compose -f compose.demo.yml exec -T backend python manage.py check_virtual_lab
docker compose -f compose.demo.yml stop
```

To start again without rebuilding: `docker compose -f compose.demo.yml up -d`.

`http://localhost:18000/platform/environment/` reports SIMULATION and checks database reachability. Protected tenant APIs still require login. For a terminal test without tenant DNS resolution:

```powershell
curl.exe -H "Host: simlab.localhost" http://127.0.0.1:18000/api/planning/tasks/
```

Expected without credentials: HTTP401. If browser requests to `simlab.localhost` fail, check browser loopback/DNS restrictions; mapping `simlab.localhost` to127.0.0.1 in the destination's hosts file is an optional machine-local fallback.

## Reset synthetic data only

Restart preserves progress. For a deliberate full reset, stop/remove this **dedicated demo project and its volumes**:

```powershell
docker compose -f compose.demo.yml down --volumes
docker compose -f compose.demo.yml up -d --build
```

This deletes demo cases/accounts/uploads and generates a new signing key. Never run a volume-removal command against another Compose project to reset this demonstration.

First build needs internet. Build and test on the presentation PC beforehand; existing local images can then be started offline. Testing with actual printers/CAD software remains necessary before claiming manufacturer compatibility.

## Verified first milestone

- Full startup against empty dedicated demo volumes, all migrations, bootstrap exit0 and healthy API/PostgreSQL/Redis.
- Seed rerun preserves case status/version/history, account identities and passwords.
- Real HTTP login, paginated prescription/planning/workload reads, CORS and anonymous/public-context access denial.
- Live Redis/Celery/tenant-PostgreSQL catalog refresh and result retrieval.
- Three seed-boundary tests and nine existing frontend unit tests pass; frontend image builds successfully.
- Lint passes with the existing App.jsx effect warning. This milestone does not claim full browser end-to-end or full legacy backend regression success.
