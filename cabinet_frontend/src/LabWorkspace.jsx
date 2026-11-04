import { useState } from 'react';
import { ArrowLeft, ArrowRight, Clock, Pause, Search } from 'lucide-react';
import { DashboardAlerts } from './LabAlerts';
import ClinicalDashboard from './ClinicalDashboard';
import FinanceDashboard from './FinanceDashboard';
import { workstation, completed } from './api/contracts';
import { Paged } from './IntegrationUI';
import { ProductionCard } from './ProductionWorkflow';

const date = value => value ? new Date(value).toLocaleDateString('fr-FR') : 'Non renseignée';
const progress = order => {
  const steps = order.workflow_steps || [];
  const index = steps.findIndex(step => step.key === order.status);
  return completed(order.status) ? 100 : Math.max(0, Math.round(index / Math.max(steps.length - 1, 1) * 100));
};

function OrderSummary({ order, onOpen }) {
  const percent = progress(order);
  return <article aria-label={`Résumé ${order.patient_ref}`} className="relative rounded-2xl border border-slate-200/80 bg-white p-5 space-y-4">
    <div className="flex flex-wrap items-start justify-between gap-3"><div><h3 className="text-lg font-semibold text-slate-900">{order.patient_ref}</h3><p className="mt-1 text-sm text-slate-600">{order.dentist_name}</p><p className="mt-1 font-mono text-[10px] text-slate-500">ID : {order.id}</p></div><span className={`rounded-full px-3 py-1 text-xs ${order.is_paused ? 'bg-amber-400/10 text-amber-700' : 'bg-sky-400/10 text-teal-700'}`}>{order.is_paused ? 'En pause' : order.accepted ? 'Acceptée' : 'Nouvelle demande'}</span></div>
    <div className="grid gap-3 text-xs sm:grid-cols-2"><div><p className="text-slate-500">Demande reçue le</p><p className="mt-1 text-slate-600">{date(order.created_at)}</p></div><div><p className="text-slate-500">Réception des éléments</p><p className="mt-1 text-slate-600">{order.received_at ? date(order.received_at) : 'À confirmer'}</p></div><div><p className="text-slate-500">Tâche actuelle</p><p className="mt-1 text-teal-800">{order.status_label}</p></div><div><p className="text-slate-500">Livraison prévue</p><p className="mt-1 text-slate-600">{date(order.delivery_date)}</p></div></div>
    <div><div className="mb-2 flex justify-between text-xs"><span className="text-slate-500">Progression du parcours</span><span className="text-teal-700">{percent}%</span></div><div role="progressbar" aria-label={`Progression ${order.patient_ref}`} aria-valuemin={0} aria-valuemax={100} aria-valuenow={percent} className="h-1.5 rounded-full bg-slate-100"><div className="h-full rounded-full bg-sky-400" style={{ width: `${percent}%` }} /></div></div>
    <div className="rounded-xl bg-slate-50 p-3 text-xs"><p className="text-slate-500">Problèmes actuels</p><p className="mt-1 whitespace-pre-wrap text-slate-600">{order.current_issues || 'Aucun problème signalé.'}</p>{order.is_paused && <p className="mt-2 flex items-start gap-2 whitespace-pre-wrap text-amber-700"><Pause className="mt-0.5 h-3 w-3 shrink-0" />Pause : {order.pause_reason}</p>}</div>
    {onOpen && <><span className="inline-flex items-center gap-2 text-sm text-teal-700">Ouvrir le diagramme <ArrowRight className="h-4 w-4" /></span><button onClick={onOpen} aria-label={`Ouvrir le diagramme ${order.patient_ref}`} className="absolute inset-0 rounded-2xl hover:bg-teal-700/[0.03] focus-visible:outline-2 focus-visible:outline-sky-400" /></>}
  </article>;
}

export function BillingOverview() {
  return ['MANAGER','COMPTABILITE'].includes(workstation()) ? <FinanceDashboard /> : <p>Acces comptabilite requis.</p>;
}

export function LabOverview({ orders, tab, setTab, alertState, alertFocus, onAlertSelect }) {
  const [query, setQuery] = useState('');
  const visible = orders.filter(order => `${order.patient_ref} ${order.dentist_name}`.toLowerCase().includes(query.toLowerCase()));
  return <div className="space-y-5"><div className="clinical-subnav">{[['dashboard', 'Vue production'], ['commandes', 'Commandes'], ['facturation', 'Facturation']].map(([key,label]) => <button key={key} className={tab === key ? 'active' : ''} onClick={() => setTab(key)} aria-pressed={tab === key}>{label}</button>)}<span>VOTRE LABORATOIRE, EN UN REGARD</span></div>
    {tab === 'dashboard' && <><ClinicalDashboard orders={orders} onOpenOrders={() => setTab('commandes')} />{alertState.alerts.length > 0 && <div className="mt-6"><DashboardAlerts {...alertState} focusRequest={alertFocus} onSelect={onAlertSelect}/></div>}</>}
    {tab === 'commandes' && <div className="space-y-5"><h2 className="text-xl font-semibold">Commandes</h2><input aria-label="Rechercher dans les commandes" placeholder="Rechercher une commande ou un client..." value={query} onChange={event => setQuery(event.target.value)} className="w-full rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm" /><div className="grid gap-5 lg:grid-cols-2">{visible.map(order => <OrderSummary key={order.id} order={order} />)}</div>{!visible.length && <p className="py-8 text-center text-slate-500">Aucune commande.</p>}</div>}
    {tab === 'facturation' && <BillingOverview orders={orders} />}
  </div>;
}

export function OrderManagement({ orders, patchOrder, refresh }) {
  const [tab, setTab] = useState('orders');
  const [selectedId, setSelectedId] = useState(null);
  const [query, setQuery] = useState('');
  const [busy, setBusy] = useState(null);
  const [error, setError] = useState('');
  const canAccept = ['MANAGER','RECEPTION'].includes(workstation());
  const selected = orders.find(order => order.id === selectedId);
  const filtered = orders.filter(order => `${order.patient_ref} ${order.dentist_name}`.toLowerCase().includes(query.toLowerCase()));
  function open(order) { setSelectedId(order.id); setTab('steps'); }
  async function accept(order) {
    setBusy(order.id); setError('');
    try { await patchOrder(order.id, { accepted: true }); }
    catch { setError('Impossible d’accepter cette commande. Réessayez.'); }
    finally { setBusy(null); }
  }
  return <div className="space-y-6"><div><p className="text-xs uppercase tracking-widest text-teal-700">Gestion</p><h1 className="mt-2 text-2xl font-semibold">Commandes</h1><p className="mt-2 text-sm text-slate-500">Acceptez les demandes puis suivez chaque commande dans son diagramme de fabrication.</p></div><div className="flex gap-2 border-b border-slate-200/80">{[['orders', 'Commandes'], ['steps', 'Étapes de commandes']].map(([key, label]) => <button key={key} onClick={() => setTab(key)} aria-pressed={tab === key} className={`border-b-2 px-4 py-3 text-sm ${tab === key ? 'border-sky-400 text-teal-700' : 'border-transparent text-slate-500'}`}>{label}</button>)}</div>{error && <p role="alert" className="text-sm text-red-700">{error}</p>}
    {tab === 'orders' ? <><div className="relative"><Search className="absolute left-3 top-3 h-4 w-4 text-slate-500" /><input aria-label="Rechercher dans la gestion des commandes" value={query} onChange={event => setQuery(event.target.value)} placeholder="Référence ou nom du client…" className="w-full rounded-xl border border-slate-200 bg-white py-2.5 pl-10 pr-4 text-sm" /></div><div className="grid items-start gap-6 xl:grid-cols-2">{[false, true].map(accepted => <section key={String(accepted)} aria-label={accepted ? 'Commandes acceptées' : 'Commandes reçues'} className="rounded-2xl border border-slate-200/80 bg-slate-50 p-4"><h2 className="mb-4 flex justify-between text-sm font-semibold">{accepted ? 'Commandes acceptées' : 'Commandes reçues'}<span className="rounded-full bg-slate-100 px-2 text-slate-500">{filtered.filter(order => order.accepted === accepted).length}</span></h2><div className="space-y-4">{<Paged rows={filtered.filter(order => order.accepted === accepted)}>{pageRows => pageRows.map(order => <div key={order.id}><OrderSummary order={order} onOpen={() => open(order)} />{!accepted && canAccept && <button disabled={busy === order.id} onClick={() => accept(order)} className="mt-2 w-full rounded-xl bg-teal-600 px-4 py-3 text-sm font-medium disabled:opacity-50">{busy === order.id ? 'Acceptation…' : `Accepter ${order.patient_ref}`}</button>}</div>)}</Paged>}{!filtered.some(order => order.accepted === accepted) && <p className="py-10 text-center text-sm text-slate-500">{accepted ? 'Aucune commande acceptée.' : 'Aucune nouvelle demande.'}</p>}</div></section>)}</div></> : <div className="space-y-5"><label className="block text-sm text-slate-500">Commande à suivre<select aria-label="Commande à suivre" value={selectedId || ''} onChange={event => setSelectedId(event.target.value)} className="mt-2 w-full rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-900"><option value="">Sélectionner une commande acceptée</option>{orders.map(order => <option key={order.id} value={order.id}>{order.patient_ref} — {order.dentist_name}</option>)}</select></label>{selected ? <><button onClick={() => setTab('orders')} className="flex items-center gap-2 text-sm text-slate-500"><ArrowLeft className="h-4 w-4" />Retour aux commandes</button><ProductionCard key={selected.id} order={selected} patchOrder={patchOrder} refresh={refresh} diagram /></> : <div className="rounded-2xl border border-dashed border-slate-200 p-12 text-center"><Clock className="mx-auto mb-3 h-8 w-8 text-slate-500" /><p className="text-sm text-slate-500">Choisissez une commande acceptée pour afficher son diagramme.</p></div>}</div>}
  </div>;
}
