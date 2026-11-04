import json
import os
import secrets

from django.conf import settings
from django.contrib.auth.hashers import make_password
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from django_tenants.utils import schema_context
from customers.models import PlatformAccount


class Command(BaseCommand):
    help = 'Initialize missing platform passwords; write one-time credentials to an ignored private local file.'

    def handle(self, **options):
        path = settings.BASE_DIR.parent / '.runtime' / 'bootstrap-credentials.json'
        path.parent.mkdir(parents=True, exist_ok=True)
        entries = json.loads(path.read_text()) if path.exists() else []
        with schema_context('public'), transaction.atomic():
            for account in PlatformAccount.objects.select_for_update().filter(password_hash=''):
                password = secrets.token_urlsafe(18)
                account.password_hash, account.password_reset_at = make_password(password), timezone.now()
                account.save(update_fields=['password_hash', 'password_reset_at'])
                entries.append({'name': account.name, 'role': account.role, 'password': password})
            fd = os.open(path, os.O_CREAT | os.O_TRUNC | os.O_WRONLY, 0o600)
            with os.fdopen(fd, 'w') as stream:
                json.dump(entries, stream, ensure_ascii=False, indent=2)
        self.stdout.write('Missing passwords initialized. Private credentials: .runtime/bootstrap-credentials.json')
