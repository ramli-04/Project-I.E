"""Presentation-readiness data for the Docker demo (Step 8.8-D).

Adds a realistic synthetic team, opening hours, a stock catalogue and pauses the
automated BROWSER- test cases. Everything except the synthetic account rows goes
through the real authenticated API. Idempotent: rerunning changes nothing new.
Never prints tokens, passwords or PINs.
"""
import json
import os
from pathlib import Path
import sys
import urllib.error
import urllib.parse
import urllib.request
import uuid

LAB = 'simlab'
PAUSE_NOTE = 'Données de test automatisées — hors démonstration'
PROTECTED = {'MY-TEST-001', 'TEST-2611-01'}
ARCHIVE_NOTE = 'Ancien dossier de démonstration — archivé'
ARCHIVED = {'DEMO-CNC-APPROVAL', 'DEMO-PRINT-EXPRESS', 'DEMO-PRINT-STANDARD', 'MY-DEMO-001'}
TEAM = [  # (name, workstation, {qualification: level})
    ('Demo Reception B', 'RECEPTION', {'demo-intake': 4}),
    ('Demo CAD C', 'CAO', {'demo-cad': 4}),
    ('Demo Fabrication B', 'FAO', {'demo-cnc': 5, 'demo-print': 2}),
    ('Demo Fabrication C', 'FAO', {'demo-print': 5}),
    ('Demo Quality B', 'QUALITE', {'demo-quality': 4}),
]
SATURDAY_STAFF = {'Demo Reception', 'Demo CAD A', 'Demo Fabrication', 'Demo Quality'}
SETTINGS = {'working_days': [0, 1, 2, 3, 4, 5], 'open_time': '08:00:00', 'close_time': '17:00:00',
            'break_start': '12:00:00', 'break_end': '13:00:00'}
STOCK = [  # (material, quantity, unit, alert threshold, unit cost MAD)
    ('Zircone multicouche 98 mm', '6', 'DISQUE', '3', '850'),
    ('E-Max CAD bloc A1', '12', 'UNITES', '5', '210'),
    ('E-Max CAD bloc A2', '4', 'UNITES', '5', '210'),
    ('E-Max CAD bloc A3', '9', 'UNITES', '5', '210'),
    ('PMMA provisoire disque 98 mm', '3', 'DISQUE', '2', '420'),
    ('Résine 3D modèles', '1800', 'GRAMMES', '500', '1.2'),
    ('Résine 3D provisoire', '350', 'GRAMMES', '400', '2.5'),
    ('Plâtre classe IV', '9000', 'GRAMMES', '2000', '0.08'),
    ('Silicone d’empreinte', '20', 'UNITES', '6', '95'),
    ('Fraises carbure Ø1 mm', '14', 'UNITES', '4', '120'),
    ('Pâte de polissage', '600', 'GRAMMES', '150', '0.6'),
    ('Liquide de glaçage', '40', 'UNITES', '10', '35'),
]


def ensure_demo_environment(env=None, container=None):
    env = os.environ if env is None else env
    container = Path('/.dockerenv').is_file() if container is None else container
    if (not container or env.get('CABINET_SIMULATION') != '1'
            or env.get('POSTGRES_HOST') != 'postgres' or env.get('POSTGRES_DB') != 'cabinet_demo'):
        raise RuntimeError('Outil reserve au conteneur Docker de demonstration ou de verification.')


def should_pause(order):
    """Only automated BROWSER- cases that are open and not already paused."""
    reference = order.get('patient_ref') or ''
    return (reference.startswith('BROWSER-') and reference not in PROTECTED
            and order.get('status') != 'CLOTURE' and not order.get('is_paused'))


def should_archive(order):
    """Owner-approved archive of the old seed/demo cases (never protected ones)."""
    reference = order.get('patient_ref') or ''
    return reference in ARCHIVED and reference not in PROTECTED and order.get('status') != 'CLOTURE' and not order.get('is_paused')


def missing_items(existing_names, catalogue=STOCK):
    names = {name.strip().casefold() for name in existing_names}
    return [row for row in catalogue if row[0].casefold() not in names]


class Operations:
    def __init__(self):
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        self.token = None
        self.report = {'accounts_created': [], 'profiles_created': [], 'qualifications_created': 0,
                       'shifts_created': 0, 'settings': None, 'stock_created': [], 'paused': [], 'pause_refused': []}

    def request(self, method, path, data=None, *, public=False, expected=(200, 201)):
        headers = {'Host': 'localhost' if public else LAB + '.localhost', 'Idempotency-Key': str(uuid.uuid4())}
        if self.token:
            headers['Authorization'] = 'Bearer ' + self.token
        body = None
        if data is not None:
            body, headers['Content-Type'] = json.dumps(data).encode('utf-8'), 'application/json'
        request = urllib.request.Request('http://127.0.0.1:8000' + path, data=body, headers=headers, method=method)
        try:
            with self.opener.open(request, timeout=60) as response:
                status, raw = response.status, response.read()
        except urllib.error.HTTPError as error:
            detail = ''
            try:
                detail = json.dumps(json.loads(error.read()), ensure_ascii=False)[:300]
            except Exception:
                pass
            raise RuntimeError(f'HTTP {error.code} {method} {path} {detail}') from None
        if status not in expected:
            raise RuntimeError(f'HTTP {status} {method} {path}')
        return json.loads(raw) if raw else {}

    def all_rows(self, path):
        rows, url = [], path
        while url:
            data = self.request('GET', url)
            if isinstance(data, list):
                return rows + data
            rows += data.get('results', [])
            nxt = data.get('next')
            url = (urllib.parse.urlsplit(nxt).path + '?' + urllib.parse.urlsplit(nxt).query) if nxt else None
        return rows

    def login(self):
        password = os.environ.get('V1_DEMO_PASSWORD', 'Demo-Lab-2026!')
        session = self.request('POST', '/platform/login/', {'name': 'Demo Manager', 'password': password,
                                                             'role': 'LAB', 'laboratory': LAB}, public=True)
        if session['account']['workstation_role'] != 'MANAGER':
            raise RuntimeError('Le compte responsable attendu est indisponible.')
        self.token = session['token']

    def accounts(self):
        """Synthetic platform accounts follow the seed command's own creation path."""
        from django.contrib.auth import get_user_model
        from django.contrib.auth.hashers import make_password
        from django_tenants.utils import schema_context
        from customers.models import Client, PlatformAccount
        from customers.views import login_key
        password = os.environ.get('DEMO_ACCOUNT_PASSWORD', '')
        if len(password) < 12:
            raise RuntimeError('DEMO_ACCOUNT_PASSWORD absent : comptes non créés.')
        users = {}
        with schema_context('public'):
            lab = Client.objects.get(schema_name=LAB)
            for name, workstation, _ in TEAM:
                account, created = PlatformAccount.objects.get_or_create(login_key=login_key(name), defaults={
                    'name': name, 'role': 'LAB', 'workstation_role': workstation, 'laboratory': lab,
                    'password_hash': make_password(password)})
                if account.role != 'LAB' or account.laboratory_id != lab.pk or account.workstation_role != workstation:
                    raise RuntimeError('Identité de compte en conflit : ' + name)
                if created:
                    self.report['accounts_created'].append(name)
                user, _ = get_user_model().objects.get_or_create(
                    username='virtual-' + login_key(name), defaults={'is_active': True, 'password': make_password(None)})
                users[name] = (account.pk, user.pk)
        return users

    def team(self, users):
        profiles = {p['name']: p for p in self.all_rows('/api/employee-profiles/')}
        for name, workstation, levels in TEAM:
            if name not in profiles:
                account_id, user_id = users[name]
                profiles[name] = self.request('POST', '/api/employee-profiles/', {
                    'user': user_id, 'platform_account': account_id, 'role': workstation,
                    'contract_type': 'CDI', 'hire_date': '2026-01-01'})
                self.report['profiles_created'].append(name)
            existing = {(q['employee'], q['qualification']) for q in self.all_rows('/api/planning/qualifications/')}
            for code, level in levels.items():
                if (profiles[name]['id'], code) not in existing:
                    self.request('POST', '/api/planning/qualifications/', {
                        'employee': profiles[name]['id'], 'qualification': code, 'proficiency_level': level})
                    self.report['qualifications_created'] += 1
        shifts = self.all_rows('/api/planning/availability/')
        with_rules = {row['employee'] for row in shifts}
        for name, profile in profiles.items():
            if profile.get('role') not in {'RECEPTION', 'CAO', 'FAO', 'QUALITE'} or profile['id'] in with_rules:
                continue
            days = [(d, '08:00:00', '17:00:00') for d in range(5)]
            if name in SATURDAY_STAFF:
                days.append((5, '08:00:00', '12:00:00'))
            for weekday, start, end in days:
                self.request('POST', '/api/planning/availability/', {
                    'employee': profile['id'], 'availability_type': 'SHIFT', 'weekday': weekday,
                    'start_time': start, 'end_time': end, 'notes': 'Horaire de démonstration'})
                self.report['shifts_created'] += 1

    def settings(self):
        result = self.request('PATCH', '/api/planning/settings/', SETTINGS)
        self.report['settings'] = {key: result.get(key) for key in SETTINGS}

    def stock(self):
        existing = [row['material_name'] for row in self.all_rows('/api/inventory/')]
        for name, quantity, unit, threshold, cost in missing_items(existing):
            self.request('POST', '/api/inventory/', {'material_name': name, 'quantity': quantity, 'unit': unit,
                                                     'alert_threshold': threshold, 'unit_cost': cost})
            self.report['stock_created'].append(name)

    def pause_test_cases(self):
        for order in self.all_rows('/api/prescriptions/?include_completed=true'):
            note = PAUSE_NOTE if should_pause(order) else ARCHIVE_NOTE if should_archive(order) else None
            if not note:
                continue
            try:
                self.request('POST', f"/api/prescriptions/{order['id']}/command/",
                             {'action': 'pause', 'data': {'paused': True, 'notes': note}})
                self.report['paused'].append({'id': order['id'], 'ref': order['patient_ref']})
            except RuntimeError as error:
                self.report['pause_refused'].append({'ref': order['patient_ref'], 'reason': str(error)[:300]})

    def recalculate(self):
        self.request('POST', '/api/planning/recalculate/', {}, expected=(200, 201, 202))


def main():
    ensure_demo_environment()
    import django
    django.setup()
    from django.conf import settings
    if (not settings.CABINET_SIMULATION or settings.DATABASES['default']['NAME'] != 'cabinet_demo'
            or settings.DATABASES['default']['HOST'] != 'postgres' or settings.EXTERNAL_DELIVERY_ENABLED):
        raise RuntimeError('Configuration de demonstration refusee.')
    ops = Operations()
    users = ops.accounts()
    ops.login()
    ops.team(users)
    ops.settings()
    ops.stock()
    ops.pause_test_cases()
    ops.recalculate()
    print(json.dumps(ops.report, ensure_ascii=False, indent=1))


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print('Preparation 8.8 interrompue : ' + str(error), file=sys.stderr)
        raise SystemExit(1)
