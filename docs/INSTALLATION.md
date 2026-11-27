# Native installation and protected-data transfer

For a portable synthetic demonstration, use [DEMO_GUIDE.md](../DEMO_GUIDE.md). It supplies its own PostgreSQL/Redis/runtime volumes and does not need a native database restore. For ordinary development, follow the current dependency, environment, migration and launch commands in the root [README](../README.md).

This document covers the additional work needed to transfer an existing PostgreSQL installation. Git contains source, not passwords, database records, uploaded files or the persistent signing key. Old SQLite portable executables are not a supported installation method.

## Source and prerequisites

- Transfer the reviewed branch/checkpoint, including any unpublished source changes. Do not assume an older remote clone contains the current local implementation.
- Recreate Python and Node environments on the destination. Do not copy virtual environments or node_modules between machines.
- Use PostgreSQL 14+ for multirange constraints; the synthetic demo currently uses PostgreSQL 18. Match source/destination PostgreSQL versions and available extensions for a native restore.
- Graphify is a separate optional development environment; see [GRAPHIFY.md](GRAPHIFY.md).

The native Django terminal reads its own environment or ignored `local_settings.py`; it does not automatically load the root Compose `.env`. Docker workers reaching a Windows-host database use `host.docker.internal`, whereas native Django commonly uses 127.0.0.1. Keep both configured for the intended database and signing key.

## Preserve a consistent installation

1. Identify the actual PostgreSQL database, active laboratory schemas and private-media location. Do not infer them from old directory or branch names.
2. Stop the installation's web writers, worker and Beat before taking a coordinated backup of database and private files. For the native infrastructure project, `docker compose stop celery_worker celery_beat` stops those background writers. This is distinct from `compose.demo.yml`.
3. Use `pg_dump` in custom format, with the real connection and an explicit backup path. For example, replacing the example database/user/path as appropriate:

```powershell
pg_dump -h 127.0.0.1 -p 5432 -U postgres -W -d cabinet -Fc -f 'C:\CabinetTransfer\cabinet.dump'
```

4. Check the exit code and inspect `pg_restore --list 'C:\CabinetTransfer\cabinet.dump'`. The backup must include public authentication/tenant registration and all required laboratory schemas.
5. Separately preserve `private_media/`, `.runtime/signing-key`, and any still-required account credentials from `.runtime/bootstrap-credentials.json`. Do not print credentials or signing keys. Preserve relative private-file paths and share these items through protected storage, outside Git.
6. Preserve pending durable PostgreSQL tasks; Redis cache can be rebuilt. Keep external email/WhatsApp dispatch disabled on the copy.

## Restore into a separate destination

1. Create a new, empty destination database; never restore over the original merely to test a source update.
2. Restore with the appropriate database owner and extensions. An example for a separately created `cabinet_rehearsal` database is:

```powershell
pg_restore -h 127.0.0.1 -p 5432 -U postgres -W --exit-on-error --no-owner --no-privileges -d cabinet_rehearsal 'C:\CabinetTransfer\cabinet.dump'
```

3. Restore private media and the persistent signing key to the destination installation. A new signing key invalidates old signed QR content. Existing hashed account passwords are restored with the database.
4. Configure native Django and Compose workers to use the destination. Recreate local secrets privately; keep `EXTERNAL_DELIVERY_ENABLED=0` until separately configured and reviewed.
5. Do not run `bootstrap_demo` over a restored installation. `secure_platform` initializes blank password hashes; it does not reset restored accounts.

## Validate source, schema and workers together

From `cabinet_backend`, with the intended native environment configured:

```powershell
& '..\.venv\Scripts\python.exe' manage.py check
& '..\.venv\Scripts\python.exe' manage.py makemigrations --check --dry-run
& '..\.venv\Scripts\python.exe' manage.py showmigrations api customers
```

Inspect the restored schema's migration state before applying reviewed migrations. The isolated demo is migrated through api0025; that does not prove the native database has received those migrations. Public and tenant migrations are separate:

```powershell
& '..\.venv\Scripts\python.exe' manage.py migrate_schemas --shared --noinput
& '..\.venv\Scripts\python.exe' manage.py migrate_schemas --tenant --noinput
```

Migration0024 installs `btree_gist`; migration0025 adds multirange employee reservations and retained equipment holds. The migration owner needs the required extension/DDL permissions. A least-privilege runtime role remains production deployment work; do not assume the development superuser configuration is the final runtime policy.

Rebuild worker/Beat images from the same source before starting the updated installation. Check registered tasks, outbox recovery, tenant isolation, private downloads, authentication and the full workflow on a disposable tenant/copy. Use a separate disposable test database for regression runs. Native deployment and manufacturer connectivity remain distinct from the verified synthetic demo.

Use `manage.py runserver` and Vite for native development. To serve a compiled frontend through Django, rebuild and copy the generated static assets as shown in README; the `frontend_build` directory is generated and excluded from Git. See [TEST_RESULTS.md](TEST_RESULTS.md) for dated evidence and [ROADMAP.md](ROADMAP.md) for remaining scope.
