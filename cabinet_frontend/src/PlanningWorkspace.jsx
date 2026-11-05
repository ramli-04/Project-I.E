import { useEffect, useRef, useState } from 'react';
import { CalendarDays, ChartGantt, Users, Settings2, RefreshCw, ChevronLeft, ChevronRight, X, LockKeyhole } from 'lucide-react';
import api from './api/client';
import { allRows, errorText, retryableRequest, rowsOf, workstation } from './api/contracts';
import { previewMode } from './api/preview';
import { Button, control, Feedback, Field } from './IntegrationUI';
import PlanningProgress from './PlanningProgress';
import PlanningResources from './PlanningResources';
import { addDays, addMonths, configurePlanningTime, labDate, labDateTime, labInput, labISO, labTime, taskLabels } from './planningTime';

const roleLabels = { RECEPTION:'Réception',CAO:'CAO',FAO:'FAO / finition',QUALITE:'Qualité',EXTERNAL:'Validation externe' };
const modes = [['calendar','Calendrier',CalendarDays],['gantt','Gantt',ChartGantt],['workload','Charge',Users],['resources','Paramètres et équipe',Settings2],['events','Historique',RefreshCw]];

export default function PlanningWorkspace({ orders, refreshOrders }) {
  const [view,setView]=useState('calendar');const [scale,setScale]=useState('week');const [day,setDay]=useState(()=>labDate(new Date()));
  const [filters,setFilters]=useState({employee:'',role:'',status:'',priority:'',prescription:'',workstation:''});
  const [page,setPage]=useState(1);const [tasks,setTasks]=useState([]);const [employees,setEmployees]=useState([]);const [machines,setMachines]=useState([]);
  const [settings,setSettings]=useState(null);const [workload,setWorkload]=useState({results:[],risks:[]});const [events,setEvents]=useState([]);const [count,setCount]=useState(0);
  const [selected,setSelected]=useState(null);const [error,setError]=useState('');const [notice,setNotice]=useState('');const [busy,setBusy]=useState(false);const [loading,setLoading]=useState(true);const [revision,setRevision]=useState(0);
  const request=useRef(retryableRequest());const manager=workstation()==='MANAGER';
  const start=scale==='month'?day.slice(0,7)+'-01':day;
  const end=scale==='month'?addMonths(start,1):addDays(day,scale==='day'||scale==='employee'?1:7);
  useEffect(()=>{
    const abort=new AbortController(); const signal=abort.signal;
    const params={start,end,page,page_size:50,...Object.fromEntries(Object.entries(filters).filter(([,v])=>v))};
    Promise.all([api.get(view==='calendar'?'planning/calendar/':'planning/tasks/',{params,signal}),api.get('planning/workload/',{params:{start,end,page,page_size:50},signal}),view==='events'?api.get('planning/events/',{params:{page},signal}):Promise.resolve({data:[]})]).then(([taskResponse,loadResponse,eventResponse])=>{
      if(signal.aborted)return;
      const rows=rowsOf(taskResponse.data);setTasks(rows);setCount(view==='events'?(eventResponse.data.count||0):(view==='workload'?(loadResponse.data.count??rowsOf(loadResponse.data).length):(taskResponse.data.count??rows.length)));
      setWorkload(Array.isArray(loadResponse.data)?{results:loadResponse.data,risks:[]}:loadResponse.data);setEvents(rowsOf(eventResponse.data));
      setSelected(old=>old?rows.find(t=>t.id===old.id)||old:null);setError('');
    }).catch(e=>{if(!signal.aborted)setError(errorText(e));}).finally(()=>{if(!signal.aborted)setLoading(false);});
    return()=>abort.abort();
  },[start,end,page,filters,view,revision]);
  useEffect(()=>{
    const abort=new AbortController();
    Promise.all([allRows(api,'employee-profiles/',{},abort.signal),allRows(api,'machines/',{},abort.signal),api.get('planning/settings/',{signal:abort.signal})])
      .then(([staff,equipment,config])=>{configurePlanningTime(config.data?.timezone);setEmployees(staff);setMachines(equipment);setSettings(Array.isArray(config.data)?null:config.data);}).catch(e=>{if(!abort.signal.aborted)setError(errorText(e));});
    return()=>abort.abort();
  },[revision]);
  useEffect(()=>{if(previewMode)return;const timer=setInterval(()=>setRevision(v=>v+1),15000);return()=>clearInterval(timer);},[]);
  function filter(key,value){setFilters({...filters,[key]:value});setPage(1);}
  async function recalculate(){if(busy)return;setBusy(true);setError('');try{await request.current(api,'planning/recalculate/',{});setNotice('Replanification demandée. Les traitements Celery mettront le planning à jour ; vous pouvez actualiser le suivi.');setRevision(v=>v+1);}catch(e){setError(errorText(e));}finally{setBusy(false);}}
  return <div className="planning-workspace space-y-5"><div className="planning-title"><div><span className="section-kicker">ORDONNANCEMENT DU LABORATOIRE</span><h1>Planning de fabrication</h1><p>Des tâches issues de vos commandes, des affectations selon les compétences et la capacité réelle.</p></div><div className="flex flex-wrap gap-2"><Button onClick={()=>{setLoading(true);setRevision(v=>v+1);}}>Actualiser</Button>{manager&&<Button disabled={busy} onClick={recalculate}><RefreshCw size={14} className="inline mr-2"/>Replanifier</Button>}</div></div>
    <Feedback error={error} notice={notice}/>{previewMode&&<p className="planning-info">Aperçu sans base : aucune affectation réelle n’est calculée. Le module utilise PostgreSQL et les workers en mode connecté.</p>}
    <div className="planning-modes">{modes.filter(([key])=>manager||key!=='resources').map(([key,label,Icon])=><button key={key} aria-pressed={view===key} className={view===key?'active':''} onClick={()=>{setView(key);setPage(1);}}><Icon size={16}/>{label}</button>)}</div>
    {view==='resources'?<PlanningResources key={settings?'configured':'loading'} settings={settings} employees={employees} onSaved={()=>setRevision(v=>v+1)}/>:<>
      <div className="planning-toolbar"><div className="flex items-center gap-2"><button aria-label="Période précédente" onClick={()=>{setDay(scale==='month'?addMonths(day,-1):addDays(day,scale==='week'?-7:-1));setPage(1);}}><ChevronLeft size={18}/></button><input className={control} aria-label="Date du planning" type="date" value={day} onChange={e=>{setDay(e.target.value);setPage(1);}}/><button aria-label="Période suivante" onClick={()=>{setDay(scale==='month'?addMonths(day,1):addDays(day,scale==='week'?7:1));setPage(1);}}><ChevronRight size={18}/></button></div><select aria-label="Vue du calendrier" className={control} value={scale} onChange={e=>{setScale(e.target.value);setPage(1);}}><option value="day">Journée</option><option value="week">Semaine</option><option value="month">Mois</option><option value="employee">Par employé</option><option value="order">Par commande</option></select><span className="text-xs text-slate-500">Africa/Casablanca · actualisation 15 s</span></div>
      <div className="planning-filters">{[['employee','Employé',employees.map(e=>[String(e.id),e.name||`Collaborateur #${e.id}`])],['role','Rôle',Object.entries(roleLabels)],['workstation','Poste',Object.entries(roleLabels)],['status','Statut',Object.entries(taskLabels)],['priority','Priorité',[['1','Standard J+4'],['2','Express J+2'],['3','Critique J+1']]],['prescription','Commande',orders.map(o=>[o.id,o.patient_ref])]].map(([key,label,options])=><Field key={key} label={label}><select className={control} value={filters[key]} onChange={e=>filter(key,e.target.value)}><option value="">Tous</option>{options.map(([value,text])=><option key={value} value={value}>{text}</option>)}</select></Field>)}</div>
      {workload.risks?.some(r=>r.risk!=='ON_TRACK')&&<div className="planning-risk-list" role="status">{workload.risks.filter(r=>r.risk!=='ON_TRACK').slice(0,8).map(r=><p key={r.prescription}><strong>{r.patient_ref}</strong> · {r.risk==='LATE'?'Retard prévisible':'Échéance à risque'} · {r.unscheduled} tâche(s) sans créneau · échéance {labDateTime(r.deadline)}</p>)}</div>}
      {loading&&<p role="status" className="text-sm text-slate-500">Chargement du planning…</p>}
      {view==='calendar'&&<Calendar settings={settings} tasks={tasks} employees={employees} scale={scale} start={start} end={end} onSelect={setSelected}/>}
      {view==='gantt'&&<Gantt tasks={tasks} start={start} end={end} onSelect={setSelected}/>}
      {view==='workload'&&<Workload data={workload}/>}
      {view==='events'&&<section className="planning-surface"><h2>Événements du planning</h2>{events.map(e=><div key={e.id} className="planning-event"><span>{labDateTime(e.created_at)}</span><strong>{e.kind}</strong><span>{e.actor}</span><p>{e.notes}</p></div>)}{!events.length&&<p>Aucun événement disponible.</p>}</section>}
      {['calendar','gantt'].includes(view)&&<section className="planning-unscheduled"><h2>Tâches sans créneau</h2>{tasks.filter(t=>!t.planned_start&&!['COMPLETED','CANCELLED'].includes(t.status)).map(t=><button key={t.id} onClick={()=>setSelected(t)}><span>{t.patient_ref} · {t.title}</span><small>{t.blocking_reason||'En attente de planification'}</small></button>)}{!tasks.some(t=>!t.planned_start)&&<p className="text-sm text-slate-500">Aucune tâche sans créneau dans cette sélection.</p>}</section>}
      {<div className="flex justify-center items-center gap-4"><Button disabled={page===1} onClick={()=>setPage(page-1)}>Page précédente</Button><span className="text-sm text-slate-500">Page {page} · {count} résultat(s)</span><Button disabled={page*50>=count} onClick={()=>setPage(page+1)}>Page suivante</Button></div>}
      <div className="planning-legend">{['SCHEDULED','READY','IN_PROGRESS','COMPLETED','BLOCKED','PAUSED'].map(s=><span key={s}><i className={`status-${s.toLowerCase()}`}/>{taskLabels[s]}</span>)}<span><i className="status-late"/>Retard</span></div>
      {workload.last_recalculated_at&&<p className="text-xs text-slate-500">Dernier calcul : {labDateTime(workload.last_recalculated_at)} · révision {workload.applied_revision}/{workload.revision}</p>}
    </>}
    {selected&&<TaskDrawer key={selected.id} task={selected} employees={employees} machines={machines} manager={manager} order={orders.find(o=>o.id===selected.prescription)||{id:selected.prescription}} onClose={()=>setSelected(null)} onSaved={async()=>{setRevision(v=>v+1);await refreshOrders?.();}}/>}
  </div>;
}

function Calendar({tasks,employees,scale,start,end,onSelect,settings}) {
  const scheduled=tasks.filter(t=>t.planned_start&&t.planned_end);
  const hoursOf=value=>{const v=labInput(value);return Number(v.slice(11,13))+Number(v.slice(14,16))/60;};
  const firstHour=Math.min(Number((settings?.open_time||'08:00').slice(0,2)),...scheduled.map(t=>Math.floor(hoursOf(t.planned_start))));
  const lastHour=Math.max(Number((settings?.close_time||'18:00').slice(0,2))+1,...scheduled.map(t=>Math.ceil(hoursOf(t.planned_end))));
  const minutesRange=(lastHour-firstHour)*60;
  const days=[];for(let d=start;d<end;d=addDays(d,1))days.push(d);
  if(scale==='month')return <section className="planning-month">{days.map(d=><div key={d}><h3>{new Date(d+'T12:00:00Z').toLocaleDateString('fr-FR',{day:'numeric',month:'short'})}</h3>{scheduled.filter(t=>labDate(t.planned_start)===d).map(t=><button key={t.id} className={`planning-month-task status-${t.late?'late':t.status.toLowerCase()}`} onClick={()=>onSelect(t)}>{labTime(t.planned_start)} · {t.patient_ref}<small>{t.title}</small></button>)}</div>)}</section>;
  if(scale==='order')return <section className="planning-surface">{[...new Set(tasks.map(t=>t.prescription))].map(id=><div className="planning-order-group" key={id}><h3>{tasks.find(t=>t.prescription===id)?.patient_ref}</h3>{tasks.filter(t=>t.prescription===id).map(t=><button className={`planning-order-task status-${t.status.toLowerCase()}`} key={t.id} onClick={()=>onSelect(t)}>{t.title}<small>{t.employee_name||'À affecter'} · {labDateTime(t.planned_start)}</small></button>)}</div>)}{!tasks.length&&<p>Aucune tâche disponible.</p>}</section>;
  const lanes=scale==='employee'?employees.map(e=>({key:String(e.id),title:e.name||`Collaborateur #${e.id}`})):days.map(d=>({key:d,title:new Date(d+'T12:00:00Z').toLocaleDateString('fr-FR',{weekday:'short',day:'numeric',month:'short'})}));
  return <div className="planning-calendar-scroll"><div className="planning-calendar" style={{'--lanes':Math.max(lanes.length,1),'--calendar-height':`${(lastHour-firstHour)*45}px`}}><div className="planning-hours"><div/>{Array.from({length:lastHour-firstHour+1},(_,i)=><span key={i}>{String(i+firstHour).padStart(2,'0')}:00</span>)}</div>{lanes.map(lane=>{
    const laneTasks=scheduled.filter(t=>scale==='employee'?String(t.assigned_employee)===lane.key&&labDate(t.planned_start)===start:labDate(t.planned_start)===lane.key);
    const tracks=[];const positions=new Map();
    for(const t of [...laneTasks].sort((a,b)=>Date.parse(a.planned_start)-Date.parse(b.planned_start))){let track=tracks.findIndex(end=>end<=Date.parse(t.planned_start));if(track<0){track=tracks.length;tracks.push(0);}tracks[track]=Date.parse(t.planned_end);positions.set(t.id,track);}
    return <div className="planning-day" key={lane.key}><h3>{lane.title}</h3><div className="planning-day-grid">{laneTasks.map(t=>{const input=labInput(t.planned_start);const minutes=Number(input.slice(11,13))*60+Number(input.slice(14,16));const duration=(Date.parse(t.planned_end)-Date.parse(t.planned_start))/60000;return <button key={t.id} className={`planning-time-block status-${t.late?'late':t.status.toLowerCase()}`} style={{top:`${(minutes-firstHour*60)/minutesRange*100}%`,height:`${Math.max(duration/minutesRange*100,4)}%`,left:`${positions.get(t.id)/Math.max(tracks.length,1)*100}%`,width:`${100/Math.max(tracks.length,1)}%`}} onClick={()=>onSelect(t)} title={`${t.patient_ref} · ${t.title} · ${t.employee_name}`}><strong>{t.patient_ref} {t.locked?'🔒':''}</strong><span>{t.title}</span><small>{labTime(t.planned_start)} · {t.employee_name}</small></button>;})}</div></div>;
  })}</div>{!scheduled.length&&<p className="planning-empty">Aucune tâche avec un créneau dans cette période. Consultez les tâches sans créneau ci-dessous.</p>}</div>;
}

function Gantt({tasks,start,end,onSelect}) {
  const [now,setNow]=useState(()=>new Date().toISOString());
  useEffect(()=>{const timer=setInterval(()=>setNow(new Date().toISOString()),15000);return()=>clearInterval(timer);},[]);
  const first=Date.parse(labISO(start+'T00:00'));
  const last=Date.parse(labISO(end+'T00:00'));
  const x=value=>Math.max(0,Math.min(100,(Date.parse(value)-first)/(last-first)*100));
  const ordered=[...tasks].sort((a,b)=>String(a.prescription).localeCompare(String(b.prescription))||a.sequence-b.sequence||a.generation-b.generation);
  const lookup=new Map(ordered.map((task,index)=>[task.id,{task,index}]));
  return <section className="planning-gantt planning-surface">
    <div className="planning-gantt-header"><span>Commande / étape</span><span>{start} → {end} · couleur : prévu, trait sombre : réel</span></div>
    {ordered.map((t,index)=><div className="planning-gantt-row" key={t.id} style={{height:76}}>
      <div><strong>{t.patient_ref}</strong><small>{t.title} · {t.employee_name||'À affecter'}</small></div>
      <div className="planning-gantt-track">
        {t.planned_start&&t.planned_end&&<button aria-label={`${t.patient_ref} : ${t.title}`} className={`planning-gantt-bar status-${t.late?'late':t.status.toLowerCase()}`} style={{left:`${x(t.planned_start)}%`,width:`${Math.max(1,x(t.planned_end)-x(t.planned_start))}%`}} onClick={()=>onSelect(t)} title={`Prévu : ${labDateTime(t.planned_start)} → ${labDateTime(t.planned_end)}`}/>}
        {t.actual_start&&<div className="planning-gantt-actual" style={{left:`${x(t.actual_start)}%`,width:`${Math.max(.5,x(t.actual_end||now)-x(t.actual_start))}%`}} title={`Réel : ${labDateTime(t.actual_start)} → ${labDateTime(t.actual_end)}`}/>}
        {t.planned_start&&<svg aria-hidden="true" className="planning-gantt-links" viewBox="0 0 1000 76" preserveAspectRatio="none">{(t.dependencies||[]).map(id=>{
          const previous=lookup.get(id);if(!previous?.task.planned_end)return null;
          const from=x(previous.task.planned_end)*10;const to=x(t.planned_start)*10;const y=(previous.index-index)*76+21;
          return <g key={id}><path d={`M ${from} ${y} H ${Math.max(from,to-8)} V 21 H ${to}`} /><path d={`M ${to-5} 17 L ${to} 21 L ${to-5} 25`}/></g>;
        })}</svg>}
        <div className="planning-gantt-dependency">{(t.dependencies||[]).map(id=>{const dep=lookup.get(id)?.task;return dep?<button key={id} onClick={()=>onSelect(dep)} title="Ouvrir la tâche préalable">↳ {dep.title}</button>:<span key={id}>Prérequis hors de cette page</span>;})}</div>
      </div>
    </div>)}
    {!tasks.length&&<p>Aucune tâche dans cette période.</p>}
  </section>;
}

function Workload({data}) {return <section className="planning-surface"><h2>Charge de travail par collaborateur</h2><div className="overflow-x-auto"><table className="planning-workload-table"><thead><tr>{['Employé','Rôle','Charge','Temps planifié','Disponibilité'].map(h=><th key={h}>{h}</th>)}</tr></thead><tbody>{(data.results||[]).map(e=><tr key={e.employee}><td>{e.name}</td><td>{roleLabels[e.role]||e.role}</td><td><div className="planning-load"><i style={{width:`${Math.min(e.utilization||0,100)}%`}}/></div>{e.utilization==null?'Sans capacité':`${e.utilization} %`}</td><td>{e.planned_minutes} / {e.available_minutes} min</td><td>{e.available?(e.utilization>=100?'Saturé':'Disponible'):'Indisponible'}{e.conflicts?' · Conflit à résoudre':''}</td></tr>)}</tbody></table></div>{!data.results?.length&&<p className="text-sm text-slate-500">Aucun collaborateur configuré pour cette période.</p>}</section>;}

function TaskDrawer({task,employees,machines,manager,order,onClose,onSaved}) {
  const [employee,setEmployee]=useState(String(task.assigned_employee||''));const [start,setStart]=useState(labInput(task.planned_start));const [end,setEnd]=useState(labInput(task.planned_end));const [duration,setDuration]=useState(task.estimated_duration_minutes);const [machine,setMachine]=useState(String(task.machine||''));const [slot,setSlot]=useState(task.machine_slot||1);
  const [notes,setNotes]=useState('');const [busy,setBusy]=useState(false);const [error,setError]=useState('');const request=useRef(retryableRequest());
  useEffect(()=>{
    const previous=document.activeElement;const dialog=document.querySelector('.planning-task-drawer');
    dialog?.querySelector('button')?.focus();
    const handle=e=>{if(e.key==='Escape')onClose();if(e.key==='Tab'){const nodes=[...dialog.querySelectorAll('button:not(:disabled),input:not(:disabled),select:not(:disabled),summary')];const first=nodes[0],last=nodes.at(-1);if(e.shiftKey&&document.activeElement===first){e.preventDefault();last?.focus();}else if(!e.shiftKey&&document.activeElement===last){e.preventDefault();first?.focus();}}};
    document.addEventListener('keydown',handle);return()=>{document.removeEventListener('keydown',handle);previous?.focus();};
  },[onClose]);
  async function assign(event){event.preventDefault();setBusy(true);setError('');try{await request.current(api,`planning/tasks/${task.id}/assign/`,{employee:Number(employee),start:labISO(start),end:labISO(end),duration:Number(duration),machine:machine?Number(machine):null,machine_slot:Number(slot),notes});await onSaved();}catch(e){setError(errorText(e));}finally{setBusy(false);}}
  async function lock(){setBusy(true);setError('');try{await request.current(api,`planning/tasks/${task.id}/lock/`,{locked:!task.locked,notes});await onSaved();onClose();}catch(e){setError(errorText(e));}finally{setBusy(false);}}
  return <div className="planning-modal-backdrop" onClick={e=>{if(e.target===e.currentTarget)onClose();}}><section className="planning-task-drawer" role="dialog" aria-modal="true" aria-label={`Tâche ${task.patient_ref}`}><div className="flex justify-between items-start gap-4"><div><span className="section-kicker">{task.patient_ref}</span><h2>{task.title}</h2><p>{taskLabels[task.status]} · {task.employee_name||'Non affectée'}</p></div><button aria-label="Fermer la tâche" onClick={onClose}><X size={20}/></button></div><Feedback error={error}/><p className="text-sm text-amber-800">{task.blocking_reason}</p><p className="text-xs text-slate-500">Échéance : {labDateTime(task.deadline)} · Prévu : {labDateTime(task.planned_start)} → {labDateTime(task.planned_end)}</p>
    {manager&&!['IN_PROGRESS','PAUSED','COMPLETED','CANCELLED'].includes(task.status)&&<form onSubmit={assign}><fieldset disabled={busy} className="grid gap-4 sm:grid-cols-2"><Field label="Collaborateur affecté"><select className={control} required value={employee} onChange={e=>setEmployee(e.target.value)}><option value="">Choisir</option>{employees.map(e=><option key={e.id} value={e.id}>{e.name||e.id} · {e.role}</option>)}</select></Field><Field label="Durée estimée (minutes)"><input className={control} type="number" min="1" max="1440" required value={duration} onChange={e=>setDuration(e.target.value)}/></Field><Field label="Début · Africa/Casablanca"><input className={control} type="datetime-local" required value={start} onChange={e=>setStart(e.target.value)}/></Field><Field label="Fin · Africa/Casablanca"><input className={control} type="datetime-local" required value={end} onChange={e=>setEnd(e.target.value)}/></Field><Field label="Équipement"><select className={control} value={machine} onChange={e=>setMachine(e.target.value)}><option value="">Sans équipement</option>{machines.map(m=><option key={m.id} value={m.id}>{m.name} · {m.status}</option>)}</select></Field><Field label="Numéro de capacité de l’équipement"><input className={control} type="number" min="1" value={slot} onChange={e=>setSlot(e.target.value)}/></Field><Field label="Motif de supervision"><input className={control} value={notes} onChange={e=>setNotes(e.target.value)}/></Field><div className="flex flex-wrap gap-2 items-end"><Button type="submit">Affecter et verrouiller</Button><Button disabled={!task.planned_start} onClick={lock}><LockKeyhole size={13} className="inline mr-2"/>{task.locked?'Déverrouiller':'Verrouiller'}</Button></div></fieldset></form>}
    <details><summary className="cursor-pointer text-sm text-teal-700">Explication de l’affectation</summary><p className="mt-2 text-xs text-slate-500">{task.assignment_explanation?.reason||task.assignment_explanation?.policy||'Affectation manuelle ou en attente.'}</p>{task.assignment_explanation?.components&&<ul className="mt-2 text-xs text-slate-500">{Object.entries(task.assignment_explanation.components).map(([key,value])=><li key={key}>{({qualification:'Qualification',availability:'Disponibilité',workload:'Charge',urgency:'Urgence',continuity:'Continuité'})[key]} : {Math.round(value*100)} %</li>)}</ul>}</details>
    <PlanningProgress order={order} refresh={onSaved}/></section></div>;
}
