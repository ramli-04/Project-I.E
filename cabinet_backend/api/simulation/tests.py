"""Fast unit checks plus isolated tiny real-command integration scenarios."""
from datetime import timedelta
import os
from pathlib import Path
import tempfile
from unittest.mock import patch

from django.core.cache import cache
from django.core.management.base import CommandError
from django.db import connection
from django.test import SimpleTestCase, TransactionTestCase, override_settings
from django_tenants.utils import schema_context, tenant_context
from customers.models import Client, Domain, PlatformAccount
from api.models import Prescription, TaskOutbox
from .clock import Clock, simulation_clock
from .guards import environment_guard, schema_guard, SCHEMAS
from .metrics import distribution, overlap_minutes, waiting_summary
from .runner import Simulation
from .scenarios import START, HOLIDAY, PROFILES, demand


class SimulationUnitTests(SimpleTestCase):
    def test_seeded_two_day_inputs_and_profile_staffing(self):
        self.assertEqual(demand('normal',42,days=2,tiny=True),demand('normal',42,days=2,tiny=True))
        self.assertNotEqual(demand('normal',42,days=2),demand('normal',43,days=2))
        self.assertEqual([p.staffing['total_scheduled_staff'] for p in PROFILES],[4,7,12])
        self.assertEqual([p.cad+p.fabrication for p in PROFILES],[2,5,10])

    def test_calendar_and_peak_inputs_are_explicit(self):
        normal=demand('normal',42)
        mixed=demand('mixed',42)
        self.assertTrue(all(row['at'].weekday()!=6 and row['at'].date()!=HOLIDAY for row in normal))
        self.assertEqual(sum(row['profile']=='MOYEN' for row in mixed),
                         sum(row['profile']=='MOYEN' for row in normal)*1.5)
        self.assertTrue(all(row['at'].hour>=9 for row in demand('ramadan',42)))

    def test_clock_and_captured_defaults_restore_and_model_ids_repeat(self):
        field=TaskOutbox._meta.get_field('next_attempt_at')
        original=field.default
        ids=[]
        for _ in range(2):
            clock=Clock(START)
            with simulation_clock(clock,42):
                self.assertEqual(TaskOutbox().next_attempt_at,START)
                ids.append(Prescription().pk)
                clock.advance(START+timedelta(days=1))
                self.assertEqual(field.get_default(),clock())
                with self.assertRaises(ValueError):clock.advance(START)
            self.assertIs(field.default,original)
        self.assertEqual(ids[0],ids[1])

    def test_metric_fixture_has_hand_checked_median_p90_and_overlap(self):
        self.assertEqual(distribution([1,2,3,4,10]),{'median':3,'p90':10,'count':5})
        waits=waiting_summary({'SALLE_CAO':[10,20]},[('SALLE_CAO',40)])
        self.assertEqual(waits[0]['mean_wait_minutes'],23.333)
        self.assertEqual(waits[0]['still_waiting'],1)
        self.assertEqual(distribution([]),{'median':None,'p90':None,'count':0})
        self.assertEqual(overlap_minutes(START,START+timedelta(hours=2),START+timedelta(hours=1),START+timedelta(hours=3)),60)

    def test_report_rejects_incomplete_or_unverified_runs(self):
        from .report import render
        with self.assertRaises(ValueError):render([])
        rows=[{'scenario':key,'days':28,'tiny':False,'scope':'benchmark-only-no-isolation-proof','isolation':None}
              for key in ['normal','ramadan','mixed']]
        with self.assertRaises(ValueError):render(rows)

    def test_command_refuses_missing_flag_wrong_database_and_presentation_schema(self):
        with patch.dict(os.environ,{'GESTION_LABO_SIMULATION':'0','GESTION_LABO_COMPOSE_PROJECT':'cabinet-sim'}):
            with self.assertRaises(CommandError):environment_guard()
        with patch.dict(os.environ,{'GESTION_LABO_SIMULATION':'1','GESTION_LABO_COMPOSE_PROJECT':'cabinet-sim'}):
            with self.assertRaises(CommandError):environment_guard() # normal suite uses the guarded test DB
        for schema in ['simlab','public','native','cabinet-ui-verification']:
            with self.assertRaises(CommandError):schema_guard(schema)


@override_settings(OUTBOX_PUBLISH_ON_COMMIT=False,EXTERNAL_DELIVERY_ENABLED=False,
                   PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'],
                   CACHES={'default':{'BACKEND':'django.core.cache.backends.locmem.LocMemCache',
                                     'KEY_FUNCTION':'django_tenants.cache.make_key'}})
class SimulationIntegrationTests(TransactionTestCase):
    def setUp(self):
        super().setUp()
        self.assertTrue(connection.settings_dict['NAME'].startswith('test_'))
        connection.set_schema_to_public()
        self.files=tempfile.TemporaryDirectory()
        self.media=override_settings(PRIVATE_MEDIA_ROOT=self.files.name)
        self.media.enable()
        with schema_context('public'):
            public,_=Client.objects.get_or_create(schema_name='public',defaults={'name':'SIM test public'})
            Domain.objects.get_or_create(domain='localhost',defaults={'tenant':public,'is_primary':True})
        self.sim=None

    def clean_labs(self):
        self.assertTrue(connection.settings_dict['NAME'].startswith('test_'))
        with schema_context('public'):
            for lab in list(Client.objects.filter(schema_name__in=SCHEMAS.values())):
                PlatformAccount.objects.filter(laboratory=lab).update(laboratory=None)
                lab.delete(force_drop=True)
        cache.clear() # Only this test's isolated LocMem cache, never a simulation Redis instance.

    def tearDown(self):
        self.clean_labs()
        self.media.disable()
        self.files.cleanup()
        connection.set_schema_to_public()
        super().tearDown()

    def test_explicit_failures_rework_and_equipment_routes_use_real_guards(self):
        def failed_cases(*args,**kwargs):
            rows=demand(*args,**kwargs)
            for row in rows:
                route={'PETIT':'CONVENTIONNEL','MOYEN':'CFAO','GRAND':'IMPRESSION_3D'}[row['profile']]
                row.update(route=route,material={'CONVENTIONNEL':'100% Métal',
                    'CFAO':'Zircone','IMPRESSION_3D':'Provisoire Résine'}[route],
                    physical=row['profile']!='GRAND',design=route!='CONVENTIONNEL',
                    failures=dict.fromkeys(['intake','model','design','quality','fitting'],True))
            return rows
        self.sim=Simulation(seed=42,days=10,tiny=True,actor_suffix='-FAILURES')
        with patch('api.simulation.runner.demand',side_effect=failed_cases):
            result=self.sim.run(isolation=False)
        for lab in self.sim.labs:
            data=result['labs'][lab.profile.key]
            self.assertEqual(data['cases_created'],1)
            self.assertEqual(data['cases_closed'],1)
            self.assertEqual(data['rework_count'],3 if lab.profile.key!='GRAND' else 2)
            expected=['intake','quality','fitting']
            if lab.profile.key!='GRAND':expected.append('model')
            if lab.profile.key!='PETIT':expected.append('design')
            for key in expected:self.assertEqual(data['executed_failures'][key],1)
            with tenant_context(lab.tenant):
                self.assertTrue(Prescription.objects.get().quality_validated)

    def test_two_day_report_is_deterministic_and_one_day_two_tenant_isolation_passes(self):
        reports=[]
        for suffix in ['-A','-B']:
            self.sim=Simulation(seed=42,days=2,tiny=True,profiles=PROFILES[:2],actor_suffix=suffix)
            reports.append(self.sim.run())
            self.assertGreater(reports[-1]['isolation']['attack_attempts'],0)
            self.assertEqual(reports[-1]['isolation']['leaks'],0)
            self.assertEqual(reports[-1]['isolation']['unauthorized_writes'],0)
            self.clean_labs()
        self.assertEqual(reports[0],reports[1])
        self.sim=Simulation(seed=42,days=1,tiny=True,profiles=PROFILES[:2],actor_suffix='-C')
        result=self.sim.run()
        self.assertEqual(result['isolation']['attack_attempts'],126)
        self.assertTrue(all(row['cases_delivered']==1 for row in result['labs'].values()))
        lab=self.sim.labs[0]
        with tenant_context(lab.tenant):
            case=next(key for key,state in lab.cases.items() if state['plan']['reference'].startswith('SIM-CACHE'))
            before=Prescription.objects.get(pk=case).state_version
            response=self.sim.command(lab,case,'advance',{'status':'CLOTURE'},role='RECEPTION',expected=400)
            self.assertEqual(Prescription.objects.get(pk=case).state_version,before)
            self.assertIn('commande métier spécialisée',str(response))
            # A stale local projection must wait for the real future slot without
            # advancing source state or bypassing the normal start command.
            from api.planning import recalculate
            from api.planning_models import PlanningTask
            from django.db import transaction
            with simulation_clock(self.sim.clock,9000):
                with transaction.atomic():recalculate(actor='SIM regression',now=self.sim.clock())
                future=PlanningTask.objects.filter(prescription_id=case,status='READY',
                    planned_start__gt=self.sim.clock()).select_related('assigned_employee__platform_account').first()
                self.assertIsNotNone(future)
                version=Prescription.objects.get(pk=case).state_version
                future.planned_start=self.sim.clock() # local stale copy only; no database write
                self.assertFalse(self.sim.try_start(lab,future))
                self.assertEqual(Prescription.objects.get(pk=case).state_version,version)
                self.assertEqual(lab.deferred_starts,1)
                self.assertTrue(any(kind=='wake' and at>self.sim.clock() for at,_,kind,_,_ in self.sim.events))
            plan=dict(lab.cases[case]['plan'])
            plan.update(reference='NON-SIM-TEST-GUARD',at=self.sim.clock())
            self.sim.create(lab,plan)
            with self.assertRaises(CommandError):schema_guard(lab.schema)
