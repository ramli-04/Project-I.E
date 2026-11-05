import { useEffect, useRef, useState } from 'react';
import api from './api/client';
import { allRows, errorText, retryableRequest } from './api/contracts';
import { Button, Feedback, Field, control } from './IntegrationUI';
import { configurePlanningTime, labDateTime, taskLabels } from './planningTime';

export default function PlanningProgress({ order, refresh }) {
  const [tasks,setTasks]=useState([]);const [events,setEvents]=useState([]);const [error,setError]=useState('');const [notice,setNotice]=useState('');
  const [notes,setNotes]=useState('');const [busy,setBusy]=useState(false);const [reload,setReload]=useState(0);const request=useRef(retryableRequest());
  useEffect(()=>{
    const abort=new AbortController();
    Promise.all([allRows(api,'planning/tasks/',{prescription:order.id,include_terminal:true},abort.signal),api.get('planning/settings/',{signal:abort.signal})]).then(([rows,config])=>{configurePlanningTime(config.data?.timezone);setTasks(rows);}).catch(e=>{if(!abort.signal.aborted)setError(errorText(e));});
    return()=>abort.abort();
  },[order.id,order.updated_at,reload]);
  async function command(task,action) {
    if(busy)return;setBusy(true);setError('');setNotice('');
    try { await request.current(api,`prescriptions/${order.id}/command/`,{action:'planning-'+action,data:{task:task.id,notes}});setNotice('Progression enregistrée.');setReload(v=>v+1);await refresh?.(); }
    catch(e){setError(errorText(e));}finally{setBusy(false);}
  }
  async function history(){try{setEvents(await allRows(api,'planning/events/',{prescription:order.id}));}catch(e){setError(errorText(e));}}
  return <section className="planning-progress"><div className="flex items-center justify-between gap-3"><h3 className="font-semibold">Progression de fabrication</h3><Button disabled={busy} onClick={()=>setReload(v=>v+1)}>Actualiser</Button></div><Feedback error={error} notice={notice}/>
    {!tasks.length && <p className="text-sm text-slate-500">Aucune tâche disponible. Les tâches sont générées après acceptation ; les dossiers antérieurs peuvent être repris depuis Planning.</p>}
    <ol className="planning-step-list">{[...tasks].sort((a,b)=>a.production_attempt-b.production_attempt||a.sequence-b.sequence||a.generation-b.generation).map(task=><li key={task.id} className={`planning-step task-${task.status.toLowerCase()}`}><div className="planning-step-dot"/><div className="flex flex-wrap justify-between gap-3"><div><strong>{task.title}</strong><p>{task.employee_name||'Responsable à affecter'} · tentative {task.production_attempt} · {task.estimated_duration_minutes} min</p></div><span className={`planning-badge status-${task.status.toLowerCase()}`}>{taskLabels[task.status]}</span></div><p className="planning-times">Prévu : {labDateTime(task.planned_start)} → {labDateTime(task.planned_end)}<br/>Réel : {labDateTime(task.actual_start)} → {labDateTime(task.actual_end)}</p>{task.blocking_reason&&<p className="text-sm text-amber-800">{task.blocking_reason}</p>}
      {task.source_status===task.workflow_step&&task.can_operate&&!task.external&&!['COMPLETED','CANCELLED'].includes(task.status)&&<div className="mt-3 flex flex-wrap gap-2">{['READY','SCHEDULED'].includes(task.status)&&<Button disabled={busy} onClick={()=>command(task,'start')}>Démarrer</Button>}{task.status==='IN_PROGRESS'&&<><Button disabled={busy} onClick={()=>command(task,'complete')}>Terminer l’étape</Button><Button disabled={busy||!notes.trim()} onClick={()=>command(task,'pause')}>Mettre en pause</Button></>}{['PAUSED','BLOCKED'].includes(task.status)&&<Button disabled={busy} onClick={()=>command(task,'resume')}>Reprendre</Button>}<Button disabled={busy||!notes.trim()} onClick={()=>command(task,'block')}>Signaler un problème</Button></div>}
      {task.external&&task.source_status===task.workflow_step&&<p className="mt-2 text-xs text-slate-500">Utilisez les contrôles du dossier pour la validation de design, la réception ou la remise QR/PIN.</p>}
    </li>)}</ol>
    <Field label="Commentaire de progression / motif du blocage"><textarea className={control} value={notes} onChange={e=>setNotes(e.target.value)} maxLength={2000}/></Field>
    <details onToggle={e=>{if(e.currentTarget.open)void history();}}><summary className="cursor-pointer text-sm text-teal-700">Historique du planning</summary><ul className="mt-3 space-y-2 text-xs text-slate-500">{events.map(event=><li key={event.id}>{labDateTime(event.created_at)} · {event.kind} · {event.actor} · {event.notes}</li>)}</ul></details>
  </section>;
}
