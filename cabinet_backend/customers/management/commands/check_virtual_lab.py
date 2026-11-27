"""Repeatable HTTP/database/worker smoke check for the isolated demo only."""
import io
import json
import os
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django_tenants.utils import schema_context


class Command(BaseCommand):
    help = 'Verify real demo API, seed restart safety, and a live Celery catalog task.'

    def handle(self, **options):
        if not settings.CABINET_SIMULATION or settings.DATABASES['default']['NAME'] != 'cabinet_demo':
            raise CommandError('This diagnostic runs only against the dedicated simulation database.')
        if settings.EXTERNAL_DELIVERY_ENABLED:
            raise CommandError('External dispatch must be disabled.')
        from api.models import EmployeeProfile, Machine, Prescription, PrescriptionHistory
        from api.planning_models import PlanningTask
        from customers.models import PlatformAccount
        with schema_context('public'):
            before_accounts = list(PlatformAccount.objects.order_by('pk').values_list('pk', 'password_hash'))
        with schema_context('simlab'):
            before_cases = list(Prescription.objects.order_by('pk').values_list('pk', 'status', 'state_version'))
            before_history = PrescriptionHistory.objects.count()
        call_command('seed_virtual_lab', stdout=io.StringIO())
        with schema_context('public'):
            if before_accounts != list(PlatformAccount.objects.order_by('pk').values_list('pk', 'password_hash')):
                raise CommandError('Reseeding unexpectedly changed accounts or passwords.')
        with schema_context('simlab'):
            if before_cases != list(Prescription.objects.order_by('pk').values_list('pk', 'status', 'state_version')):
                raise CommandError('Reseeding unexpectedly changed prescription progress.')
            if before_history != PrescriptionHistory.objects.count():
                raise CommandError('Reseeding unexpectedly appended status history.')
            if EmployeeProfile.objects.count() < 5 or Machine.objects.count() < 4 or not PlanningTask.objects.exists():
                raise CommandError('Expected demo resources/planning tasks missing.')
        self.stdout.write('PASS: seed rerun preserves case progress, status history and passwords.')

        base = os.environ.get('DEMO_API_URL', 'http://backend:8000').rstrip('/')
        frontend_origin = os.environ.get('DEMO_FRONTEND_ORIGIN', 'http://localhost:18080').rstrip('/')
        def request(path, *, data=None, token=None, tenant=False, origin=False):
            headers = {'Host': 'simlab.localhost' if tenant else 'localhost'}
            if token:
                headers['Authorization'] = 'Bearer ' + token
            if origin:
                headers['Origin'] = frontend_origin
            if data is not None:
                headers['Content-Type'] = 'application/json'
            req = Request(base + path, data=None if data is None else json.dumps(data).encode(), headers=headers)
            try:
                with urlopen(req, timeout=15) as response:
                    content = response.read()
                    return response.status, json.loads(content) if content else {}, response.headers
            except HTTPError as error:
                return error.code, json.loads(error.read()), error.headers

        status, payload, _ = request('/platform/environment/')
        if status != 200 or payload.get('mode') != 'SIMULATION':
            raise CommandError('Real HTTP backend is not reporting simulation mode.')
        status, _, _ = request('/api/planning/tasks/', tenant=True)
        if status != 401:
            raise CommandError('Anonymous planning access was not denied.')
        status, login, _ = request('/platform/login/', data={
            'name': 'Demo Manager', 'password': os.environ['DEMO_ACCOUNT_PASSWORD'],
            'role': 'LAB', 'laboratory': 'simlab',
        })
        if status != 200:
            raise CommandError('Demo manager login failed. A changed password needs corresponding diagnostic configuration.')
        token = login['token']
        try:
            for path in ['/api/prescriptions/', '/api/planning/tasks/', '/api/planning/workload/']:
                status, payload, headers = request(path, token=token, tenant=True, origin=True)
                if status != 200:
                    raise CommandError(f'Real API check failed: {path}, HTTP{status}')
                if headers.get('Access-Control-Allow-Origin') != frontend_origin:
                    raise CommandError('Frontend CORS origin was not accepted.')
            status, _, _ = request('/api/planning/tasks/', token=token)
            if status not in {401, 403}:
                raise CommandError('Operational planning leaked into public context.')
        finally:
            request('/platform/logout/', data={}, token=token)
        self.stdout.write('PASS: real login, tenant API reads, CORS and public/anonymous denial.')

        from api.tasks import refresh_tenant_billing_catalog_task
        result = refresh_tenant_billing_catalog_task.delay('simlab').get(timeout=45)
        if result.get('schema_name') != 'simlab' or result.get('status') != 'refreshed':
            raise CommandError('Live tenant-aware worker refresh failed.')
        self.stdout.write('PASS: Redis broker -> Celery worker -> tenant PostgreSQL -> result backend.')
