"""Existing tasks remain manual until an unlocked automatic replan.

No historical task is rewritten. Live reservations use unbounded holds, so an
overdue cycle cannot silently free equipment. PostgreSQL 14+ multirange GiST
operators protect the two attended windows without booking their gap.
"""
import django.contrib.postgres.constraints
import django.contrib.postgres.fields
from django.db import migrations, models


FUNCTIONS = """
CREATE FUNCTION api_employee_booking(phase varchar, s timestamptz, e timestamptz,
    phase_start timestamptz, setup integer, unload integer)
RETURNS tstzmultirange LANGUAGE sql IMMUTABLE AS $$
SELECT CASE
 WHEN s IS NULL OR e IS NULL THEN '{}'::tstzmultirange
 WHEN phase = 'MANUAL' THEN tstzmultirange(tstzrange(s,e,'[)'))
 WHEN phase = 'PLANNED' THEN tstzmultirange(
   tstzrange(s,s + setup * interval '1 minute','[)'),
   tstzrange(e - unload * interval '1 minute',e,'[)'))
 WHEN phase IN ('SETUP','UNLOADING') THEN
   tstzmultirange(tstzrange(COALESCE(phase_start,s),NULL,'[)'))
 ELSE '{}'::tstzmultirange END;
$$;
CREATE FUNCTION api_machine_booking(phase varchar, s timestamptz, e timestamptz)
RETURNS tstzrange LANGUAGE sql IMMUTABLE AS $$
SELECT CASE WHEN phase IN ('SETUP','CYCLE','AWAITING_UNLOAD','UNLOADING')
 THEN tstzrange(s,NULL,'[)') ELSE tstzrange(s,e,'[)') END;
$$;
"""


class Migration(migrations.Migration):
    dependencies = [('api','0024_production_planning')]
    operations = [
        migrations.RemoveConstraint('planningtask','planning_employee_no_overlap'),
        migrations.RemoveConstraint('planningtask','planning_machine_no_overlap'),
        migrations.AddField('planningtask','resource_phase',models.CharField(max_length=20,default='MANUAL',choices=[
            ('MANUAL','Travail manuel'),('PLANNED','Cycle planifié'),('SETUP','Chargement / réglage'),
            ('CYCLE','Cycle autonome'),('AWAITING_UNLOAD','En attente de déchargement'),
            ('UNLOADING','Déchargement'),('FINISHED','Déchargement confirmé')])),
        migrations.AddField('planningtask','setup_minutes',models.PositiveSmallIntegerField(default=10)),
        migrations.AddField('planningtask','unload_minutes',models.PositiveSmallIntegerField(default=10)),
        migrations.AddField('planningtask','phase_started_at',models.DateTimeField(null=True,blank=True)),
        migrations.AddField('planningtask','cycle_started_at',models.DateTimeField(null=True,blank=True)),
        migrations.AddField('planningtask','cycle_completed_at',models.DateTimeField(null=True,blank=True)),
        migrations.AddField('planningtask','unloaded_at',models.DateTimeField(null=True,blank=True)),
        migrations.RunSQL(FUNCTIONS,reverse_sql='DROP FUNCTION api_employee_booking(varchar,timestamptz,timestamptz,timestamptz,integer,integer); DROP FUNCTION api_machine_booking(varchar,timestamptz,timestamptz);'),
        migrations.AddConstraint('planningtask',models.CheckConstraint(
            condition=models.Q(resource_phase='MANUAL') | (models.Q(setup_minutes__gte=1,unload_minutes__gte=1)
                & models.Q(estimated_duration_minutes__gt=models.F('setup_minutes')+models.F('unload_minutes'))),
            name='planning_phase_durations')),
        migrations.AddConstraint('planningtask',django.contrib.postgres.constraints.ExclusionConstraint(
            name='planning_employee_no_overlap',expressions=[('assigned_employee','='),
                (models.Func('resource_phase','planned_start','planned_end','phase_started_at','setup_minutes','unload_minutes',
                    function='api_employee_booking',output_field=django.contrib.postgres.fields.DateTimeRangeField()),'&&')],
            condition=(models.Q(status__in=['READY','SCHEDULED','IN_PROGRESS','PAUSED']) | models.Q(resource_phase__in=['SETUP','CYCLE','AWAITING_UNLOAD','UNLOADING']))
                & models.Q(assigned_employee__isnull=False,planned_start__isnull=False))),
        migrations.AddConstraint('planningtask',django.contrib.postgres.constraints.ExclusionConstraint(
            name='planning_machine_no_overlap',expressions=[('machine','='),('machine_slot','='),
                (models.Func('resource_phase','planned_start','planned_end',function='api_machine_booking',
                    output_field=django.contrib.postgres.fields.DateTimeRangeField()),'&&')],
            condition=(models.Q(status__in=['READY','SCHEDULED','IN_PROGRESS','PAUSED']) | models.Q(resource_phase__in=['SETUP','CYCLE','AWAITING_UNLOAD','UNLOADING']))
                & models.Q(machine__isnull=False,planned_start__isnull=False))),
    ]
