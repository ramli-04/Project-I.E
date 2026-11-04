import { useEffect, useRef, useState } from 'react';
import api from './api/client';
import { allRows, download, errorText, money, retryableRequest, rowsOf } from './api/contracts';
import { Button, control, Feedback, Field, Paged, Panel } from './IntegrationUI';

export default function FinanceDashboard() {
  const [data, setData] = useState(null); const [periodId, setPeriodId] = useState(''); const [closeReview, setCloseReview] = useState(false);
  const [busy, setBusy] = useState(false); const [error, setError] = useState(''); const [notice, setNotice] = useState(''); const [reload, setReload] = useState(0);
  async function fetchData(signal) {
    const [periods, lines, invoices, credits, disputes, clinics] = await Promise.all(['billing/periods/','billing/statement-lines/','billing/invoices/','billing/credit-notes/','billing/disputes/','partner-clinics/'].map(path => allRows(api, path, {}, signal)));
    return { periods, lines, invoices, credits, disputes, clinics };
  }
  useEffect(() => { const abort = new AbortController(); fetchData(abort.signal).then(setData).catch(e => { if (!abort.signal.aborted) setError(errorText(e)); }); return () => abort.abort(); }, [reload]);
  async function mutate(action, message = 'Action comptable enregistrée.') {
    if (busy) return; setBusy(true); setError(''); setNotice('');
    try { await action(); setNotice(message); setData(await fetchData()); } catch (e) { setError(errorText(e)); } finally { setBusy(false); }
  }
  const period = data?.periods.find(p => p.id === periodId);
  const lines = data?.lines.filter(line => line.period === periodId) || [];
  const included = lines.filter(line => !line.contested && !line.excluded);
  const total = included.reduce((sum, line) => sum + Number(line.base_amount) + Number(line.express_surcharge), 0);
  return <div className="space-y-5"><h1 className="text-2xl font-semibold">Situations mensuelles et facturation</h1><p className="text-sm text-slate-500">Les relevés regroupent les dossiers livrés dans le mois, selon le calendrier Africa/Casablanca. Les périodes se clôturent après la fin du mois.</p><Feedback error={error} notice={notice} /><Button disabled={busy} onClick={() => { setError(''); setReload(v => v + 1); }}>Actualiser</Button>
    <CatalogFinance />
    {!data ? <p>Chargement de la comptabilité…</p> : <>
      <Panel title="Relevés de livraison"><Field label="Cabinet et mois de livraison"><select className={control} value={periodId} onChange={e => { setPeriodId(e.target.value); setCloseReview(false); }}><option value="">Choisir un relevé</option>{data.periods.map(p => <option key={p.id} value={p.id}>{p.month.slice(0,7)} · {data.clinics.find(c => c.id === p.clinic)?.name || p.clinic} · {p.closed_at ? 'Clôturé' : 'Ouvert'}</option>)}</select></Field>
        {period && <><p>{included.length} dossier(s) inclus · {money(total)} · {period.closed_at ? 'Clôturé' : 'Ouvert'}</p><Paged rows={lines}>{rows => <div className="space-y-3">{rows.map(line => <LineAdjustment key={`${line.id}:${line.contested}:${line.excluded}`} line={line} closed={Boolean(period.closed_at)} busy={busy} mutate={mutate} />)}</div>}</Paged>
          {!period.closed_at && <>{!closeReview ? <Button disabled={busy || !included.length} onClick={() => setCloseReview(true)}>Vérifier la clôture</Button> : <div className="space-y-3 rounded-xl border border-amber-400/30 p-4"><p>Émettre la facture définitive pour {included.length} dossiers, soit {money(total)} ? {lines.length - included.length} ligne(s) contestée(s) ou exclue(s) resteront hors facture.</p><Button disabled={busy} onClick={() => mutate(async () => { await api.post(`billing/periods/${periodId}/close/`, {}); setCloseReview(false); }, 'Période clôturée. La facture PDF sera disponible après traitement.')}>Confirmer la clôture et émettre la facture</Button><Button onClick={() => setCloseReview(false)}>Annuler</Button></div>}</>}
        </>}
      </Panel>
      <Panel title="Factures et avoirs"><Paged rows={data.invoices}>{rows => <div className="space-y-4">{rows.map(invoice => <InvoiceCard key={invoice.id} invoice={invoice} credits={data.credits.filter(c => c.invoice === invoice.id)} busy={busy} mutate={mutate} />)}{!rows.length && <p className="text-sm text-slate-500">Aucune facture émise.</p>}</div>}</Paged></Panel>
      <Panel title="Contestations"><Paged rows={data.disputes}>{rows => <div className="space-y-4">{rows.map(d => <DisputeCard key={`${d.id}:${d.status}`} dispute={d} busy={busy} mutate={mutate} />)}{!rows.length && <p className="text-sm text-slate-500">Aucune contestation.</p>}</div>}</Paged></Panel>
    </>}
  </div>;
}
function LineAdjustment({ line, closed, busy, mutate }) {
  const [contested, setContested] = useState(line.contested); const [excluded, setExcluded] = useState(line.excluded); const [reason, setReason] = useState(line.dispute_reason || '');
  return <div className="space-y-3 rounded-xl border border-slate-200/80 p-4"><p className="text-sm">{line.snapshot?.patient_ref || line.prescription} · {money(Number(line.base_amount) + Number(line.express_surcharge))}</p><p className="text-xs text-slate-500">Livraison : {line.snapshot?.delivered_at ? new Date(line.snapshot.delivered_at).toLocaleString('fr-FR', { timeZone: 'Africa/Casablanca' }) : 'Non renseignée'}</p><fieldset disabled={closed || busy} className="space-y-3"><div className="flex gap-5 text-sm"><label className="flex gap-2"><input type="checkbox" checked={contested} onChange={e => setContested(e.target.checked)} />Contestée</label><label className="flex gap-2"><input type="checkbox" checked={excluded} onChange={e => setExcluded(e.target.checked)} />Exclue</label></div><Field label="Motif de l’ajustement"><input className={control} value={reason} onChange={e => setReason(e.target.value)} /></Field>{!closed && <Button disabled={!reason.trim() || busy} onClick={() => mutate(() => api.post(`billing/statement-lines/${line.id}/adjust/`, { contested, excluded, reason }))}>Enregistrer l’ajustement</Button>}</fieldset></div>;
}
function InvoiceCard({ invoice, credits, busy, mutate }) {
  const [caseId, setCaseId] = useState(''); const [amount, setAmount] = useState(''); const [reason, setReason] = useState(''); const request = useRef(retryableRequest());
  const selected = invoice.lines.find(line => line.case_id === caseId);
  const available = selected ? Number(selected.total_amount) - credits.filter(c => c.prescription === caseId).reduce((sum,c) => sum + Number(c.amount), 0) : 0;
  return <div className="space-y-3 rounded-xl border border-slate-200/80 p-4"><p>{invoice.number} · {invoice.clinic_name} · {money(invoice.total_amount)}</p><Button disabled={busy} onClick={() => mutate(() => download(api, `billing/invoices/${invoice.id}/pdf/`, `${invoice.number}.pdf`), 'Facture téléchargée.')}>Télécharger le PDF</Button><details><summary className="cursor-pointer text-sm text-teal-700">Émettre un avoir sur une ligne</summary><form className="mt-3 space-y-3" onSubmit={e => { e.preventDefault(); mutate(async () => { await request.current(api, `billing/invoices/${invoice.id}/credit/`, { prescription: caseId, amount, reason }); setAmount(''); setReason(''); }, 'Avoir émis. Son PDF sera disponible après traitement.'); }}><fieldset disabled={busy} className="space-y-3"><Field label="Dossier facturé"><select required className={control} value={caseId} onChange={e => setCaseId(e.target.value)}><option value="">Choisir</option>{invoice.lines.map(line => <option key={line.case_id} value={line.case_id}>{line.patient_ref || line.case_id} · {money(line.total_amount)}</option>)}</select></Field><p className="text-xs text-slate-500">Montant restant ajustable : {money(available)}</p><Field label="Montant de l’avoir (MAD)"><input className={control} required type="number" min="0.01" max={Math.max(0, available).toFixed(2)} step="0.01" value={amount} onChange={e => setAmount(e.target.value)} /></Field><Field label="Motif"><input className={control} required value={reason} onChange={e => setReason(e.target.value)} /></Field><Button type="submit" disabled={!selected || available <= 0}>Émettre l’avoir</Button></fieldset></form></details>{credits.map(c => <div key={c.id} className="text-sm text-amber-800">Avoir · {money(c.amount)} · {c.reason} <Button disabled={busy} onClick={() => mutate(() => download(api, `billing/credit-notes/${c.id}/pdf/`, `avoir-${c.id}.pdf`), 'Avoir téléchargé.')}>PDF</Button></div>)}</div>;
}
function DisputeCard({ dispute, busy, mutate }) {
  const [notes, setNotes] = useState(''); const [amount, setAmount] = useState('');
  return <div className="space-y-3 rounded-xl border border-slate-200/80 p-4"><p className="text-sm">Dossier {dispute.prescription} · {dispute.status}</p><p className="text-sm text-slate-500">{dispute.reason}</p>{dispute.status === 'OPEN' && <fieldset disabled={busy} className="space-y-3"><Field label="Justification de la décision"><textarea className={control} value={notes} onChange={e => setNotes(e.target.value)} /></Field>{dispute.invoice && <Field label="Montant de l’avoir si accepté (MAD)"><input className={control} type="number" min="0.01" step="0.01" value={amount} onChange={e => setAmount(e.target.value)} /></Field>}<div className="flex gap-3">{[['ACCEPTED','Accepter'],['REJECTED','Rejeter']].map(([decision,label]) => <Button key={decision} disabled={!notes.trim() || (decision === 'ACCEPTED' && dispute.invoice && !(Number(amount) > 0))} onClick={() => mutate(() => api.post(`billing/disputes/${dispute.id}/resolve/`, { decision, notes, ...(dispute.invoice ? { amount } : {}) }))}>{label}</Button>)}</div></fieldset>}</div>;
}
function CatalogFinance() {
  const [month, setMonth] = useState(''); const [result, setResult] = useState(null); const [error, setError] = useState(''); const [busy, setBusy] = useState(false);
  async function load() {
    setBusy(true); setError('');
    try {
      const params = month ? { month } : {};
      const [statements, finances] = await Promise.all([allRows(api, 'analytics/monthly-statements/', params), allRows(api, 'analytics/monthly-finances/', params)]);
      const metadata = await api.get('analytics/monthly-finances/', { params });
      rowsOf(metadata.data);
      setResult({ statements, finances, analytics: metadata.data.analytics });
    } catch (e) { setError(errorText(e)); } finally { setBusy(false); }
  }
  return <Panel title="Catalogues mensuels"><div className="flex flex-wrap items-end gap-3"><Field label="Mois"><input type="month" className={control} value={month} onChange={e => setMonth(e.target.value)} /></Field><Button disabled={busy} onClick={load}>Consulter les catalogues</Button></div><Feedback error={error} />{result && <><p className="text-xs text-slate-500">Dernière actualisation : {result.analytics?.last_refreshed_at || 'Jamais'} · {result.analytics?.stale ? 'Données à actualiser' : 'À jour'}{result.analytics?.refresh_failed ? ' · Échec du dernier rafraîchissement' : ''}</p><p className="text-sm">Livraisons : {result.statements.length} · Brut : {money(result.finances.reduce((s,r) => s + Number(r.gross_amount), 0))} · Avoirs : {money(result.finances.reduce((s,r) => s + Number(r.credited_amount), 0))} · Net : {money(result.finances.reduce((s,r) => s + Number(r.net_amount), 0))}</p><Paged rows={result.finances}>{rows => <div className="space-y-2 text-sm">{rows.map(row => <p key={row.invoice_id}>{row.closing_month.slice(0,7)} · {row.clinic_name} · {row.number} · Net {money(row.net_amount)}</p>)}</div>}</Paged><details><summary className="cursor-pointer text-sm">Détail des livraisons du catalogue</summary><Paged rows={result.statements}>{rows => <div className="space-y-2 text-sm">{rows.map(row => <p key={row.prescription_id}>{row.patient_ref} · {row.closing_month.slice(0,7)} · {money(row.total_amount)}{row.contested ? ' · Contestée' : ''}{row.excluded ? ' · Exclue' : ''}{row.billed ? ' · Facturée' : ''}</p>)}</div>}</Paged></details></>}</Panel>;
}
