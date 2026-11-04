# Cabinet 2.0 — transfer this working version to another Windows PC

Snapshot: 4 November 2026. Read `MODEL_HANDOFF.md` before continuing development.

**This is unfinished development work. Backend contracts changed; parts of the frontend still need adapting.** The source checkpoint is on branch `feat/labo-config-and-ui` in `Mouss2000/I.E`. Database and private files are separate; GitHub does not contain them. Do not replace the original installation until the copy is verified.

After the checkpoint is pushed, the simplest source transfer on the destination PC is:

```powershell
git clone --branch feat/labo-config-and-ui --single-branch https://github.com/Mouss2000/I.E.git 'C:\Projects\Cabinet2'
```

Use the manual source-copy option below only for additional uncommitted changes. Continue with database backup, prerequisites and destination setup either way.

## 1. Prepare transfer on the current PC

Close frontend/backend terminals with Ctrl+C. From the project directory, stop background writers before backing up:

```powershell
Set-Location 'C:\Users\SetupGame\OneDrive\Desktop\New folder\Soutenance\Projet Innov'
docker compose stop celery_worker celery_beat
```

Create a source copy. This copies tracked AND untracked work; it does not commit or push anything. Destination below is a new transfer folder, not an existing installation:

```powershell
$transferRoot = 'C:\CabinetTransfer'
New-Item -ItemType Directory -Force -Path "$transferRoot\source" | Out-Null
robocopy . "$transferRoot\source" /E /XD .git venv .venv .graphify-venv node_modules __pycache__ .runtime private_media dist /XF .env .env.* local_settings.py *.pyc *.log
Copy-Item -LiteralPath '.env.example' -Destination "$transferRoot\source\.env.example"
```

Robocopy exit codes 0–7 are normally successful/nonfatal; 8+ means inspect failures. Keep this transfer private. Check that new Python modules, migrations 0015–0023, frontend source, lockfile, Compose files and both handoff documents are present. Generated build files may be stale; rebuild later. The copy omits Git history. If needed, clone your own repository on the new PC first, then overlay this source copy while preserving its `.git` folder.

Back up PostgreSQL using its installed command-line tools; add PostgreSQL's `bin` directory to PATH if commands are unavailable:

```powershell
pg_dump -h 127.0.0.1 -p 5432 -U postgres -W -d cabinet -Fc -f "$transferRoot\cabinet.dump"
```

Enter database password at the prompt. The dump includes public and tenant schemas. Check command success before transferring it.

Separately copy these private items through secure storage:

- `private_media/`: uploaded clinical files and generated PDFs. Preserve relative paths.
- `.runtime/signing-key`: preserve to keep existing signed QR codes valid. Otherwise a new key invalidates old signatures.
- `.runtime/bootstrap-credentials.json`: existing one-time platform passwords, if still needed. Never publish or paste contents into model chat.

Recreate `.env` for the destination database; do not upload credentials or the database dump to GitHub. Redis cache can be rebuilt. Pending durable tasks live in PostgreSQL; keep external delivery disabled until reviewed on the destination.

## 2. Install prerequisites on the new PC

- Python 3.13, including `py` launcher.
- Node.js compatible with the copied Vite dependencies; use Node 22.12+ within the 22.x line, or compatible newer version.
- PostgreSQL, preferably the same major version as the source server; include command-line tools.
- Docker Desktop with Linux containers/WSL2, running.
- Git if retaining repository history.

Clone or copy source to `C:\Projects\Cabinet2`. In PowerShell:

```powershell
Set-Location 'C:\Projects\Cabinet2'
py -3.13 -m venv venv
& '.\venv\Scripts\python.exe' -m pip install -r '.\cabinet_backend\requirements.txt'
Push-Location '.\cabinet_frontend'
npm.cmd ci
Pop-Location
Copy-Item -LiteralPath '.env.example' -Destination '.env'
notepad.exe '.env'
```

Set `.env` to the destination PostgreSQL database/user/password/port. Docker Compose reads this file automatically. **Native Django does not automatically load `.env`.** Configure its terminal separately:

```powershell
$env:POSTGRES_DB = 'cabinet'
$env:POSTGRES_USER = 'postgres'
$env:POSTGRES_HOST = '127.0.0.1'
$env:POSTGRES_PORT = '5432'
$dbSecret = Read-Host 'Destination PostgreSQL password' -AsSecureString
$dbSecretPointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($dbSecret)
try {
    $env:POSTGRES_PASSWORD = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($dbSecretPointer)
} finally {
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($dbSecretPointer)
    Remove-Variable dbSecret, dbSecretPointer
}
$env:EXTERNAL_DELIVERY_ENABLED = '0'
```

Repeat environment setup in each native Django terminal. Current development setup uses `postgres`; separating migration owner from a restricted runtime role remains unfinished.

## 3. Restore database and private files

Create a new, empty database, then restore. If `cabinet` already exists, choose another database name consistently instead of overwriting it:

```powershell
createdb -h 127.0.0.1 -p 5432 -U postgres -W -T template0 cabinet
pg_restore -h 127.0.0.1 -p 5432 -U postgres -W -d cabinet --no-owner --no-privileges --exit-on-error 'C:\CabinetTransfer\cabinet.dump'
```

Place transferred uploads in `C:\Projects\Cabinet2\private_media`. Place preserved signing key in `C:\Projects\Cabinet2\.runtime\signing-key` before running Django. Store transferred credentials privately in `.runtime` if needed.

For a fresh demonstration database instead of a restore, complete migrations below, then run `bootstrap_demo` and `secure_platform`. Do not run bootstrap to replace a restored installation.

## 4. Validate this snapshot before regular use

Latest tenant migrations 0021–0023 were not applied to the original real laboratories. Run these checks against the new development copy; do not assume the frontend is complete because migrations succeed:

```powershell
Push-Location '.\cabinet_backend'
& '..\venv\Scripts\python.exe' manage.py check
& '..\venv\Scripts\python.exe' manage.py makemigrations --check --dry-run
& '..\venv\Scripts\python.exe' manage.py test api.test_bpmn_acceptance --noinput
Pop-Location
```

Tests need permission to create a separate PostgreSQL test database. Latest acceptance run passed all 13 tests on the checkpoint source. Frontend lint and build also passed, with one lint warning. Full regression suite and frontend/backend integration remain pending; ask the next model to finish the handoff checklist.

After checks pass, migrate the destination development database:

```powershell
Push-Location '.\cabinet_backend'
& '..\venv\Scripts\python.exe' manage.py migrate_schemas --shared --noinput
& '..\venv\Scripts\python.exe' manage.py migrate_schemas --tenant --noinput
Pop-Location
```

For a **fresh empty installation only**:

```powershell
Push-Location '.\cabinet_backend'
& '..\venv\Scripts\python.exe' manage.py bootstrap_demo
& '..\venv\Scripts\python.exe' manage.py secure_platform
Pop-Location
```

`bootstrap_demo` creates public platform, Labo 1–3 and demo accounts. `secure_platform` assigns passwords only to accounts with blank password hashes; credentials are saved privately in `.runtime/bootstrap-credentials.json`. It does not reset existing passwords on a restored database. Configure real partner clinics and pickup addresses separately.

## 5. Start infrastructure, backend and frontend

`manage.py check` above creates a signing key if none was transferred. Both native Django and Docker must use that same persistent key.

From the project root:

```powershell
docker compose up -d --build redis celery_worker celery_beat
docker compose ps
docker compose logs --tail=60 celery_worker celery_beat
```

Worker connects to Windows PostgreSQL through `host.docker.internal`. If refused, check PostgreSQL listening addresses, `pg_hba.conf` and Windows firewall for the specific Docker network. Use password authentication; do not open unrestricted trust access.

Backend terminal, after native environment setup from step 2:

```powershell
Set-Location 'C:\Projects\Cabinet2\cabinet_backend'
& '..\venv\Scripts\python.exe' manage.py runserver 127.0.0.1:8000
```

Frontend terminal:

```powershell
Set-Location 'C:\Projects\Cabinet2\cabinet_frontend'
npm.cmd run dev -- --host 127.0.0.1
```

Open the Vite URL printed in its terminal, normally `http://localhost:5173/static/` because the Vite base is `/static/`. API defaults to `http://localhost:8000`; tenant API hosts use `labo1.localhost`, etc. Login requires actual account passwords. Current unfinished frontend may fail newer case/workflow actions; use `MODEL_HANDOFF.md` to complete them.

Stop native servers with Ctrl+C. Stop containers without deleting persisted data:

```powershell
Set-Location 'C:\Projects\Cabinet2'
docker compose stop celery_worker celery_beat redis
```

Compiled frontend bundles and the old packaged executable ZIP are deliberately excluded from Git. Source development uses Vite above. To regenerate the Django-served bundle after finishing frontend integration:

```powershell
Set-Location 'C:\Projects\Cabinet2\cabinet_frontend'
npm.cmd run build
New-Item -ItemType Directory -Force -Path '..\cabinet_backend\frontend_build' | Out-Null
Copy-Item -Path '.\dist\*' -Destination '..\cabinet_backend\frontend_build' -Recurse -Force
```

Backend static serving needs the appropriate development or production static configuration; using Vite avoids depending on the bundled root page during development.

## 6. Recreate Graphify separately

Do not copy virtual environments between PCs. Current Graphify distribution is `graphifyy==0.9.97`; wrapper `graphify.cmd` imports module `graphify`:

```powershell
Set-Location 'C:\Projects\Cabinet2'
py -3.13 -m venv .graphify-venv
& '.\.graphify-venv\Scripts\python.exe' -m pip install 'graphifyy==0.9.97'
.\graphify.cmd --help
.\graphify.cmd update .
.\graphify.cmd query 'BPMN workflow, authentication, inventory ledger and billing implementation' --budget 1200
```

The original PC graph was refreshed for this checkpoint (1026 nodes, 2264 edges). Generated graph files are excluded from Git; rebuild locally using the command above. Keep Graphify isolated from the Django venv.
