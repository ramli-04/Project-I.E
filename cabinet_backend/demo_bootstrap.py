"""Compose one-shot initialization. Synthetic database only; safe to rerun."""
import os

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'cabinet_backend.settings')
import django
django.setup()

from django.conf import settings
from django.core.management import call_command

if not settings.CABINET_SIMULATION or settings.DATABASES['default']['NAME'] != 'cabinet_demo':
    raise SystemExit('Demo bootstrap requires simulation mode and the dedicated cabinet_demo database.')

call_command('migrate_schemas', shared=True, interactive=False)
call_command('migrate_schemas', tenant=True, interactive=False)
call_command('seed_virtual_lab')
