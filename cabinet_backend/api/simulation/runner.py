"""Event-driven synthetic actors over the real API and scheduler."""
from copy import copy
from datetime import datetime, time, timedelta
import heapq
import uuid

from django.db import transaction
from django.db.models import F, Q
from django.utils import timezone
from django_tenants.utils import tenant_context
from api.models import Prescription, Machine, CaseAttachment
from api.planning import recalculate, deadline, reservations, slot_for, TERMINAL, EQUIPMENT_PHASES
from api.planning_models import PlanningTask, PlanningSettings
from api.case_commands import CHECKS, qr_token
from api.workflow_spec import rework_restart_options
from .clock import Clock, simulation_clock
from .client import SimClient
from .guards import schema_guard
from .resources import bootstrap
from .scenarios import START, HOLIDAY, TZ, PROFILES, demand


class Simulation:
    def __init__(self, scenario='normal', seed=20261209, days=28, grand_daily=60, tiny=False, profiles=None, progress=None, actor_suffix=''):
        self.actor_suffix=actor_suffix
        self.scenario,self.seed,self.days,self.grand_daily,self.tiny=scenario,seed,days,grand_daily,tiny
        self.profiles=list(profiles or PROFILES)
        self.clock=Clock(START)
        self.end=START+timedelta(days=days)
        self.api=SimClient()
        self.events=[]
        self.serial=0
        self.wakes=set()
        self.labs=[]
        self.by_schema={}
        self.progress=progress or (lambda message:None)
        self.last_day=None

    def schedule(self, at, kind, lab, payload=None):
        if at < self.clock():
            raise RuntimeError('A simulator event attempted to reverse time.')
        if kind=='wake':
            key=(lab.schema,at)
            if key in self.wakes:
                return
            self.wakes.add(key)
        self.serial+=1
        heapq.heappush(self.events,(at,self.serial,kind,lab.schema,payload))

    def command(self, lab, order, action, data=None, role=None, account=None, dentist=False, expected=200):
        person=account or (lab.accounts['DENTIST'][lab.cases[str(order)]['plan']['clinic_index']] if dentist
                           else lab.accounts[role or 'RECEPTION'][0])
        response=self.api.command(person,'localhost' if dentist else lab.host,str(order),action,data,
                                  expected=expected,dentist=dentist,schema=lab.schema)
        lab.dirty=True
        return response

    def run(self, *, isolation=True):
        with simulation_clock(self.clock,self.seed):
            self.labs=bootstrap(self.profiles,self.scenario,self.days,self.actor_suffix)
            self.by_schema={lab.schema:lab for lab in self.labs}
            by_profile={lab.profile.key:lab for lab in self.labs}
            plans=demand(self.scenario,self.seed,self.days,self.grand_daily,self.tiny,self.profiles)
            for plan in plans:
                self.schedule(plan['at'],'arrival',by_profile[plan['profile']],plan)
            if self.scenario=='mixed' and 'GRAND' in by_profile and self.days>10:
                lab=by_profile['GRAND']
                mill=next(machine for machine in lab.machines if machine.machine_type=='USINEUSE_CNC')
                self.schedule(START+timedelta(days=9),'outage',lab,(mill.pk,True))
                self.schedule(START+timedelta(days=10),'outage',lab,(mill.pk,False))
            while self.events and self.events[0][0]<self.end:
                at=self.events[0][0]
                self.clock.advance(at)
                if self.last_day != at.date():
                    self.progress(f'SIM {self.scenario}: {at.date().isoformat()}')
                    self.last_day=at.date()
                touched=set()
                while self.events and self.events[0][0]==at:
                    _,_,kind,schema,payload=heapq.heappop(self.events)
                    lab=self.by_schema[schema]
                    touched.add(schema)
                    with tenant_context(lab.tenant):
                        schema_guard(schema,lab.cases)
                        self.handle(lab,kind,payload)
                for lab in self.labs:
                    if lab.schema not in touched:
                        continue
                    with tenant_context(lab.tenant):
                        self.dispatch(lab)
            self.clock.advance(self.end)
            from .metrics import lab_metrics
            metrics={lab.profile.key:lab_metrics(lab,START,self.end,self.clock()) for lab in self.labs}
            proof=None
            if isolation:
                from .isolation import verify_isolation
                proof=verify_isolation(self)
            return {'label':'Données synthétiques - simulation','scenario':self.scenario,'seed':self.seed,
                'simulated_start':START.isoformat(),'simulated_end':self.end.isoformat(),'days':self.days,
                'scope':'real-api-workflow-and-planning','grand_daily_cases':self.grand_daily,
                'nominal_grand_daily_cases':60,'tiny':self.tiny,'arrival_pattern':'one morning batch per working day; Saturday half volume','labs':metrics,'isolation':proof}

    def create(self, lab, plan):
        person=lab.accounts['DENTIST'][plan['clinic_index']]
        data={'laboratory_id':lab.schema,'partner_clinic':lab.clinics[plan['clinic_index']].pk,
              'patient_ref':plan['reference'],'impression_type':'PHYSIQUE' if plan['physical'] else 'NUMERIQUE',
              'disinfected':True,'delivery_service':plan['service'],'design_validation_requested':plan['design'],
              'clinical_items':[{'tooth_number':11,'function':'Couronne','form':'Anatomique',
                                 'shade':'A2','material':plan['material']}]}
        created=self.api.json(person,'localhost','post','/platform/dentist/orders/',data,expected=201)
        case=str(created['id'])
        lab.cases[case]={'plan':plan,'entered':self.clock(),'status':'DEMANDE_RECUE','used':set(),
                         'external':None,'first_delivery':None,'last_delivery':None,'delivered_deadline':None,
                         'first_rework':None,'completed':None}
        if not plan['physical']:
            self.api.upload(lab.accounts['RECEPTION'][0],lab.host,case,'STL')
        if plan['service']=='NEXT_DAY':
            self.command(lab,case,'quote',{'surcharge':'250.00'},role='COMPTABILITE')
        self.command(lab,case,'accept',role='RECEPTION')
        self.changed(lab,case)

    def changed(self, lab, case):
        state=lab.cases[str(case)]
        order=Prescription.objects.get(pk=case)
        if state['status']!=order.status:
            state['entered'],state['status'],state['external']=self.clock(),order.status,None
        if order.status=='LIVRE':
            if state['first_delivery'] is None:
                state['first_delivery']=self.clock()
            state['last_delivery']=self.clock()
            state['delivered_deadline']=deadline(order,PlanningSettings.objects.get(pk=1))
        if order.status=='CLOTURE':
            state['completed']=self.clock()
        external={'ATTENTE_RAMASSAGE':'pickup','EN_ROUTE_LABO':'deposit','PRET_EXPEDITION':'checkout',
                  'EN_ROUTE_CABINET':'delivery','VALIDATION_CAO':'design','RETOUR_DEMANDE':'resubmit',
                  'LIVRE':'fitting','ESSAYAGE':'fitting'}.get(order.status)
        if external and state['external'] is None:
            when=(self.next_round(self.clock()) if external in {'pickup','checkout'} else
                  self.clock()+timedelta(hours=1) if external in {'deposit','delivery'} else
                  self.clock()+timedelta(days=1) if external=='resubmit' else
                  self.clock()+timedelta(hours=4))
            state['external']=external
            self.schedule(when,external,lab,str(case))
        lab.dirty=True

    @staticmethod
    def next_round(now):
        day=now.astimezone(TZ).date()
        for offset in range(9):
            candidate=day+timedelta(days=offset)
            if candidate.weekday()==6 or candidate==HOLIDAY:
                continue
            for hour in [10,16]:
                value=datetime.combine(candidate,time(hour),TZ)
                if value>=now:
                    return value
        raise RuntimeError('No courier round found in the scenario calendar.')

    def handle(self, lab, kind, payload):
        if kind=='arrival':
            self.create(lab,payload)
            return
        if kind=='wake':
            self.wakes.discard((lab.schema,self.clock()))
            return
        if kind=='outage':
            machine,down=payload
            self.api.json(lab.accounts['MANAGER'][0],lab.host,'patch',f'/api/machines/{machine}/',
                          {'status':'PANNE' if down else 'ACTIF'})
            lab.outages.append({'at':self.clock().isoformat(),'machine':machine,'down':down})
            lab.dirty=True
            return
        if kind in {'work','launch','cycle','unload','finish-unload'}:
            case,task_id=payload
            task=PlanningTask.objects.select_related('assigned_employee__platform_account','machine').get(pk=task_id)
            order=Prescription.objects.get(pk=case)
            if task.status in TERMINAL or task.workflow_step!=order.status:
                return
            person=task.assigned_employee.platform_account
            data={'task':str(task.pk),'notes':'SIM - explicit synthetic equipment/work acknowledgement'}
            if kind=='work':
                self.finish_work(lab,order,task,person)
            elif kind=='launch':
                self.command(lab,case,'planning-launch-cycle',data,account=person)
                self.schedule(self.clock()+timedelta(minutes=task.estimated_duration_minutes-task.setup_minutes-task.unload_minutes),
                              'cycle',lab,(case,task_id))
            elif kind=='cycle':
                self.command(lab,case,'planning-cycle-finished',data,account=person)
                self.schedule(self.clock(),'unload',lab,(case,task_id))
            elif kind=='unload':
                start=self.unload_slot(task)
                if start is None:
                    return
                if start>self.clock():
                    self.schedule(start,'unload',lab,(case,task_id))
                else:
                    self.command(lab,case,'planning-begin-unload',data,account=person)
                    self.schedule(self.clock()+timedelta(minutes=task.unload_minutes),'finish-unload',lab,(case,task_id))
            else:
                self.command(lab,case,'planning-complete',data,account=person)
                self.changed(lab,case)
            return
        case=str(payload)
        state=lab.cases[case]
        order=Prescription.objects.get(pk=case)
        if state['external']!=kind:
            return
        state['external']=None
        lab.waits.setdefault(order.status,[]).append(max(0,(self.clock()-state['entered']).total_seconds()/60))
        if kind in {'pickup','deposit','checkout'}:
            action={'pickup':'pickup','deposit':'lab-deposit','checkout':'checkout'}[kind]
            if kind=='checkout':
                pin=self.command(lab,case,'issue-pin',dentist=True)['result']['pin_once']
                state['pin']=pin
            self.command(lab,case,action,{'qr_token':qr_token(order)},role='COURIER')
        elif kind=='delivery':
            self.command(lab,case,'confirm-delivery',{'pin':state.pop('pin')},role='COURIER')
        elif kind=='resubmit':
            self.command(lab,case,'resubmit',dentist=True)
        elif kind=='design':
            review=order.design_reviews.filter(status='PENDING').get()
            failed=self.failure(state,'design')
            self.command(lab,case,'design-decision',{'review':str(review.pk),
                'decision':'CHANGES_REQUESTED' if failed else 'APPROVED','notes':'SIM - explicit synthetic dentist decision'},dentist=True)
            if failed:
                self.command(lab,case,'pause',{'paused':False,'notes':'SIM - begin requested design correction'},role='CAO')
        elif kind=='fitting':
            if self.failure(state,'fitting'):
                self.command(lab,case,'fitting',{'passed':False},dentist=True,expected=400)
                self.rework(lab,order,'CLINIC',dentist=True)
            else:
                self.command(lab,case,'fitting',{'passed':True},dentist=True)
        self.changed(lab,case)

    @staticmethod
    def failure(state, key):
        if state['plan']['failures'][key] and key not in state['used']:
            state['used'].add(key)
            return True
        return False

    @staticmethod
    def restart_step(order, *, model=False):
        preferred=('COULEE_PLATRE' if model else
                   'MODELAGE' if order.production_method=='CONVENTIONNEL' else 'SALLE_CAO')
        if preferred not in rework_restart_options(order):
            raise RuntimeError('Synthetic correction has no allowed responsible restart step.')
        return preferred

    def rework(self, lab, order, origin='LAB', role='QUALITE', dentist=False, model=False):
        state=lab.cases[str(order.pk)]
        state['first_rework']=state['first_rework'] or self.clock()
        restart=self.restart_step(order,model=model)
        self.command(lab,order.pk,'rework',{'origin':origin,'cause':'SIM - documented synthetic non-compliance',
            'corrective_action':'SIM - explicit correction at the responsible step','restart_status':restart,'losses':[]},
            role=role,dentist=dentist)

    def finish_work(self, lab, order, task, person):
        case=str(order.pk)
        state=lab.cases[case]
        step=order.status
        if step in {'CONTROLE_DOSSIER','CONTROLE_MODELE','CONTROLE_QUALITE'}:
            stage='MODEL' if step=='CONTROLE_MODELE' else 'QUALITY' if step=='CONTROLE_QUALITE' else 'PHYSICAL' if order.impression_type=='PHYSIQUE' else 'DIGITAL'
            key={'MODEL':'model','QUALITY':'quality','PHYSICAL':'intake','DIGITAL':'intake'}[stage]
            failed=self.failure(state,key)
            checks=dict.fromkeys(sorted(CHECKS[stage]),True)
            photo=None
            if failed:
                checks[sorted(checks)[0]]=False
                photo=self.api.upload(person,lab.host,case,'PHOTO',photo=True)['id']
            self.command(lab,case,'inspection',{'stage':stage,'checks':checks,'advance':True,
                'photo':photo,'notes':'SIM - synthetic failed check' if failed else 'SIM - explicit synthetic passing checks'},account=person)
            if failed and stage in {'MODEL','QUALITY'}:
                self.rework(lab,order,role=task.required_role,model=stage=='MODEL')
        elif step=='PLANIFICATION':
            plan=state['plan']
            self.api.json(lab.accounts['MANAGER'][0],lab.host,'post','/api/production-lots/',
                {'code':plan['reference']+'-LOT','prescriptions':[case]},expected=201)
            days={'STANDARD':4,'EXPRESS':2,'NEXT_DAY':1}[plan['service']]
            self.command(lab,case,'advance',{'production_method':plan['route'],
                'thermal_treatment':'FRITTAGE' if plan['material']=='Zircone' and plan['route']=='CFAO' else 'CRISTALLISATION' if plan['material']=='E-Max' and plan['route']=='CFAO' else 'AUCUN',
                'delivery_date':(order.created_at.astimezone(TZ).date()+timedelta(days=days)).isoformat()},account=person)
        elif step=='ANALYSE_DEMANDE':
            self.command(lab,case,'advance',{'analysis_validated':True},account=person)
        elif step=='A_CONFIRMER':
            self.command(lab,case,'advance',{'reception_validated':True},account=person)
        elif step=='SALLE_CAO' and order.design_validation_requested and not order.design_reviews.filter(
                production_attempt=order.production_attempt,status='APPROVED').exists():
            attachment=self.api.upload(person,lab.host,case,'DESIGN')
            self.command(lab,case,'design-request',{'attachment':attachment['id']},account=person)
        else:
            self.command(lab,case,'planning-complete',{'task':str(task.pk),'notes':'SIM - explicit synthetic work completion'},account=person)
        self.changed(lab,case)

    def unload_slot(self, task):
        employee=task.assigned_employee
        others=PlanningTask.objects.exclude(pk=task.pk).filter(
            Q(locked=True)|Q(manual_block=True)|Q(status__in=['IN_PROGRESS','PAUSED'])|Q(resource_phase__in=EQUIPMENT_PHASES))
        probe=copy(task)
        probe.resource_phase='MANUAL'
        probe.machine_type=''
        probe.estimated_duration_minutes=task.unload_minutes
        result=slot_for(employee,probe,None,1,self.clock(),PlanningSettings.objects.get(pk=1),reservations(others,self.clock()))
        return result[0] if result else None

    def try_start(self, lab, task):
        # A command may rebuild movable bookings before validating the selected task.
        # Respect a refused start; never use a supervisor override to force capacity.
        if self.clock() != timezone.now():
            raise RuntimeError('Simulator and API clocks disagree.')
        case=str(task.prescription_id)
        version=Prescription.objects.get(pk=case).state_version
        fresh=PlanningTask.objects.get(pk=task.pk)
        diagnostic={'event_clock':self.clock().isoformat(),'api_clock':timezone.now().isoformat(),
                    'selected_start':task.planned_start.isoformat() if task.planned_start else None,
                    'fresh_start':fresh.planned_start.isoformat() if fresh.planned_start else None,
                    'schema':lab.schema,'step':task.workflow_step}
        response=self.api.request(task.assigned_employee.platform_account,lab.host,'post',
            f'/api/prescriptions/{case}/command/',
            {'action':'planning-start','data':{'task':str(task.pk)}},expected=None)
        if response.status_code==200:
            return True
        data=response.json()
        details=data if isinstance(data,list) else [data.get('detail') or data.get('error')] if isinstance(data,dict) else []
        retryable={
            'Créneau futur : attendez le début prévu ou demandez une replanification au responsable.',
            'Conflit de réservation : employé ou équipement déjà occupé.',
        }
        if response.status_code!=400 or len(details)!=1 or details[0] not in retryable:
            raise RuntimeError(f'SIM unexpected planning-start refusal: HTTP {response.status_code}; {diagnostic}')
        if Prescription.objects.get(pk=case).state_version!=version:
            raise RuntimeError('A refused simulation start changed source state.')
        lab.deferred_starts+=1
        if len(lab.start_diagnostics)<10:
            lab.start_diagnostics.append({**diagnostic,'reason':details[0]})
        with transaction.atomic():
            recalculate(actor='SIM scheduler after guarded refusal',now=self.clock())
        task.refresh_from_db()
        self.schedule(max(self.clock()+timedelta(minutes=1),task.planned_start or self.clock()),'wake',lab)
        lab.dirty=False
        return False

    def dispatch(self, lab):
        schema_guard(lab.schema,lab.cases)
        if lab.dirty:
            with transaction.atomic():
                recalculate(actor='SIM scheduler',now=self.clock())
            lab.dirty=False
        # Requery after each start: the real start command can move automatic reservations.
        for _ in range(len(lab.employees)+1):
            tasks=list(PlanningTask.objects.filter(status='READY',prescription__status=F('workflow_step'),
                production_attempt=F('prescription__production_attempt'),intake_revision=F('prescription__intake_revision'))
                .select_related('assigned_employee__platform_account','machine').order_by('planned_start','prescription_id','sequence'))
            ready=next((task for task in tasks if task.planned_start and task.planned_start<=self.clock()),None)
            if ready is None:
                future=[task.planned_start for task in tasks if task.planned_start and task.planned_start>self.clock()]
                if future:
                    self.schedule(min(future),'wake',lab)
                break
            case=str(ready.prescription_id)
            state=lab.cases[case]
            if not self.try_start(lab,ready):
                return
            wait=max(0,(self.clock()-state['entered']).total_seconds()/60)
            lab.waits.setdefault(ready.workflow_step,[]).append(wait)
            ready.refresh_from_db()
            self.schedule(self.clock()+timedelta(minutes=ready.setup_minutes if ready.resource_phase=='SETUP' else ready.estimated_duration_minutes),
                'launch' if ready.resource_phase=='SETUP' else 'work',lab,(case,str(ready.pk)))
            lab.dirty=False
