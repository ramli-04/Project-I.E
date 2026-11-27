"""End-of-run authorization checks against the real API; a leak fails the run."""
from datetime import datetime, timedelta, time
from decimal import Decimal
import hashlib
import json

from django.apps import apps
from django.core.cache import cache
from django.db.models import Sum
from django_tenants.utils import schema_context
from api.models import (Prescription, PlanningTask, BillingPeriod, FinanceInvoice, Payment,
                        CaseAttachment, TenantReadVersion, MessageDelivery)
from api.analytics import refresh_billing_catalog
from api.tasks import generate_invoice_pdf_task
from .guards import schema_guard
from .scenarios import TZ


class Assertions:
    def __init__(self):
        self.assertions=0
        self.attacks=0

    def check(self, condition, label):
        self.assertions+=1
        if not condition:
            raise AssertionError('SIM isolation failed: '+label)


def row_snapshot(labs):
    result={}
    for lab in labs:
        with schema_context(lab.schema):
            values={model._meta.label:model.objects.count() for model in apps.get_app_config('api').get_models()
                    if model._meta.managed and not model._meta.proxy}
            values['sources']=list(Prescription.objects.order_by('pk').values_list('id','status','state_version','updated_at'))
            values['tasks']=list(PlanningTask.objects.order_by('pk').values_list('id','status','updated_at'))
            result[lab.schema]=hashlib.sha256(json.dumps(values,default=str,sort_keys=True).encode()).hexdigest()
    return result


def verify_isolation(sim):
    proof=Assertions()
    # Extra control orders are outside the measurement window, labelled and counted separately.
    controls={lab.schema:0 for lab in sim.labs}
    first_two=sim.labs[:2]
    before={}
    for lab in first_two:
        with schema_context(lab.schema):
            rows=sim.api.rows(lab.accounts['MANAGER'][0],lab.host,'/api/prescriptions/')
            before[lab.schema]=({row['id'] for row in rows},TenantReadVersion.objects.get(name='active_orders').version)
    for lab in first_two:
        with schema_context(lab.schema):
            schema_guard(lab.schema)
            plan={'at':sim.clock(),'profile':lab.profile.key,'sequence':0,
                'reference':'SIM-CACHE-'+lab.profile.key,'route':'CONVENTIONNEL','service':'STANDARD',
                'material':'100% Métal','physical':False,'design':False,'clinic_index':1,
                'failures':dict.fromkeys(['intake','model','design','quality','fitting'],False)}
            sim.create(lab,plan)
            controls[lab.schema]+=1
    for lab in first_two:
        with schema_context(lab.schema):
            rows=sim.api.rows(lab.accounts['MANAGER'][0],lab.host,'/api/prescriptions/')
            ids={row['id'] for row in rows}
            proof.check(before[lab.schema][0]<ids,'interleaved write appears in its tenant cache')
            proof.check(TenantReadVersion.objects.get(name='active_orders').version>before[lab.schema][1],
                        'tenant cache generation advanced')
            proof.check(ids<=set(lab.cases),'cached case IDs belong to the local ledger')
            envelope=cache.get('active_orders')
            proof.check(bool(envelope) and {str(row['id']) for row in envelope['rows']}<=set(lab.cases),
                        'Redis envelope contains only local IDs')
    # Close only simulator-owned delivery periods after their month has ended.
    next_month=(sim.clock().date().replace(day=1)+timedelta(days=32)).replace(day=1)
    sim.clock.advance(datetime.combine(next_month,time(12),TZ))
    financial={}
    for index,lab in enumerate(sim.labs):
        with schema_context(lab.schema):
            schema_guard(lab.schema)
            period=BillingPeriod.objects.filter(closed_at__isnull=True,lines__contested=False,lines__excluded=False).order_by('month','pk').first()
            proof.check(period is not None,'a genuinely delivered case exists for finance/PDF isolation')
            invoice=sim.api.json(lab.accounts['COMPTABILITE'][0],lab.host,'post',f'/api/billing/periods/{period.pk}/close/')
            # Distinct residual balances also detect an aggregate result served from another tenant.
            balance=Decimal((index+1)*17)
            total=Decimal(invoice['total_amount'])
            proof.check(total>balance,'positive synthetic invoice is available')
            payment=sim.api.json(lab.accounts['COMPTABILITE'][0],lab.host,'post','/api/billing/payments/',
                {'clinic':period.clinic_id,'method':'ESPECES','amount':format(total-balance,'.2f'),
                 'received_on':sim.clock().date().isoformat(),
                 'allocations':[{'invoice':invoice['id'],'amount':format(total-balance,'.2f')}]},expected=201)
            source=invoice['lines'][0]['case_id']
            generate_invoice_pdf_task.run(lab.schema,source)
            refresh_billing_catalog(lab.schema)
            case=Prescription.objects.order_by('patient_ref').first()
            attachment=sim.api.upload(lab.accounts['RECEPTION'][0],lab.host,str(case.pk),'PHOTO',photo=True)
            financial[lab.schema]={'invoice':str(invoice['id']),'payment':str(payment['id']),
                                  'source':str(source),'attachment':str(attachment['id']),
                                  'attachment_case':str(case.pk),'balance':balance}
    for lab in sim.labs:
        with schema_context(lab.schema):
            schema_guard(lab.schema)
            proof.check(Prescription.objects.count()==len(lab.cases),'source count equals the simulator ledger plus controls')
            expected_cases=set(lab.cases)
            expected_tasks={str(pk) for pk in PlanningTask.objects.values_list('pk',flat=True)}
            expected_employees={employee.pk for employee in lab.employees}
            expected_finance={path:model.objects.count() for path,model in [
                ('periods',BillingPeriod),('invoices',FinanceInvoice),('payments',Payment)]}
            own=financial[lab.schema]
            for role in ['MANAGER','RECEPTION','CAO','FAO','QUALITE','COMPTABILITE','COURIER']:
                actor=lab.accounts[role][0]
                cases=sim.api.rows(actor,lab.host,'/api/prescriptions/',{'include_completed':'true','page_size':200})
                ids={row['id'] for row in cases}
                if role=='COURIER':
                    courier_ids={str(pk) for pk in Prescription.objects.filter(status__in=[
                        'ATTENTE_RAMASSAGE','EN_ROUTE_LABO','PRET_EXPEDITION','EN_ROUTE_CABINET']).values_list('pk',flat=True)}
                    proof.check(ids==courier_ids,'courier sees exactly its local handoffs')
                else:
                    proof.check(ids==expected_cases,role+' case list equals the local ledger')
                for path in ['/api/work-queue/','/api/planning/tasks/','/api/planning/workload/']:
                    response=sim.api.request(actor,lab.host,'get',path,expected=None)
                    if role=='COURIER':
                        proof.check(response.status_code==403,'courier restricted work/planning endpoint')
                        continue
                    proof.check(response.status_code==200,role+' work/planning allowed')
                    rows=sim.api.rows(actor,lab.host,path,{'page_size':200})
                    if 'work-queue' in path:
                        proof.check({row['id'] for row in rows}<=expected_cases,'work queue is tenant-local')
                    elif 'tasks' in path:
                        proof.check({row['id'] for row in rows}==expected_tasks,'planning tasks are tenant-local')
                        proof.check({str(row['prescription']) for row in rows}<=expected_cases,'task sources are tenant-local')
                    else:
                        proof.check({row['employee'] for row in rows}==expected_employees,'workload staff count matches approved staffing')
                        proof.check(all(row['name'].startswith('SIM-'+lab.profile.key) for row in rows),'workload names are tenant-local')
                for endpoint in ['periods','invoices','payments','receivables','statement-lines','credit-notes','disputes']:
                    path=f'/api/billing/{endpoint}/'
                    response=sim.api.request(actor,lab.host,'get',path,expected=None)
                    finance_role=role in {'MANAGER','COMPTABILITE'}
                    proof.check(response.status_code==(200 if finance_role else 403),role+' billing role matrix')
                    if not finance_role:
                        continue
                    rows=sim.api.rows(actor,lab.host,path,{'page_size':200})
                    if endpoint in expected_finance:
                        proof.check(len(rows)==expected_finance[endpoint],'finance count matches local source')
                    if endpoint=='invoices':
                        proof.check(all(('-'+lab.schema+'-') in row['number'] for row in rows),'invoice numbering embeds its own schema')
                    elif endpoint=='payments':
                        proof.check({row['id'] for row in rows}=={own['payment']},'payment belongs to this tenant')
                    elif endpoint=='receivables':
                        proof.check(sum(Decimal(row['total_due']) for row in rows)==own['balance'],'live receivables use the local payment')
                summary=sim.api.request(actor,lab.host,'get','/api/dashboard/summary/',expected=None)
                if role not in {'MANAGER','COMPTABILITE'}:
                    proof.check(summary.status_code==403,'dashboard restricted by role')
                else:
                    proof.check(summary.status_code==200,'dashboard available to finance roles')
                    data=summary.json()
                    proof.check(Decimal(data['finance']['total_receivables'])==own['balance'],'dashboard finance aggregate is tenant-local')
                    proof.check(('operations' in data)==(role=='MANAGER'),'accounting has no operations block')
                    if role=='MANAGER':
                        proof.check(data['operations']['active_cases']==Prescription.objects.exclude(status='CLOTURE').count(),
                                    'dashboard active count matches local source')
                document=f"/api/prescriptions/{own['attachment_case']}/attachment/{own['attachment']}/"
                response=sim.api.request(actor,lab.host,'get',document,expected=None)
                proof.check(response.status_code==(403 if role=='COURIER' else 200),'clinical document role and ownership')
                response.close()
                pdf=sim.api.request(actor,lab.host,'get',f"/api/billing/invoices/{own['invoice']}/pdf/",expected=None)
                proof.check(pdf.status_code==(200 if role in {'MANAGER','COMPTABILITE'} else 403),'invoice PDF role and ownership')
                if pdf.status_code==200:
                    content=b''.join(pdf.streaming_content)
                    proof.check(content.startswith(b'%PDF-'),'own stored invoice is a real PDF')
                pdf.close()
            proof.check(not MessageDelivery.objects.filter(status='SENT').exists(),'no external delivery was marked sent')
            # Existing product identifiers are UUID-derived, not a shared sequential counter.
            numbers=list(FinanceInvoice.objects.values_list('number',flat=True))
            proof.check(len(numbers)==len(set(numbers)),'local invoice numbers are unique')
    # Probe foreign IDs both through the wrong host and inside a valid local membership.
    for index,lab in enumerate(sim.labs):
        foreign=sim.labs[(index+1)%len(sim.labs)]
        target=financial[foreign.schema]
        with schema_context(foreign.schema):
            foreign_task=str(PlanningTask.objects.values_list('pk',flat=True).first())
        for role in ['MANAGER','RECEPTION','CAO','FAO','QUALITE','COMPTABILITE','COURIER']:
            actor=lab.accounts[role][0]
            sim.api.client(actor,lab.host)  # Mint any authorized session before the write snapshot.
            before=row_snapshot(sim.labs)
            attacks=[('get',foreign.host,'/api/prescriptions/',{}),
                ('get',lab.host,f"/api/prescriptions/{target['source']}/",{}),
                ('post',lab.host,f"/api/prescriptions/{target['source']}/command/",{'action':'planning-start','data':{'task':foreign_task}}),
                ('get',lab.host,f'/api/planning/tasks/{foreign_task}/',{}),
                ('get',lab.host,f"/api/billing/invoices/{target['invoice']}/",{}),
                ('get',lab.host,f"/api/billing/invoices/{target['invoice']}/pdf/",{}),
                ('get',lab.host,f"/api/billing/payments/{target['payment']}/",{}),
                ('post',lab.host,f"/api/billing/payments/{target['payment']}/reverse/",{'reason':'ANNULE'}),
                ('get',lab.host,f"/api/prescriptions/{target['attachment_case']}/attachment/{target['attachment']}/",{})]
            for method,host,path,data in attacks:
                response=sim.api.request(actor,host,method,path,data,expected=None)
                proof.attacks+=1
                proof.check(response.status_code in {403,404},'foreign ID/host request denied')
                response.close()
            proof.check(before==row_snapshot(sim.labs),'foreign attack group writes nothing in any tenant')
    # Both global dentist accounts have actual cases in at least two laboratories.
    for dentist in sim.labs[0].accounts['DENTIST']:
        expected={}
        for lab in sim.labs:
            with schema_context(lab.schema):
                expected.update({str(pk):lab.schema for pk in Prescription.objects.filter(dentist_account=dentist).values_list('pk',flat=True)})
        rows=sim.api.rows(dentist,'localhost','/platform/dentist/orders/')
        actual={row['id']:row['laboratory_id'] for row in rows}
        proof.check(actual==expected,'multi-lab dentist sees exactly their owned cases')
        proof.check(len(set(actual.values()))>=2,'dentist really works with at least two laboratories')
    return {'assertions':proof.assertions,'attack_attempts':proof.attacks,'leaks':0,'unauthorized_writes':0,
        'post_horizon_control_cases':controls,'method':'real bearer authentication and DRF middleware/routes in-process',
        'numbering_rule':'Case UUIDs and caller-supplied references; invoices INV-YYYYMM-schema-periodUUIDprefix. No sequential invoice counter.',
        'clock_limits':['QR signature age and Redis TTL use wall time; tenant generations are checked after interleaved writes.',
                        'Financial/PDF control fixtures are created after the workload measurement window.']}
