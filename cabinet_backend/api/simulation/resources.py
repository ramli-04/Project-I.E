"""Use the product's tenant, account and planning resource models unchanged."""
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
import secrets

from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password
from django.core.management.base import CommandError
from django.db import transaction
from django_tenants.utils import schema_context
from customers.models import Client, Domain, PlatformAccount
from customers.views import login_key
from api.models import EmployeeProfile, Machine, PartnerClinic, Prescription
from api.planning_models import EmployeeAvailability, EmployeeQualification, PlanningSettings
from api.planning import DEFAULT_RULES
from .guards import SCHEMAS, schema_guard
from .scenarios import START, HOLIDAY, TZ


@dataclass
class Lab:
    profile: object
    tenant: object
    host: str
    accounts: dict
    employees: list
    clinics: list
    machines: list
    cases: dict = field(default_factory=dict)
    dirty: bool = True
    waits: dict = field(default_factory=dict)
    outages: list = field(default_factory=list)
    deferred_starts: int = 0
    start_diagnostics: list = field(default_factory=list)

    @property
    def schema(self):
        return self.tenant.schema_name


def account(name, role, tenant=None):
    with schema_context('public'):
        return PlatformAccount.objects.create(name=name,login_key=login_key(name),
            role=role if role in {'DENTIST','COURIER'} else 'LAB',
            workstation_role=role if role not in {'DENTIST','COURIER'} else 'MANAGER',
            laboratory=tenant,password_hash=make_password(secrets.token_urlsafe(24)))


def bootstrap(profiles, scenario, days, actor_suffix=''):
    def create_account(name,role,tenant=None):
        return account(name+actor_suffix,role,tenant)
    with schema_context('public'):
        if Client.objects.exclude(schema_name__in=['public',*SCHEMAS.values()]).exists():
            raise CommandError('Base de simulation refusée : laboratoire inattendu.')
        dentists=[create_account('SIM-DENTIST-'+key,'DENTIST') for key in ['A','B']]
    labs=[]
    for profile in profiles:
        schema=SCHEMAS[profile.key]
        with schema_context('public'):
            tenant,created=Client.objects.get_or_create(schema_name=schema,
                defaults={'name':'SIM-'+profile.key+' - synthetic laboratory'})
            Domain.objects.get_or_create(domain=f'sim-{profile.key.lower()}.localhost',
                                         defaults={'tenant':tenant,'is_primary':True})
        schema_guard(schema)
        with schema_context(schema):
            if not created or Prescription.objects.exists():
                raise CommandError('Jeu synthétique déjà présent ; choisissez un nouveau SIM_RUN, sans effacer de volume.')
        roles={'MANAGER':[create_account('SIM-'+profile.key+'-MANAGER','MANAGER',tenant)],
               'COMPTABILITE':[create_account('SIM-'+profile.key+'-COMPTABILITE','COMPTABILITE',tenant)],
               'COURIER':[create_account('SIM-'+profile.key+'-COURIER','COURIER',tenant)]}
        employees=[]
        with schema_context(schema):
            for role,count in [('RECEPTION',1),('QUALITE',1),('CAO',profile.cad),('FAO',profile.fabrication)]:
                roles[role]=[]
                for index in range(count):
                    person=create_account(f'SIM-{profile.key}-{role}-{index+1}',role,tenant)
                    roles[role].append(person)
                    with schema_context('public'):
                        user=get_user_model().objects.create_user(username=login_key(person.name),is_active=True)
                        user.set_unusable_password()
                        user.save(update_fields=['password'])
                    employee=EmployeeProfile.objects.create(platform_account=person,user=user,role=role,
                        contract_type='CDI',hire_date=START.date()-timedelta(days=30))
                    EmployeeQualification.objects.create(employee=employee,qualification='sim-'+role.lower(),proficiency_level=3)
                    employees.append(employee)
                    for weekday in range(6):
                        EmployeeAvailability.objects.create(employee=employee,availability_type='SHIFT',weekday=weekday,
                            start_time=time(9 if scenario=='ramadan' else 8),
                            end_time=time(12 if weekday==5 else 15 if scenario=='ramadan' else 18))
                    EmployeeAvailability.objects.create(employee=employee,availability_type='ABSENCE',
                        starts_at=datetime.combine(HOLIDAY,time(0),TZ),ends_at=datetime.combine(HOLIDAY+timedelta(days=1),time(0),TZ),
                        notes='SIM - fixed synthetic holiday')
                    for offset in range(days):
                        day=START.date()+timedelta(days=offset)
                        if day.weekday()==4:
                            EmployeeAvailability.objects.create(employee=employee,availability_type='BREAK',
                                starts_at=datetime.combine(day,time(12),TZ),
                                ends_at=datetime.combine(day,time(13 if scenario=='ramadan' else 14),TZ),
                                notes='SIM - Friday midday break')
            rules={step:{'qualifications':['sim-'+role.lower()]} for step,(role,_,_) in DEFAULT_RULES.items()}
            for step in ['USINAGE_CNC','TRAITEMENT_THERMIQUE','IMPRESSION_3D']:
                rules[step].update(unattended=True,setup_minutes=10,unload_minutes=10)
            PlanningSettings.objects.create(pk=1,working_days=list(range(6)),open_time=time(8),close_time=time(18),
                break_start=time(12),break_end=time(12 if scenario=='ramadan' else 13),step_rules=rules)
            machines=[]
            for kind,count in [('SCANNER',1),('USINEUSE_CNC',profile.mills),
                               ('FOUR_FRITTAGE',profile.furnaces),('IMPRESSION_3D',profile.printers)]:
                for index in range(count):
                    machines.append(Machine.objects.create(name=f'SIM-{profile.key}-{kind}-{index+1}',
                        machine_type=kind,capacity=1,status='ACTIF'))
            clinics=[PartnerClinic.objects.create(name=f'SIM-{profile.key}-CLINIC-{index+1}',
                pickup_address='SIM - synthetic address only',contact_phone='0000000000',
                platform_dentist=dentist,payment_terms_days=60) for index,dentist in enumerate(dentists)]
        roles['DENTIST']=dentists
        labs.append(Lab(profile,tenant,f'sim-{profile.key.lower()}.localhost',roles,employees,clinics,machines))
    return labs
