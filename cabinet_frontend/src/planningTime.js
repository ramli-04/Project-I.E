const zone = 'Africa/Casablanca';
let serverZone=null;
export function configurePlanningTime(value) { serverZone=value?.zone===zone&&value.transitions?.length?value:null; }
function display(value) {
  const instant=new Date(value).getTime();
  if(serverZone&&instant<Date.parse(serverZone.until)) {
    const transition=serverZone.transitions.findLast(t=>Date.parse(t.at)<=instant);
    if(transition)return {value:new Date(instant+transition.offset*60000),timeZone:'UTC'};
  }
  return {value:new Date(value),timeZone:zone};
}
const parts = value => {const d=display(value);return Object.fromEntries(new Intl.DateTimeFormat('en-CA', { timeZone:d.timeZone, year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',hourCycle:'h23' }).formatToParts(d.value).map(p => [p.type,p.value]));};
export function labInput(value) {
  if (!value) return '';
  const p=parts(value); return `${p.year}-${p.month}-${p.day}T${p.hour}:${p.minute}`;
}
export function labISO(value) {
  if (!value) return null;
  const desired=Date.parse(value+'Z'); let time=desired;
  if (!Number.isFinite(desired)) throw new Error('Date ou heure invalide.');
  for (let i=0;i<3;i++) time += desired-Date.parse(labInput(time)+'Z');
  if (labInput(time)!==value) throw new Error('Cette heure n’existe pas dans le calendrier Africa/Casablanca.');
  return new Date(time).toISOString();
}
export const labDate = value => labInput(value).slice(0,10);
export const labTime = value => {if(!value)return 'Non planifiée';const d=display(value);return new Intl.DateTimeFormat('fr-FR',{timeZone:d.timeZone,hour:'2-digit',minute:'2-digit'}).format(d.value);};
export const labDateTime = value => {if(!value)return '—';const d=display(value);return new Intl.DateTimeFormat('fr-FR',{timeZone:d.timeZone,dateStyle:'short',timeStyle:'short'}).format(d.value);};
export function addDays(day,count) { const d=new Date(day+'T12:00:00Z');d.setUTCDate(d.getUTCDate()+count);return d.toISOString().slice(0,10); }
export function addMonths(day,count) { const d=new Date(day.slice(0,7)+'-01T12:00:00Z');d.setUTCMonth(d.getUTCMonth()+count);return d.toISOString().slice(0,10); }


export const taskLabels = { PENDING:'En attente',READY:'Prête',SCHEDULED:'Planifiée',IN_PROGRESS:'En cours',PAUSED:'En pause',BLOCKED:'Bloquée',COMPLETED:'Terminée',CANCELLED:'Annulée' };
