import { useRef, useState } from 'react';
import { ArrowRight, Pause, Search } from 'lucide-react';
import { completed } from './api/contracts';
import { caseStatusLabel, frenchMessage } from './api/messages';
import { Paged } from './IntegrationUI';
import CaseWorkspace from './CaseWorkspace';
import { useTestCaseFilter } from './TestCaseToggle';

const date = value => value ? new Date(value).toLocaleDateString('fr-FR', { timeZone: 'Africa/Casablanca' }) : 'Non renseignée';
const progress = order => {
  const steps = order.workflow_steps || [];
  const index = steps.findIndex(step => step.key === order.status);
  return completed(order.status) ? 100 : Math.max(0, Math.round(index / Math.max(steps.length - 1, 1) * 100));
};

function OrderSummary({ order, onOpen }) {
  const percent = progress(order);
  return <article aria-label={`Résumé ${order.patient_ref}`} className="relative rounded-2xl border border-slate-200/80 bg-white p-5 space-y-4">
    <div className="flex flex-wrap items-start justify-between gap-3"><div><h3 className="text-lg font-semibold text-slate-900">{order.patient_ref}</h3><p className="mt-1 text-sm text-slate-600">{order.dentist_name}</p><p className="mt-1 font-mono text-[10px] text-slate-500">ID : {order.id}</p></div><span className={`rounded-full px-3 py-1 text-xs ${order.is_paused ? 'bg-amber-400/10 text-amber-700' : 'bg-sky-400/10 text-teal-700'}`}>{order.is_paused ? 'En pause' : order.accepted ? 'Acceptée' : 'Nouvelle demande'}</span></div>
    <div className="grid gap-3 text-xs sm:grid-cols-2"><div><p className="text-slate-500">Demande reçue le</p><p className="mt-1 text-slate-600">{date(order.created_at)}</p></div><div><p className="text-slate-500">Réception des éléments</p><p className="mt-1 text-slate-600">{order.received_at ? date(order.received_at) : 'À confirmer'}</p></div><div><p className="text-slate-500">Tâche actuelle</p><p className="mt-1 text-teal-800">{caseStatusLabel(order)}</p></div><div><p className="text-slate-500">Livraison prévue</p><p className="mt-1 text-slate-600">{date(order.delivery_date)}</p></div></div>
    <div><div className="mb-2 flex justify-between text-xs"><span className="text-slate-500">Progression du parcours</span><span className="text-teal-700">{percent}%</span></div><div role="progressbar" aria-label={`Progression ${order.patient_ref}`} aria-valuemin={0} aria-valuemax={100} aria-valuenow={percent} className="h-1.5 rounded-full bg-slate-100"><div className="h-full rounded-full bg-sky-400" style={{ width: `${percent}%` }} /></div></div>
    <div className="rounded-xl bg-slate-50 p-3 text-xs"><p className="text-slate-500">Problèmes actuels</p><p className="mt-1 whitespace-pre-wrap text-slate-600">{order.current_issues || 'Aucun problème signalé.'}</p>{order.is_paused && <p className="mt-2 flex items-start gap-2 whitespace-pre-wrap text-amber-700"><Pause className="mt-0.5 h-3 w-3 shrink-0" />Pause : {frenchMessage(order.pause_reason)}</p>}</div>
    <span className="inline-flex items-center gap-2 text-sm text-teal-700">Ouvrir le dossier <ArrowRight className="h-4 w-4" /></span><button onClick={onOpen} aria-label={`Ouvrir le dossier ${order.patient_ref}`} className="absolute inset-0 rounded-2xl hover:bg-teal-700/[0.03] focus-visible:outline-2 focus-visible:outline-sky-400" />
  </article>;
}

export function OrderManagement({ orders, refresh }) {
  const [selectedId, setSelectedId] = useState(null); const opener = useRef(null);
  const [query, setQuery] = useState('');
  const selected = orders.find(order => order.id === selectedId);
  const { visible, toggle } = useTestCaseFilter(orders);
  const filtered = visible.filter(order => `${order.patient_ref} ${order.dentist_name}`.toLowerCase().includes(query.toLowerCase()));
  return <div className="space-y-6"><div><p className="text-xs uppercase tracking-widest text-teal-700">Gestion</p><h1 className="mt-2 text-2xl font-semibold">Commandes</h1><p className="mt-2 text-sm text-slate-500">Ouvrez un dossier pour voir l’action attendue et son parcours.</p>{toggle}</div>
    <div className="relative"><Search className="absolute left-3 top-3 h-4 w-4 text-slate-500" /><input aria-label="Rechercher dans la gestion des commandes" value={query} onChange={event => setQuery(event.target.value)} placeholder="Référence ou nom du client…" className="w-full rounded-xl border border-slate-200 bg-white py-2.5 pl-10 pr-4 text-sm" /></div>
    <div className="grid items-start gap-6 xl:grid-cols-2">{[false, true].map(accepted => <section key={String(accepted)} aria-label={accepted ? 'Commandes acceptées' : 'Commandes reçues'} className="rounded-2xl border border-slate-200 bg-slate-50 p-4"><h2 className="mb-4 flex justify-between text-sm font-semibold">{accepted ? 'Commandes acceptées' : 'Commandes reçues'}<span className="rounded-full bg-slate-100 px-2 text-slate-500">{filtered.filter(order => order.accepted === accepted).length}</span></h2><div className="space-y-4"><Paged rows={filtered.filter(order => order.accepted === accepted)}>{pageRows => pageRows.map(order => <OrderSummary key={order.id} order={order} onOpen={event => { opener.current = event.currentTarget; setSelectedId(order.id); }} />)}</Paged>{!filtered.some(order => order.accepted === accepted) && <p className="py-10 text-center text-sm text-slate-500">{accepted ? 'Aucune commande acceptée.' : 'Aucune nouvelle demande.'}</p>}</div></section>)}</div>
    {selected && <CaseWorkspace key={selected.id} order={selected} refresh={refresh} returnFocus={opener} onClose={() => setSelectedId(null)} />}
  </div>;
}
