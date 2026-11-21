import { useEffect, useRef, useState } from 'react';
import api from './api/client';
import { frenchMessage } from './api/messages';
import { allRows, errorText, retryableRequest } from './api/contracts';
import { Button, Feedback } from './IntegrationUI';
import { configurePlanningTime, labDateTime, taskLabels } from './planningTime';
import ReasonNote from './ReasonNote';
import { progressNotePresets } from './technicianNotes';

const phaseLabels = { PLANNED:'Chargement → cycle autonome → déchargement', SETUP:'Chargement / réglage · technicien occupé', CYCLE:'Cycle autonome · technicien libéré', AWAITING_UNLOAD:'Cycle terminé · machine occupée jusqu’au déchargement', UNLOADING:'Déchargement · technicien occupé', FINISHED:'Déchargement confirmé' };

function EquipmentControls({task,busy,notes,command}) {
  const phase = task.resource_phase;
  if (!phase || phase === 'MANUAL') return null;
  return <div className="mt-3 space-y-2"><p className="text-sm font-semibold">{phaseLabels[phase]}</p><p className="text-xs text-slate-500">Estimations : chargement {task.setup_minutes} min · cycle {task.estimated_duration_minutes-task.setup_minutes-task.unload_minutes} min · déchargement {task.unload_minutes} min. Une fin de cycle ne valide jamais la qualité clinique.</p>
    {task.can_operate&&task.source_status===task.workflow_step&&task.status==='IN_PROGRESS'&&<div className="flex flex-wrap gap-2">
      {phase==='SETUP'&&<Button disabled={busy} onClick={()=>command(task,'launch-cycle')}>Chargement terminé : lancer le cycle</Button>}
      {phase==='CYCLE'&&<Button disabled={busy||!notes.trim()} onClick={()=>command(task,'cycle-finished')}>Confirmer la fin réelle du cycle</Button>}
      {phase==='AWAITING_UNLOAD'&&<Button disabled={busy} onClick={()=>command(task,'begin-unload')}>Commencer le déchargement</Button>}
      {phase==='UNLOADING'&&<Button disabled={busy} onClick={()=>command(task,'complete')}>Confirmer le déchargement et terminer</Button>}
    </div>}
  </div>;
}

export default function PlanningProgress({ order, refresh }) {
  const [tasks,setTasks]=useState([]);const [events,setEvents]=useState([]);const [error,setError]=useState('');const [notice,setNotice]=useState('');
  const [showAll,setShowAll]=useState(false);
  const [notes,setNotes]=useState('');const [busy,setBusy]=useState(false);const [reload,setReload]=useState(0);const request=useRef(retryableRequest());
  useEffect(()=>{
    const abort=new AbortController();
    Promise.all([allRows(api,'planning/tasks/',{prescription:order.id,include_terminal:true},abort.signal),api.get('planning/settings/',{signal:abort.signal})]).then(([rows,config])=>{configurePlanningTime(config.data?.timezone);setTasks(rows);setError('');}).catch(e=>{if(!abort.signal.aborted)setError(errorText(e));});
    const timer=setInterval(()=>setReload(v=>v+1),10000);
    return()=>{abort.abort();clearInterval(timer);};
  },[order.id,order.updated_at,reload]);
  async function command(task,action,extra={}) {
    if(busy)return;setBusy(true);setError('');setNotice('');
    try { await request.current(api,`prescriptions/${order.id}/command/`,{action:'planning-'+action,data:{task:task.id,notes,...extra}});setNotes('');setNotice('Progression enregistrée.');setReload(v=>v+1);await refresh?.(); }
    catch(e){setError(errorText(e));}finally{setBusy(false);}
  }
  async function history(){try{setEvents(await allRows(api,'planning/events/',{prescription:order.id}));}catch(e){setError(errorText(e));}}
  const ordered = [...tasks].sort((a,b)=>a.production_attempt-b.production_attempt||a.sequence-b.sequence||a.generation-b.generation);
  const visible = showAll ? ordered : ordered.filter(task=>task.source_status===task.workflow_step);
  const currentTask = [...ordered].reverse().find(task=>task.source_status===task.workflow_step&&!['COMPLETED','CANCELLED'].includes(task.status));
  return <section className="planning-progress"><div className="flex items-center justify-between gap-3"><h3 className="font-semibold">Progression de fabrication</h3><Button disabled={busy} onClick={()=>{setError('');setNotice('');setReload(v=>v+1);}}>Actualiser</Button></div><Feedback error={error} notice={notice}/>
    {!tasks.length && <p className="text-sm text-slate-500">Aucune tâche disponible. Les tâches sont générées après acceptation ; les dossiers antérieurs peuvent être repris depuis Planning.</p>}
    <ReasonNote label="Commentaire de progression / motif du blocage" value={notes} onChange={setNotes} presets={progressNotePresets(currentTask)} disabled={busy}/>
    <Button aria-expanded={showAll} onClick={()=>setShowAll(value=>!value)}>{showAll?'Afficher uniquement l’étape actuelle':'Afficher tout le parcours'}</Button>
    <ol className="planning-step-list">{visible.map(task=><li key={task.id} className={`planning-step task-${task.status.toLowerCase()}`}><div className="planning-step-dot"/><div className="flex flex-wrap justify-between gap-3"><div><strong>{task.title}</strong><p>{task.employee_name||'Responsable à affecter'} · tentative {task.production_attempt} · {task.estimated_duration_minutes} min</p></div><span className={`planning-badge status-${task.status.toLowerCase()}`}>{taskLabels[task.status]}</span></div><p className="planning-times">Prévu : {labDateTime(task.planned_start)} → {labDateTime(task.planned_end)}<br/>Réel : {labDateTime(task.actual_start)} → {labDateTime(task.actual_end)}</p>{task.blocking_reason&&<p className="text-sm text-amber-800">{frenchMessage(task.blocking_reason)}</p>}
      <EquipmentControls task={task} busy={busy} notes={notes} command={command}/>
      {task.can_start_now&&task.source_status===task.workflow_step&&!task.external&&['READY','SCHEDULED'].includes(task.status)&&task.planned_start&&<Button disabled={busy||!notes.trim()} onClick={()=>command(task,'start',{start_now:true})}>Démarrer maintenant et replanifier</Button>}
      {task.source_status===task.workflow_step&&task.can_operate&&!task.external&&!['COMPLETED','CANCELLED'].includes(task.status)&&<div className="mt-3 flex flex-wrap gap-2">{['READY','SCHEDULED'].includes(task.status)&&<Button disabled={busy} onClick={()=>command(task,'start')}>Démarrer</Button>}{task.status==='IN_PROGRESS'&&<>{(!task.resource_phase||task.resource_phase==='MANUAL')&&<Button disabled={busy} onClick={()=>command(task,'complete')}>Terminer l’étape</Button>}<Button disabled={busy||!notes.trim()} onClick={()=>command(task,'pause')}>Mettre en pause</Button></>}{['PAUSED','BLOCKED'].includes(task.status)&&<Button disabled={busy} onClick={()=>command(task,'resume')}>Reprendre</Button>}<Button disabled={busy||!notes.trim()} onClick={()=>command(task,'block')}>Signaler un problème</Button></div>}
      {task.external&&task.source_status===task.workflow_step&&<p className="mt-2 text-xs text-slate-500">Utilisez les contrôles du dossier pour la validation de design, la réception ou la remise QR/PIN.</p>}
    </li>)}</ol>
    <details onToggle={e=>{if(e.currentTarget.open)void history();}}><summary className="cursor-pointer text-sm text-teal-700">Historique du planning</summary><ul className="mt-3 space-y-2 text-xs text-slate-500">{events.map(event=><li key={event.id}>{labDateTime(event.created_at)} · {event.kind} · {event.actor} · {event.notes}</li>)}</ul></details>
  </section>;
}
