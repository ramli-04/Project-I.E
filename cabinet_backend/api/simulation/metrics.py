"""Transparent metrics over recorded execution, with censored cases kept visible."""
from datetime import timedelta
import math
from statistics import median
from django_tenants.utils import schema_context
from api.models import Prescription, ReworkCase
from api.planning_models import PlanningTask, PlanningSettings
from api.planning import employee_windows
from api.workflow_spec import STEPS


def distribution(values):
    values=sorted(values)
    return {'median':round(median(values),3) if values else None,
            'p90':round(values[max(0,math.ceil(.9*len(values))-1)],3) if values else None,
            'count':len(values)}


def overlap_minutes(a,b,start,end):
    return max(0,(min(b,end)-max(a,start)).total_seconds()/60)


def lab_metrics(lab, start, end, now):
    with schema_context(lab.schema):
        statuses={str(pk):status for pk,status in Prescription.objects.values_list('id','status')}
        tasks=list(PlanningTask.objects.all())
        settings=PlanningSettings.objects.get(pk=1)
        staffing=[]
        for employee in lab.employees:
            capacity=0
            day=start.date()
            while day<=end.date():
                capacity+=sum(overlap_minutes(a,b,start,end) for a,b in employee_windows(employee,day,settings))
                day+=timedelta(days=1)
            attended=0
            for task in tasks:
                if task.assigned_employee_id!=employee.pk:
                    continue
                attended+=task.worked_seconds/60
                if task.last_started_at:
                    attended+=overlap_minutes(task.last_started_at,now,start,end)
            staffing.append({'role':employee.role,'available_minutes':round(capacity,3),
                'attended_minutes':round(attended,3),'utilization_percent':round(attended/capacity*100,3) if capacity else None})
        by_role=[]
        for role in ['RECEPTION','CAO','FAO','QUALITE']:
            rows=[row for row in staffing if row['role']==role]
            capacity=sum(row['available_minutes'] for row in rows)
            actual=sum(row['attended_minutes'] for row in rows)
            by_role.append({'role':role,'staff':len(rows),'available_minutes':round(capacity,3),
                'attended_minutes':round(actual,3),'utilization_percent':round(actual/capacity*100,3) if capacity else None})
        machine_rows=[]
        for machine in lab.machines:
            occupied=sum(overlap_minutes(task.actual_start,task.actual_end or now,start,end)
                for task in tasks if task.machine_id==machine.pk and task.actual_start)
            machine_rows.append({'name':machine.name,'type':machine.machine_type,
                'calendar_minutes':round((end-start).total_seconds()/60,3),'occupied_minutes':round(occupied,3),
                'occupancy_percent':round(occupied/(end-start).total_seconds()*6000,3)})
        completed=[state for key,state in lab.cases.items() if state['last_delivery']
                   and statuses[key] in {'LIVRE','ESSAYAGE','CLOTURE'}]
        service_rows={}
        for service in ['STANDARD','EXPRESS','NEXT_DAY']:
            created=[state for state in lab.cases.values() if state['plan']['service']==service]
            delivered=[state for state in completed if state['plan']['service']==service]
            on_time=sum(state['last_delivery']<=state['delivered_deadline'] for state in delivered)
            service_rows[service]={'created':len(created),'delivered':len(delivered),'on_time':on_time,
                'on_time_percent':round(on_time/len(delivered)*100,3) if delivered else None}
        def hours(state):return (state['last_delivery']-state['plan']['at']).total_seconds()/3600
        normal=[hours(state) for state in completed if state['first_rework'] is None]
        remade=[hours(state) for state in completed if state['first_rework'] is not None]
        pending=[]
        for key,state in lab.cases.items():
            current=next((task for task in tasks if str(task.prescription_id)==key
                          and task.workflow_step==state['status'] and task.status not in {'COMPLETED','CANCELLED'}),None)
            if state['external'] or current and current.actual_start is None:
                pending.append((state['status'],max(0,(end-state['entered']).total_seconds()/60)))
        bottlenecks=waiting_summary(lab.waits,pending)
        return {'staffing':lab.profile.staffing,'cases_created':len(lab.cases),'cases_delivered':len(completed),
            'cases_delivered_at_least_once':sum(bool(state['first_delivery']) for state in lab.cases.values()),
            'cases_closed':sum(status=='CLOTURE' for status in statuses.values()),
            'unfinished_at_horizon':len(lab.cases)-len(completed),'services':service_rows,
            'lead_time_hours':distribution([hours(state) for state in completed]),'bottlenecks':bottlenecks,
            'staff_utilization':by_role,'machines':machine_rows,'machine_outage_events':lab.outages,
            'rework_count':ReworkCase.objects.count(),
            'deferred_starts':lab.deferred_starts,'start_diagnostics':lab.start_diagnostics,
            'rework_delay_hours':{'without_rework':distribution(normal),'with_rework':distribution(remade),
                'median_difference':round(median(remade)-median(normal),3) if normal and remade else None,
                'interpretation':'Observed cohort difference, not a causal estimate'},
            'executed_failures':{key:sum(key in state['used'] for state in lab.cases.values())
                for key in ['intake','model','design','quality','fitting']}}


def waiting_summary(started, pending):
    values={key:list(rows) for key,rows in started.items()}
    censored={}
    for key,minutes in pending:
        values.setdefault(key,[]).append(minutes)
        censored[key]=censored.get(key,0)+1
    rows=[{'step':key,'label':STEPS[key].label,'observations':len(times),
           'still_waiting':censored.get(key,0),'mean_wait_minutes':round(sum(times)/len(times),3),
           'total_wait_minutes':round(sum(times),3)} for key,times in values.items() if times]
    return sorted(rows,key=lambda row:(-row['mean_wait_minutes'],row['step']))[:3]
