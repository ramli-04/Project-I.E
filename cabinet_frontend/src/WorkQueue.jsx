import { useCallback, useEffect, useRef, useState } from 'react';
import api from './api/client';
import { allRows, errorText, workstation } from './api/contracts';
import { previewMode } from './api/preview';
import { caseStatusLabel, frenchMessage } from './api/messages';
import { Button, control, Feedback, Field } from './IntegrationUI';
import CaseWorkspace from './CaseWorkspace';
import { labDateTime } from './planningTime';
import { groupQueue, riskLabels, roleLabels, serviceLabels } from './workQueueHelpers';
import { useTestCaseFilter } from './TestCaseToggle';

export default function WorkQueue({ refreshOrders }) {
  const [rows, setRows] = useState([]); const [query, setQuery] = useState(''); const [role, setRole] = useState('');
  const [error, setError] = useState(''); const [notice, setNotice] = useState(''); const [loading, setLoading] = useState(true); const [opening, setOpening] = useState(false);
  const [selected, setSelected] = useState(null); const opener = useRef(null); const sequence = useRef(0);
  const mounted = useRef(true);
  const { visible, toggle } = useTestCaseFilter(rows);
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; sequence.current += 1; }; }, []);
  const load = useCallback(async () => {
    const request = ++sequence.current;
    setLoading(true);
    try {
      const data = await allRows(api, 'work-queue/', { search: query, role });
      if (request === sequence.current) { setRows(data); setError(''); return true; }
    } catch (e) { if (request === sequence.current) setError(errorText(e)); return false; }
    finally { if (request === sequence.current) setLoading(false); }
  }, [query, role]);
  useEffect(() => {
    const debounce = setTimeout(() => void load(), 200);
    const update = () => { if (document.visibilityState === 'visible') void load(); };
    const timer = previewMode ? null : setInterval(update, 15000);
    window.addEventListener('focus', update); document.addEventListener('visibilitychange', update);
    return () => { clearTimeout(debounce); clearInterval(timer); sequence.current += 1; window.removeEventListener('focus', update); document.removeEventListener('visibilitychange', update); };
  }, [load]);
  async function open(row, button) {
    opener.current = button; setOpening(true); setError('');
    try {
      const { data } = await api.get(`prescriptions/${row.id}/`);
      if (mounted.current) setSelected({ order: data, entry: row });
    } catch (e) { if (mounted.current) setError(errorText(e)); }
    finally { if (mounted.current) setOpening(false); }
  }
  async function refresh() {
    await Promise.all([load(), refreshOrders()]);
    if (selected) {
      const { data } = await api.get(`prescriptions/${selected.order.id}/`);
      if (mounted.current) setSelected(previous => previous ? { ...previous, order: data } : null);
    }
  }
  return <section aria-label="File de travail" className="space-y-5">
    <div className="flex flex-wrap items-start justify-between gap-3"><p className="text-sm text-slate-600">Les actions de votre poste, classées par risque et échéance.</p><Button disabled={loading} onClick={async () => { setNotice(''); if (await load()) setNotice('File de travail actualisée.'); }}>Actualiser la file</Button></div>
    <Feedback error={error} notice={notice} />
    <div className="grid gap-3 sm:grid-cols-2"><Field label="Rechercher dans ma file"><input className={control} value={query} onChange={e => setQuery(e.target.value)} placeholder="Référence patient, dentiste…" /></Field>
      {workstation() === 'MANAGER' && <Field label="Filtrer par poste"><select className={control} value={role} onChange={e => setRole(e.target.value)}><option value="">Tous les postes</option>{Object.entries(roleLabels).map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select></Field>}</div>
    {loading && <p role="status" className="text-sm text-slate-500">Actualisation de la file…</p>}
    {toggle}
    {!loading && !error && !visible.length && <p className="rounded-2xl border border-slate-200 bg-white p-6">Rien à faire pour votre poste pour le moment.</p>}
    {groupQueue(visible).map(group => <section key={group.key} aria-label={`${group.label} (${group.rows.length})`} className="space-y-3"><h2 className="text-lg font-semibold">{group.label} <span className="text-sm text-slate-500">({group.rows.length})</span></h2>
      {group.rows.map(row => <article key={row.id} aria-label={`Dossier ${row.patient_ref}`} className="min-w-0 space-y-3 rounded-2xl border border-slate-200 bg-white p-4 sm:p-5">
        <div className="flex flex-wrap items-start justify-between gap-3"><div className="min-w-0"><h3 className="break-words font-semibold">{row.patient_ref}</h3><p className="break-words text-sm text-slate-600">{row.dentist_name}</p></div><span className="rounded-full bg-teal-50 px-3 py-1 text-xs text-teal-800">{row.current_step.stage_label}</span></div>
        <p className="text-sm font-medium">{caseStatusLabel(row)}</p>
        <div className="flex flex-wrap items-center gap-2 text-xs"><span className={`rounded-full px-2 py-1 ${row.risk === 'LATE' ? 'bg-red-50 text-red-800' : row.risk === 'AT_RISK' ? 'bg-amber-50 text-amber-800' : 'bg-emerald-50 text-emerald-800'}`}>{riskLabels[row.risk]}</span><span>Échéance : {labDateTime(row.deadline_at)}</span><span className="rounded-full bg-slate-100 px-2 py-1">{serviceLabels[row.delivery_service] || (row.is_fast_track ? 'Urgent' : 'Standard')}</span>{row.is_paused && <span className="text-amber-800">En pause</span>}</div>
        {(row.waiting_reason || row.pause_reason) && <p className="break-words text-sm text-slate-600">{frenchMessage(row.waiting_reason || row.pause_reason)}</p>}
        <Button disabled={opening} className="max-w-full whitespace-normal text-left" onClick={event => void open(row, event.currentTarget)}>{row.primary_action.label}</Button>
      </article>)}
    </section>)}
    {selected && <CaseWorkspace key={selected.order.id} order={selected.order} refresh={refresh} queueEntry={selected.entry} focusAction={selected.entry.primary_action.kind === 'QUOTE' ? 'quote' : 'primary'} returnFocus={opener} onClose={() => setSelected(null)} />}
  </section>;
}
