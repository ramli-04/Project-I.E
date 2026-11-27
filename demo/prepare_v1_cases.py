"""Add synthetic V1 cases through the real Docker demo API; never advance ORM rows."""
import io
import json
import os
from pathlib import Path
import sys
import urllib.error
import urllib.request
import uuid
from datetime import timedelta

LAB = 'simlab'
NOTE = 'V1 : donnees fictives de demonstration, sans patient reel.'
TARGETS = [
    ('COMMANDE', 'DEMANDE_RECUE', False),
    ('RECEPTION', 'A_CONFIRMER', True),
    ('CONTROLE_ENTREE', 'CONTROLE_DOSSIER', False),
    ('MODELE', 'CONTROLE_MODELE', True),
    ('CONCEPTION', 'SALLE_CAO', False),
    ('FABRICATION', 'PREPARATION_CNC', False),
    ('FINITION_QC', 'CONTROLE_QUALITE', False),
    ('LIVRAISON', 'PRET_EXPEDITION', False),
    ('CLOTURE', 'CLOTURE', False),
]


def ensure_demo_environment(env=None, container=None):
    env = os.environ if env is None else env
    container = Path('/.dockerenv').is_file() if container is None else container
    if (not container or env.get('CABINET_SIMULATION') != '1'
            or env.get('POSTGRES_HOST') != 'postgres' or env.get('POSTGRES_DB') != 'cabinet_demo'):
        raise RuntimeError('Outil reserve au conteneur Docker de demonstration ou de verification.')


def assert_created_order(order, expected_reference):
    if not expected_reference.startswith('V1-') or order.get('patient_ref') != expected_reference:
        raise RuntimeError('Dossier refuse : cette execution ne peut agir que sur ses nouveaux dossiers V1.')


def synthetic_stl():
    vertices = [(0, 0, 0), (1, 0, 0), (0, 1, 0), (0, 0, 1)]
    faces = [(0, 2, 1), (0, 1, 3), (1, 2, 3), (2, 0, 3)]
    lines = ['solid V1_NON_MANUFACTURING_DEMO']
    for face in faces:
        lines += ['facet normal 0 0 0', 'outer loop']
        lines += ['vertex ' + ' '.join(map(str, vertices[index])) for index in face]
        lines += ['endloop', 'endfacet']
    return ('\n'.join(lines) + '\nendsolid V1_NON_MANUFACTURING_DEMO\n').encode('ascii')


class DemoCases:
    def __init__(self):
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        self.sessions = {}
        self.ledger = {}
        self.tag = uuid.uuid4().hex[:8]
        self.clinic = None
        self.pins = {}

    def request(self, actor, method, path, data=None, *, public=False, expected=200, body=None, content_type=None):
        headers = {'Host': 'localhost' if public else LAB + '.localhost',
                   'Idempotency-Key': str(uuid.uuid4())}
        if actor:
            headers['Authorization'] = 'Bearer ' + self.sessions[actor]['token']
        if body is None and data is not None:
            body = json.dumps(data).encode('utf-8')
            content_type = 'application/json'
        if content_type:
            headers['Content-Type'] = content_type
        request = urllib.request.Request('http://127.0.0.1:8000' + path, data=body,
                                         headers=headers, method=method)
        try:
            with self.opener.open(request, timeout=45) as response:
                status, raw = response.status, response.read()
        except urllib.error.HTTPError as error:
            # Never print response bodies: successful creation/PIN results contain secrets.
            raise RuntimeError('Action refusee (HTTP ' + str(error.code) + ') : ' + method + ' ' + path) from None
        if status != expected:
            raise RuntimeError('Reponse inattendue (HTTP ' + str(status) + ') : ' + path)
        return json.loads(raw)

    def login(self):
        password = os.environ.get('V1_DEMO_PASSWORD', 'Demo-Lab-2026!')
        for actor, name, role in [('MANAGER', 'Demo Manager', 'LAB'),
                                  ('DENTIST', 'Demo Dentist', 'DENTIST'),
                                  ('COURIER', 'Demo Courier', 'COURIER')]:
            data = {'name': name, 'password': password, 'role': role}
            if role != 'DENTIST':
                data['laboratory'] = LAB
            self.sessions[actor] = self.request(None, 'POST', '/platform/login/', data, public=True)
        if self.sessions['MANAGER']['account']['workstation_role'] != 'MANAGER':
            raise RuntimeError('Le compte responsable attendu est indisponible.')

    def order(self, case):
        if case not in self.ledger:
            raise RuntimeError('Dossier refuse : identifiant absent du registre de cette execution.')
        order = self.request('MANAGER', 'GET', '/api/prescriptions/' + case + '/')
        assert_created_order(order, self.ledger[case]['reference'])
        return order

    def command(self, case, action, data=None, actor='MANAGER', dentist=False):
        self.order(case)
        path = ('/platform/dentist/orders/' + LAB + '/' + case + '/command/' if dentist
                else '/api/prescriptions/' + case + '/command/')
        return self.request(actor, 'POST', path, {'action': action, 'data': {'notes': NOTE, **(data or {})}},
                            public=dentist)

    def upload(self, case, kind, photo=False):
        self.order(case)
        if photo:
            from PIL import Image
            output = io.BytesIO()
            Image.new('RGB', (8, 8), (210, 220, 220)).save(output, format='PNG')
            content, filename, mime = output.getvalue(), 'V1-FICTIVE-PROOF.png', 'image/png'
        else:
            content, filename, mime = synthetic_stl(), 'V1-NON-MANUFACTURING.stl', 'model/stl'
        boundary = 'V1' + uuid.uuid4().hex
        body = ('--' + boundary + '\r\nContent-Disposition: form-data; name="kind"\r\n\r\n' + kind +
                '\r\n--' + boundary + '\r\nContent-Disposition: form-data; name="file"; filename="' +
                filename + '"\r\nContent-Type: ' + mime + '\r\n\r\n').encode() + content + (
                '\r\n--' + boundary + '--\r\n').encode()
        return self.request('MANAGER', 'POST', '/api/prescriptions/' + case + '/attachments/',
                            expected=201, body=body, content_type='multipart/form-data; boundary=' + boundary)

    def create(self, label, physical=False, design=False, route='CFAO'):
        reference = 'V1-' + label + '-' + self.tag
        created = self.request('DENTIST', 'POST', '/platform/dentist/orders/', {
            'laboratory_id': LAB, 'partner_clinic': self.clinic['id'], 'patient_ref': reference,
            'impression_type': 'PHYSIQUE' if physical else 'NUMERIQUE', 'disinfected': True,
            'delivery_service': 'STANDARD', 'design_validation_requested': design,
            'clinical_items': [{'tooth_number': 11, 'function': 'Couronne', 'form': 'Anatomique',
                                'shade': 'A2', 'material': '100% M\u00e9tal' if route == 'CONVENTIONNEL' else 'Zircone'}],
        }, public=True, expected=201)
        assert_created_order(created, reference)
        if created['partner_clinic'] != self.clinic['id']:
            raise RuntimeError('Le nouveau dossier ne correspond pas au cabinet fictif de cette execution.')
        case = str(created['id'])
        self.ledger[case] = {'reference': reference, 'physical': physical, 'lot': False, 'route': route}
        if not physical:
            self.upload(case, 'STL')
        return case

    def qr(self, case):
        self.order(case)
        from django.db import connection, transaction
        from django_tenants.utils import schema_context, tenant_context
        from customers.models import Client
        from api.models import Prescription
        from api.case_commands import qr_token
        with schema_context('public'):
            tenant = Client.objects.get(schema_name=LAB)
        with tenant_context(tenant), transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute('SET TRANSACTION READ ONLY')
            order = Prescription.objects.only('id', 'patient_ref', 'qr_nonce').get(pk=case)
            assert_created_order({'patient_ref': order.patient_ref}, self.ledger[case]['reference'])
            return qr_token(order)

    def inspection(self, case, stage, passed=True):
        from api.case_commands import CHECKS
        checks = dict.fromkeys(sorted(CHECKS[stage]), True)
        photo = None
        if not passed:
            checks[sorted(checks)[0]] = False
            photo = self.upload(case, 'PHOTO', photo=True)['id']
        return self.command(case, 'inspection', {'stage': stage, 'checks': checks, 'photo': photo,
                                                'advance': passed, 'notes': NOTE})

    def through(self, case, target, date_override=None):
        from django.utils import timezone
        for _ in range(50):
            order = self.order(case)
            status = order['status']
            if status == target:
                return order
            if status == 'DEMANDE_RECUE':
                self.command(case, 'accept', {'advance': True})
            elif status == 'ANALYSE_DEMANDE':
                self.command(case, 'advance', {'analysis_validated': True})
            elif status in {'ATTENTE_RAMASSAGE', 'EN_ROUTE_LABO'}:
                self.command(case, 'pickup' if status == 'ATTENTE_RAMASSAGE' else 'lab-deposit',
                             {'qr_token': self.qr(case)}, actor='COURIER')
            elif status == 'A_CONFIRMER':
                self.command(case, 'advance', {'reception_validated': True})
            elif status == 'CONTROLE_DOSSIER':
                self.inspection(case, 'PHYSICAL' if self.ledger[case]['physical'] else 'DIGITAL')
            elif status == 'CONTROLE_MODELE':
                self.inspection(case, 'MODEL')
            elif status == 'PLANIFICATION':
                if not self.ledger[case]['lot']:
                    self.request('MANAGER', 'POST', '/api/production-lots/', {
                        'code': self.ledger[case]['reference'] + '-LOT', 'prescriptions': [case]}, expected=201)
                    self.ledger[case]['lot'] = True
                self.command(case, 'advance', {'production_method': self.ledger[case]['route'],
                    'thermal_treatment': 'AUCUN' if self.ledger[case]['route'] == 'CONVENTIONNEL' else 'FRITTAGE',
                    'delivery_date': (date_override or timezone.localdate() + timedelta(days=4)).isoformat()})
            elif status == 'CONTROLE_QUALITE':
                self.inspection(case, 'QUALITY')
            elif status == 'PRET_EXPEDITION':
                response = self.command(case, 'issue-pin', actor='DENTIST', dentist=True)
                self.pins[case] = response['result']['pin_once']
                self.command(case, 'checkout', {'qr_token': self.qr(case)}, actor='COURIER')
            elif status == 'EN_ROUTE_CABINET':
                self.command(case, 'confirm-delivery', {'pin': self.pins.pop(case)}, actor='COURIER')
            elif status in {'LIVRE', 'ESSAYAGE'}:
                self.command(case, 'fitting', {'passed': True}, actor='DENTIST', dentist=True)
            elif status in {'VALIDATION_CAO', 'RETOUR_DEMANDE', 'CLOTURE'}:
                raise RuntimeError('Arret sur une etape externe inattendue : ' + status)
            else:
                self.command(case, 'advance')
        raise RuntimeError('Nombre maximal de transitions depasse pour un dossier fictif.')

    def run(self):
        from django.utils import timezone
        from api.workflow_spec import STAGES
        self.login()
        clinic_name = 'V1-CABINET-FICTIF-' + self.tag
        self.clinic = self.request('MANAGER', 'POST', '/api/partner-clinics/', {
            'name': clinic_name, 'pickup_address': 'V1 - adresse fictive de demonstration',
            'contact_phone': '0000000000', 'contact_email': 'demo@example.invalid',
            'platform_dentist': self.sessions['DENTIST']['account']['id'], 'payment_terms_days': 60,
        }, expected=201)
        if self.clinic['name'] != clinic_name:
            raise RuntimeError('Cabinet refuse : reponse inattendue lors de la creation additive.')
        rows = []
        for stage, target, physical in TARGETS:
            case = self.create(stage, physical, route='CONVENTIONNEL' if stage in {'FINITION_QC', 'LIVRAISON', 'CLOTURE'} else 'CFAO')
            order = self.through(case, target)
            if order['current_step']['stage'] != stage:
                raise RuntimeError('Etape affichee inattendue pour le dossier fictif.')
            row = {'id': case, 'reference': order['patient_ref'], 'stage': stage,
                   'stage_label': dict(STAGES)[stage], 'status': order['status']}
            rows.append(row)
            print(json.dumps({'created_stage': row}, ensure_ascii=False), flush=True)
        if {row['stage'] for row in rows} != {key for key, _ in STAGES}:
            raise RuntimeError('Les neuf etapes de presentation ne sont pas toutes representees.')
        overdue = self.create('RETARD')
        self.through(overdue, 'PREPARATION_CNC', timezone.localdate() - timedelta(days=1))
        failed = self.create('REPRISE', route='CONVENTIONNEL')
        self.through(failed, 'CONTROLE_QUALITE')
        self.inspection(failed, 'QUALITY', passed=False)
        self.command(failed, 'rework', {'origin': 'LAB', 'cause': 'V1 - non-conformite fictive',
            'corrective_action': 'V1 - correction fictive au modelage', 'restart_status': 'MODELAGE', 'losses': []})
        self.command(failed, 'advance')
        remade = self.order(failed)
        if remade['production_attempt'] != 2 or remade['status'] != 'MODELAGE':
            raise RuntimeError('La reprise documentee fictive est incomplete.')
        paused = self.create('DESIGN', design=True)
        self.through(paused, 'SALLE_CAO')
        design = self.upload(paused, 'DESIGN')
        self.command(paused, 'design-request', {'attachment': design['id']})
        design_order = self.order(paused)
        if design_order['status'] != 'VALIDATION_CAO' or not design_order['is_paused']:
            raise RuntimeError('La demande de validation fictive est incomplete.')
        extras = [{'purpose': purpose, 'id': case, 'reference': self.ledger[case]['reference'],
                   'status': self.order(case)['status']} for purpose, case in [
                       ('retard', overdue), ('reprise', failed), ('validation_design', paused)]]
        result = {'label': 'Donnees fictives - demonstration V1', 'run': self.tag,
                  'clinic': {'id': self.clinic['id'], 'name': self.clinic['name']}, 'stages': rows, 'extras': extras,
                  'scope': 'Positions de demonstration via commandes metier ; aucun temps de fabrication reel revendique.'}
        print(json.dumps({'V1_FIXTURE_RESULT': result}, ensure_ascii=False), flush=True)
        return result


def main():
    ensure_demo_environment()
    import django
    django.setup()
    from django.conf import settings
    if (not settings.CABINET_SIMULATION or settings.DATABASES['default']['NAME'] != 'cabinet_demo'
            or settings.DATABASES['default']['HOST'] != 'postgres' or settings.EXTERNAL_DELIVERY_ENABLED):
        raise RuntimeError('Configuration de demonstration refusee.')
    DemoCases().run()


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        # Guard and request errors contain only paths/statuses, never response bodies.
        print('Preparation V1 interrompue : ' + str(error), file=sys.stderr)
        raise SystemExit(1)
