import { useEffect, useRef, useState } from 'react';
import { AlertTriangle, ArrowRight, Bell, X } from 'lucide-react';

const labels = { stock: 'Seuil du stock', expiry: 'Stock périmé', maintenance: 'Maintenance', contract: 'Contrat du personnel', qualification: 'Qualifications' };
export function AlertPopup({ alerts, onOpen }) {
  const [dismissed, setDismissed] = useState('');
  const signature = alerts.map(alert => `${alert.id}:${alert.message}`).join('|');
  if (!alerts.length || dismissed === signature) return null;
  return <aside aria-label="Notification des alertes" className="fixed bottom-6 right-6 z-30 w-96 max-w-[calc(100vw-3rem)] rounded-2xl border border-red-400/40 bg-rose-50 text-red-100 shadow-2xl shadow-red-950/40">
    <button aria-label="Fermer la notification" onClick={() => setDismissed(signature)} className="absolute right-2 top-2 rounded-lg p-1.5 text-red-700 hover:bg-red-400/10"><X className="h-4 w-4" /></button>
    <button onClick={() => { setDismissed(signature); onOpen(); }} className="w-full rounded-2xl p-5 pr-10 text-left focus-visible:outline-2 focus-visible:outline-red-300">
      <div className="flex items-center gap-2 text-sm font-semibold text-red-700"><AlertTriangle className="h-4 w-4 shrink-0" />{alerts.length} alerte{alerts.length > 1 ? 's' : ''} au laboratoire</div>
      <p role="status" className="mt-2 text-sm leading-relaxed">{alerts[0].message}</p>
      <span className="mt-3 inline-flex items-center gap-2 text-xs font-medium text-red-700">Voir toutes les alertes sur le dashboard <ArrowRight className="h-3 w-3" /></span>
    </button>
  </aside>;
}

export function DashboardAlerts({ alerts, loading, error, focusRequest, onSelect, compact = false }) {
  const panel = useRef(null);
  useEffect(() => {
    if (focusRequest) {
      panel.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
      panel.current?.focus({ preventScroll: true });
    }
  }, [focusRequest]);
  return <section ref={panel} tabIndex={-1} aria-label="Toutes les alertes" className="scroll-mt-24 rounded-2xl border border-red-400/20 bg-white p-6 outline-none focus:ring-1 focus:ring-red-400/40">
    <div className="flex items-center justify-between gap-3"><h2 className="flex items-center gap-2 text-lg font-semibold"><Bell className="h-5 w-5 text-red-700" />Alertes du laboratoire</h2><span className="rounded-full bg-red-400/10 px-3 py-1 text-sm text-red-700">{alerts.length}</span></div>
    <p className="mt-2 text-xs text-slate-500">{compact ? 'Stock, maintenance, contrats et qualifications. Cliquez pour ouvrir la fiche.' : 'Stock au seuil ou en dessous ; maintenance, contrats et qualifications à échéance sous 7 jours ou dépassés. Cliquez sur une alerte pour ouvrir sa fiche.'}</p>
    {error && <p role="alert" className="mt-4 text-sm text-red-700">{error}</p>}
    {loading ? <p role="status" className="py-6 text-sm text-slate-500">Chargement des alertes…</p> : !alerts.length && !error ? <p className="py-6 text-sm text-emerald-700">Aucune alerte en cours.</p> : <div className={`mt-4 space-y-2 ${compact ? 'max-h-72 overflow-y-auto pr-1' : ''}`}>{alerts.map(alert => <button key={alert.id} onClick={() => onSelect(alert)} className="flex w-full items-center justify-between gap-3 rounded-xl border border-red-400/20 bg-red-400/5 p-3 text-left transition-colors hover:border-red-400/50 hover:bg-red-400/10">
      <div><span className="text-xs font-medium text-red-700">{labels[alert.type]} · {alert.reference}{alert.overdue ? ' · Échéance dépassée' : ''}</span><p className="mt-1 text-sm text-slate-800">{alert.message}</p><p className="mt-2 text-xs text-slate-500">Configuration / {alert.section === 'staff' ? 'Personnel' : alert.section === 'equipment' ? 'Matériel' : 'Stock'} / {alert.name}</p></div><ArrowRight className="h-4 w-4 shrink-0 text-red-700" />
    </button>)}</div>}
  </section>;
}
