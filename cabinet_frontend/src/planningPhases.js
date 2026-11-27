import { labISO } from './planningTime.js';

// Employee lanes show attended work. Machine/day views retain the entire job.
export function employeeReservations(task, firstDay, lastDay) {
  const phase = task.resource_phase;
  if (!phase || phase === 'MANUAL') return [task];
  const first = Date.parse(labISO(firstDay+'T00:00'));
  const last = Date.parse(labISO(lastDay+'T00:00'))-1;
  const start = Date.parse(task.planned_start);
  const end = Date.parse(task.planned_end);
  let intervals = [];
  if (phase === 'PLANNED') {
    intervals = [[start,start+task.setup_minutes*60000,'Chargement'],
      [end-task.unload_minutes*60000,end,'Déchargement']];
  } else if (['SETUP','UNLOADING'].includes(phase)) {
    intervals = [[Date.parse(task.phase_started_at||task.planned_start),last,
      phase==='SETUP'?'Chargement en cours':'Déchargement en cours']];
  }
  return intervals.filter(([a,b])=>a<last&&first<b).map(([a,b,label],index)=>({
    ...task, id:task.id+'-attended-'+index, original_task:task,
    title:label+' · '+task.title,
    planned_start:new Date(Math.max(a,first)).toISOString(),
    planned_end:new Date(Math.min(b,last)).toISOString(),
  }));
}
