import os
from django.conf import settings
from django.core.management.base import CommandError
from django_tenants.utils import schema_context

SCHEMAS = {'PETIT': 'simpetit', 'MOYEN': 'simmoyen', 'GRAND': 'simgrand'}


def environment_guard():
    database = settings.DATABASES['default']
    if (os.environ.get('GESTION_LABO_SIMULATION') != '1'
            or os.environ.get('GESTION_LABO_COMPOSE_PROJECT') != 'cabinet-sim'
            or not settings.CABINET_SIMULATION or settings.EXTERNAL_DELIVERY_ENABLED
            or database['NAME'] != 'cabinet_sim' or database['HOST'] != 'postgres'):
        raise CommandError('Simulation refusée : utilisez uniquement le projet Compose cabinet-sim et sa base cabinet_sim.')


def schema_guard(schema, expected_ids=None):
    if schema not in SCHEMAS.values():
        raise CommandError('Schéma de simulation refusé ; le laboratoire de présentation simlab est protégé.')
    from api.models import Prescription
    with schema_context(schema):
        if Prescription.objects.exclude(patient_ref__startswith='SIM-').exists():
            raise CommandError('Simulation refusée : ce laboratoire contient des dossiers non synthétiques.')

        if expected_ids is not None and Prescription.objects.exclude(pk__in=expected_ids).exists():
            raise CommandError('Simulation refusée : un dossier ne figure pas dans le registre de ce simulateur.')
