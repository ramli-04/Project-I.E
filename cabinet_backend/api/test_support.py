"""Workflow setup for integration tests; uses real authenticated endpoints."""
import uuid
import tempfile
from datetime import timedelta

from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from django.test import override_settings

from .case_commands import qr_token


class WorkflowFixtures:
    def setUp(self):
        super().setUp()
        files = tempfile.TemporaryDirectory()
        self.addCleanup(files.cleanup)
        media = override_settings(PRIVATE_MEDIA_ROOT=files.name)
        media.enable()
        self.addCleanup(media.disable)

    def workflow_command(self, order, action, data=None):
        response = self.client.post(f'/api/prescriptions/{order.pk}/command/',
            {'action': action, 'data': data or {}}, format='json',
            HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()))
        self.assertEqual(response.status_code, 200, response.data)
        order.refresh_from_db()
        return response

    def passing_intake(self, order):
        stage = 'PHYSICAL' if order.impression_type == 'PHYSIQUE' else 'DIGITAL'
        if stage == 'DIGITAL':
            content = b'solid test\nfacet normal 0 0 1\nouter loop\nvertex 0 0 0\nvertex 1 0 0\nvertex 0 1 0\nendloop\nendfacet\nendsolid test\n'
            uploaded = self.client.post(f'/api/prescriptions/{order.pk}/attachments/',
                {'kind': 'STL', 'file': SimpleUploadedFile('scan.stl', content)}, format='multipart')
            self.assertEqual(uploaded.status_code, 201, uploaded.data)
        checks = ['deformation', 'bubbles', 'limits', 'occlusion', 'hygiene'] if stage == 'PHYSICAL' else ['margins', 'occlusion', 'space', 'scan_quality']
        self.workflow_command(order, 'inspection', {'stage': stage, 'checks': dict.fromkeys(checks, True)})

    def deliver_case(self, order, *, route='CFAO', pin=None, thermal_treatment='AUCUN', stop_at='LIVRE'):
        pin = pin or getattr(order, '_new_delivery_pin', None)
        self.assertIsNotNone(pin, 'Fixture must retain the case creation PIN')
        if not order.accepted:
            accepted = self.client.patch(f'/api/prescriptions/{order.pk}/', {'accepted': True}, format='json')
            self.assertEqual(accepted.status_code, 200, accepted.data)
            order.refresh_from_db()
        visited = [order.status]
        for _ in range(35):
            stage = order.status
            if stage == stop_at:
                return visited
            data = {}
            if stage == 'ANALYSE_DEMANDE':
                data['analysis_validated'] = True
            elif stage == 'A_CONFIRMER':
                if order.intake_version >= 2:
                    self.passing_intake(order)
                data['reception_validated'] = True
            elif stage == 'CONTROLE_MODELE':
                self.workflow_command(order, 'inspection', {'stage': 'MODEL', 'checks': {'model': True, 'scan': True}})
            elif stage == 'PLANIFICATION':
                data = {'production_method': route, 'thermal_treatment': thermal_treatment,
                    'delivery_date': (timezone.localdate() + timedelta(days=4)).isoformat()}
                if order.intake_version >= 2:
                    lot = self.client.post('/api/production-lots/', {'code': 'TEST-' + uuid.uuid4().hex,
                        'prescriptions': [str(order.pk)]}, format='json')
                    self.assertEqual(lot.status_code, 201, lot.data)
            elif stage == 'CONTROLE_QUALITE':
                self.workflow_command(order, 'inspection', {'stage': 'QUALITY', 'checks': dict.fromkeys(
                    ['margins', 'contacts', 'shade', 'occlusion', 'cosmetic', 'glazing', 'polishing'], True)})
            custody = {'ATTENTE_RAMASSAGE': 'pickup', 'EN_ROUTE_LABO': 'lab-deposit', 'PRET_EXPEDITION': 'checkout'}
            if stage in custody:
                self.workflow_command(order, custody[stage], {'qr_token': qr_token(order)})
            elif stage == 'EN_ROUTE_CABINET':
                self.workflow_command(order, 'confirm-delivery', {'pin': pin})
            else:
                self.workflow_command(order, 'advance', data)
            visited.append(order.status)
        self.fail(f'Fixture did not reach {stop_at} within the workflow bound')
