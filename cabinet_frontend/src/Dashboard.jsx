import { useEffect, useRef, useState } from 'react';
import api from './api/client';
import { errorText, money } from './api/contracts';
import { Button, Feedback, Paged, Panel } from './IntegrationUI';
import CaseWorkspace from './CaseWorkspace';
import { labDateTime } from './planningTime';

function Tile({ label, value, detail }) {
  return <div className="min-w-0 rounded-2xl border border-slate-200 bg-white p-4"><p className="text-sm text-slate-600">{label}</p><p className="mt-2 break-words text-2xl font-semibold">{value}</p>{detail && <p className="mt-1 text-xs text-slate-500">{detail}</p>}</div>;
}

export default function Dashboard({ refreshOrders }) {
  const [data, setData] = useState(null); const [error, setError] = useState(''); const [notice, setNotice] = useState('');
  const [loading, setLoading] = useState(true); const [selected, setSelected] = useState(null); const [opening, setOpening] = useState(false);
  const opener = useRef(null); const sequence = useRef(0); const mounted = useRef(true);
  async function load() {
    const current = ++sequence.current;
    try { const result = await api.get('dashboard/summary/'); if (current === sequence.current) { setData(result.data); setError(''); return true; } }
    catch (cause) { if (current === sequence.current) setError(errorText(cause)); }
    finally { if (current === sequence.current) setLoading(false); }
    return false;
  }
  useEffect(() => {
    mounted.current = true;
    const current = ++sequence.current;
    const controller = new AbortController();
    api.get('dashboard/summary/', { signal: controller.signal })
      .then(result => { if (current === sequence.current) { setData(result.data); setError(''); } })
      .catch(cause => { if (current === sequence.current) setError(errorText(cause)); })
      .finally(() => { if (current === sequence.current) setLoading(false); });
    return () => { mounted.current = false; sequence.current += 1; controller.abort(); };
  }, []);
  async function open(row, button) {
    opener.current = button; setOpening(true); setError('');
    try { const response = await api.get(`prescriptions/${row.id}/`); if (mounted.current) setSelected(response.data); }
    catch (cause) { if (mounted.current) setError(errorText(cause)); }
    finally { if (mounted.current) setOpening(false); }
  }
  async function refresh() {
    setLoading(true);
    await Promise.all([load(), refreshOrders()]);
    if (selected) { const response = await api.get(`prescriptions/${selected.id}/`); if (mounted.current) setSelected(response.data); }
  }
  const operations = data?.operations; const finance = data?.finance;
  const max = Math.max(1, ...(operations?.stages || []).map(stage => stage.count));
  return <section aria-label="Indicateurs du laboratoire" className="space-y-5">
    <div className="flex flex-wrap items-center justify-between gap-3"><p className="text-sm text-slate-600">Production et finances du laboratoire sélectionné.</p><Button disabled={loading} onClick={async () => { setLoading(true); setNotice(''); if (await load()) setNotice('Tableau de bord actualisé.'); }}>Actualiser le tableau de bord</Button></div>
    <Feedback error={error} notice={notice} />{loading && <p role="status">Actualisation des indicateurs…</p>}
    {data && <><p className="text-xs text-slate-500">Situation au {labDateTime(data.as_of)} · Africa/Casablanca</p>
      {operations && <><div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <Tile label="Dossiers actifs" value={operations.active_cases} /><Tile label="En retard" value={operations.late.length} detail="Échéance dépassée ou fin projetée tardive" />
        <Tile label="À risque" value={operations.at_risk.length} detail="Travail restant sans créneau" /><Tile label="En pause ou bloqués" value={operations.paused_or_blocked_cases} />
        <Tile label="Livraisons dues aujourd’hui" value={operations.deliveries_due_today} /><Tile label="Livraisons dues cette semaine" value={operations.deliveries_due_this_week} detail="D’aujourd’hui à dimanche" />
        <Tile label="Reprises sur 30 jours" value={operations.rework_30_days.rate_percent == null ? '—' : `${operations.rework_30_days.rate_percent.toLocaleString('fr-FR')} %`} detail={`${operations.rework_30_days.reworks} reprise(s) / ${operations.rework_30_days.delivered} dossier(s) livré(s)`} />
      </div><Panel title="Dossiers par étape"><ul className="space-y-3">{operations.stages.map(stage => <li key={stage.key}><div className="flex justify-between gap-3 text-sm"><span>{stage.label}</span><strong>{stage.count}</strong></div><div aria-hidden="true" className="mt-1 h-2 rounded bg-slate-100"><div className="h-full rounded bg-teal-700" style={{ width: `${stage.count / max * 100}%` }} /></div></li>)}</ul></Panel>
        {[['En retard', operations.late], ['À risque', operations.at_risk]].map(([title, rows]) => <Panel key={title} title={title}><Paged rows={rows}>{items => <ul className="space-y-3">{items.map(row => <li key={row.id} className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-slate-200 p-3"><div className="min-w-0"><p className="break-words font-medium">{row.patient_ref}</p><p className="text-xs text-slate-600">{row.stage_label} · Échéance : {labDateTime(row.deadline_at)}</p></div><Button disabled={opening} onClick={event => void open(row, event.currentTarget)}>Ouvrir le dossier {row.patient_ref}</Button></li>)}{!items.length && <li>Aucun dossier.</li>}</ul>}</Paged></Panel>)}</>}
      {finance && <Panel title="Finances"><div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
        <Tile label="Facturé ce mois" value={money(finance.billed_this_month)} detail={`Mois d’émission : ${finance.month.slice(0, 7)}`} />
        <Tile label="Facturé au dernier mois clôturé" value={money(finance.invoiced_last_closed_month)} detail={finance.last_closed_month ? `Mois du relevé : ${finance.last_closed_month.slice(0, 7)} · avant avoirs` : 'Aucun relevé clôturé'} />
        <Tile label="Créances à encaisser" value={money(finance.total_receivables)} /><Tile label="Dont retard de plus de 60 jours" value={money(finance.over_60_days)} />
        <Tile label="Trop-perçu à régulariser" value={money(finance.overpaid_amount)} /><Tile label="Contestations ouvertes" value={finance.open_disputes} />
      </div><p className="mt-3 text-xs text-slate-500">Facturation : {finance.analytics.last_refreshed_at ? `catalogue actualisé le ${labDateTime(finance.analytics.last_refreshed_at)}` : 'catalogue en attente d’actualisation'}. Créances et contestations calculées en direct.</p>{finance.analytics.stale && <p className="text-sm text-amber-800">Le catalogue de facturation est ancien ou en attente. Les montants facturés peuvent ne pas refléter les dernières opérations.</p>}{finance.analytics.refresh_failed && <p className="text-sm text-amber-800">La dernière actualisation du catalogue a échoué.</p>}</Panel>}
    </>}
    {selected && <CaseWorkspace key={selected.id} order={selected} refresh={refresh} returnFocus={opener} onClose={() => setSelected(null)} />}
  </section>;
}
