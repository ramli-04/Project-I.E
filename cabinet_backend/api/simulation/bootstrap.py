"""Bootstrap only the isolated simulation platform, never the presentation seed."""
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE','cabinet_backend.settings')
import django
django.setup()
from django.core.management import call_command
from django_tenants.utils import schema_context
from customers.models import Client, Domain
from .guards import environment_guard, SCHEMAS

environment_guard()
call_command('migrate_schemas',shared=True,interactive=False)
with schema_context('public'):
    if Client.objects.exclude(schema_name__in=['public',*SCHEMAS.values()]).exists():
        raise SystemExit('La base de simulation contient un laboratoire inattendu ; initialisation refusée.')
    public,_=Client.objects.get_or_create(schema_name='public',defaults={'name':'SIM platform - synthetic only'})
    for hostname in ['localhost','127.0.0.1','backend','bootstrap']:
        Domain.objects.get_or_create(domain=hostname,defaults={'tenant':public,'is_primary':hostname=='localhost'})
call_command('migrate_schemas',tenant=True,interactive=False)
print('Plateforme de simulation isolée prête ; aucun dossier de démonstration créé.')
