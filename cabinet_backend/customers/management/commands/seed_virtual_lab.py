"""Synthetic fixtures exercising production services, never bypassing BPMN guards."""
import os
import uuid
from datetime import date, time, timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction
from django.utils import timezone
from django_tenants.utils import schema_context, tenant_context

from customers.models import Client, Domain, PlatformAccount


class Command(BaseCommand):
    help = 'Seed an isolated, synthetic virtual laboratory; never reset existing records.'

    def handle(self, **options):
        if not settings.CABINET_SIMULATION or settings.DATABASES['default']['NAME'] != 'cabinet_demo':
            raise CommandError('Requires CABINET_SIMULATION=1 and the dedicated cabinet_demo database.')
        password = os.environ.get('DEMO_ACCOUNT_PASSWORD', '')
        if len(password) < 12:
            raise CommandError('Set DEMO_ACCOUNT_PASSWORD to at least 12 characters.')
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_advisory_lock(hashtextextended('virtual-lab-seed-v1', 0))")
        try:
            self.seed(password)
        finally:
            with connection.cursor() as cursor:
                cursor.execute("SELECT pg_advisory_unlock(hashtextextended('virtual-lab-seed-v1', 0))")
        self.stdout.write(self.style.SUCCESS('Virtual laboratory ready. Existing progress and passwords preserved.'))

    def seed(self, password):
        with schema_context('public'):
            public, _ = Client.objects.get_or_create(schema_name='public', defaults={'name': 'SIMULATION platform'})
            for hostname in ['localhost', '127.0.0.1', 'backend', 'bootstrap']:
                Domain.objects.get_or_create(domain=hostname, defaults={'tenant': public, 'is_primary': hostname == 'localhost'})
            lab, _ = Client.objects.get_or_create(schema_name='simlab', defaults={'name': 'SIMULATION Laboratory'})
            Domain.objects.get_or_create(domain='simlab.localhost', defaults={'tenant': lab, 'is_primary': True})
            specifications = [
                ('Demo Manager', 'LAB', 'MANAGER'), ('Demo Reception', 'LAB', 'RECEPTION'),
                ('Demo CAD A', 'LAB', 'CAO'), ('Demo CAD B', 'LAB', 'CAO'),
                ('Demo Fabrication', 'LAB', 'FAO'), ('Demo Quality', 'LAB', 'QUALITE'),
                ('Demo Dentist', 'DENTIST', 'MANAGER'), ('Demo Courier', 'COURIER', 'MANAGER'),
            ]
            accounts = {}
            from customers.views import login_key
            for name, role, workstation in specifications:
                account, created = PlatformAccount.objects.get_or_create(login_key=login_key(name), defaults={
                    'name': name, 'role': role, 'workstation_role': workstation,
                    'laboratory': lab if role in {'LAB', 'COURIER'} else None,
                    'password_hash': make_password(password),
                })
                if account.role != role or (role in {'LAB', 'COURIER'} and account.laboratory_id != lab.pk):
                    raise CommandError('Demo account identity conflicts with an existing record.')
                accounts[name] = account

        from api.models import EmployeeProfile, Machine, PartnerClinic
        from api.planning_models import EmployeeQualification, PlanningSettings
        from api.planning import recalculate, lock_resources, resources_changed, DEFAULT_RULES
        with tenant_context(lab):
            for name, role, workstation in specifications:
                if role != 'LAB' or workstation == 'MANAGER':
                    continue
                with schema_context('public'):
                    user, _ = get_user_model().objects.get_or_create(
                        username='virtual-' + login_key(name), defaults={'is_active': True, 'password': make_password(None)})
                employee, created = EmployeeProfile.objects.get_or_create(user=user, defaults={
                    'platform_account': accounts[name], 'role': workstation,
                    'contract_type': 'CDI', 'hire_date': date(2026, 1, 1),
                })
                codes = {'CAO': ['demo-cad'], 'FAO': ['demo-print', 'demo-cnc'],
                         'RECEPTION': ['demo-intake'], 'QUALITE': ['demo-quality']}[workstation]
                if created:
                    for code in codes:
                        EmployeeQualification.objects.create(employee=employee, qualification=code,
                            proficiency_level=5 if name == 'Demo CAD A' else 3)
            for name, kind in [('Virtual printer', 'IMPRESSION_3D'), ('Virtual mill', 'USINEUSE_CNC'),
                               ('Virtual furnace', 'FOUR_FRITTAGE'), ('Virtual scanner', 'SCANNER')]:
                Machine.objects.get_or_create(name=name, defaults={'machine_type': kind, 'capacity': 1, 'status': 'ACTIF'})
            PlanningSettings.objects.get_or_create(pk=1, defaults={
                # Deliberately artificial, so presentations can run outside normal shifts.
                'working_days': list(range(7)), 'open_time': time(0), 'close_time': time(23, 59),
                'break_start': time(12), 'break_end': time(12),
                'step_rules': {'SALLE_CAO': {'qualifications': ['demo-cad']},
                    'IMPRESSION_3D': {'qualifications': ['demo-print']},
                    'USINAGE_CNC': {'qualifications': ['demo-cnc']}},
            })
            # Versioned synthetic capability upgrade: preserve operator choices,
            # active task snapshots and all case/audit history on repeated startup.
            with transaction.atomic():
                anchor=lock_resources()
                config=PlanningSettings.objects.get(pk=1)
                changed=False
                for step in ['IMPRESSION_3D','USINAGE_CNC','TRAITEMENT_THERMIQUE','FRITTAGE_9H']:
                    rule=config.step_rules.setdefault(step,{})
                    if 'unattended' not in rule:
                        rule.setdefault('setup_minutes',10)
                        rule.setdefault('unload_minutes',10)
                        rule['unattended']=rule.get('duration',DEFAULT_RULES[step][1]) > rule['setup_minutes']+rule['unload_minutes']
                        changed=True
                if changed:
                    config.save(update_fields=['step_rules','updated_at'])
                    resources_changed('demo-bootstrap',kind='DEMO_PHASE_RULES_INITIALIZED',
                        anchor=anchor,resources_locked=True)
            clinic, _ = PartnerClinic.objects.get_or_create(name='SIMULATION Clinic', defaults={
                'pickup_address': 'Synthetic address — presentation data only', 'contact_phone': '0000000000',
                'contact_email': 'demo@example.invalid', 'platform_dentist': accounts['Demo Dentist'],
            })
            for reference, service, approval, method in [
                ('DEMO-PRINT-STANDARD', 'STANDARD', False, 'IMPRESSION_3D'),
                ('DEMO-PRINT-EXPRESS', 'EXPRESS', False, 'IMPRESSION_3D'),
                ('DEMO-CNC-APPROVAL', 'STANDARD', True, 'CFAO'),
            ]:
                self.case(reference, service, approval, method, clinic, accounts)
            recalculate(actor='demo-bootstrap')

    @transaction.atomic
    def case(self, reference, service, approval, method, clinic, accounts):
        from api.models import Prescription
        if Prescription.objects.filter(patient_ref=reference).exists():
            return
        from api.case_serializers import PrescriptionSerializer
        from api.case_commands import execute_case_command
        from api.documents import save_attachment
        from api.signals import prescription_audit_context
        material = 'Zircone' if method == 'CFAO' else 'Provisoire Résine'
        serializer = PrescriptionSerializer(data={
            'patient_ref': reference, 'dentist_name': 'Demo Dentist', 'disinfected': True,
            'partner_clinic': clinic.pk, 'impression_type': 'NUMERIQUE', 'delivery_service': service,
            'design_validation_requested': approval,
            'clinical_items': [{'tooth_number': 11, 'function': 'Synthetic demonstration',
                'form': 'Anatomique', 'shade': 'A2', 'material': material}],
        })
        serializer.is_valid(raise_exception=True)
        order = serializer.save(dentist_account=accounts['Demo Dentist'])
        actor = f"platform:{accounts['Demo Manager'].pk}:Demo Manager"
        with prescription_audit_context(actor, 'Synthetic intake demonstration', {'role': 'MANAGER'}):
            order.accepted = True
            order.save()
            order.status = 'ANALYSE_DEMANDE'
            order.save()
            order.status, order.analysis_validated = 'A_CONFIRMER', True
            order.save()
            mesh = b'solid demo\nfacet normal 0 0 1\nouter loop\nvertex 0 0 0\nvertex 1 0 0\nvertex 0 1 0\nendloop\nendfacet\nendsolid demo'
            save_attachment(order, SimpleUploadedFile('synthetic-demo.stl', mesh), 'STL', actor)
            order, _ = execute_case_command(order.pk, 'inspection', {
                'stage': 'DIGITAL', 'checks': dict.fromkeys(['margins', 'occlusion', 'space', 'scan_quality'], True),
            }, actor, 'MANAGER', uuid.uuid4())
            order.status, order.reception_validated = 'CONTROLE_DOSSIER', True
            order.save()
            order.status = 'PLANIFICATION'
            order.save()
            order.production_method, order.delivery_date = method, timezone.localdate() + timedelta(days=4 if service == 'STANDARD' else 2)
            order.status = 'SALLE_CAO'
            order.save()
