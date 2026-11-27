import PaymentsWorkspace from './PaymentsWorkspace';
import { paymentStatusLabel } from './paymentHelpers';
import { useEffect, useRef, useState } from 'react';
import api from './api/client';
import { labelFor } from './api/messages';
import { allRows, download, errorText, money, retryableRequest, rowsOf, sumAmounts } from './api/contracts';
import { Button, control, Feedback, Field, Paged, Panel } from './IntegrationUI';
import CaseWorkspace from './CaseWorkspace';
import { serviceLabels } from './workQueueHelpers';
import { useTestCaseFilter } from './TestCaseToggle';
import { deliveredRows, currentLabMonth } from './financeHelpers';

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
  const defaultPeriod = data?.periods.find(p => p.month.startsWith(currentLabMonth()))?.id || '';
  const activePeriod = periodId || defaultPeriod;
  const period = data?.periods.find(p => p.id === activePeriod);
  const lines = data?.lines.filter(line => line.period === activePeriod) || [];
  const included = lines.filter(line => !line.contested && !line.excluded);
  const total = sumAmounts(included.flatMap(line => [line.base_amount, line.express_surcharge]));
  return <div className="space-y-5"><h1 className="text-2xl font-semibold">Situations mensuelles et facturation</h1><p className="text-sm text-slate-500">Les relevés regroupent les dossiers livrés dans le mois, selon le calendrier Africa/Casablanca. Les périodes se clôturent après la fin du mois.</p><Feedback error={error} notice={notice} /><Button disabled={busy} onClick={() => { setError(''); setReload(v => v + 1); }}>Actualiser</Button>
    {!data ? <p>Chargement de la comptabilité…</p> : <>
      <DeliveredOrders data={data} />
      <PaymentsWorkspace invoices={data.invoices} clinics={data.clinics} onChanged={async () => setData(await fetchData())} />
      <Panel title="Relevés de livraison"><Field label="Cabinet et mois de livraison"><select className={control} value={activePeriod} onChange={e => { setPeriodId(e.target.value); setCloseReview(false); }}><option value="">Choisir un relevé</option>{data.periods.map(p => <option key={p.id} value={p.id}>{p.month.slice(0,7)} · {data.clinics.find(c => c.id === p.clinic)?.name || p.clinic} · {p.closed_at ? 'Clôturé' : 'Ouvert'}</option>)}</select></Field>
        {period && <><p>{included.length} dossier(s) inclus · {money(total)} · {period.closed_at ? 'Clôturé' : 'Ouvert'}</p><Paged rows={lines}>{rows => <div className="space-y-3">{rows.map(line => <LineAdjustment key={`${line.id}:${line.contested}:${line.excluded}`} line={line} closed={Boolean(period.closed_at)} busy={busy} mutate={mutate} />)}</div>}</Paged>
          {!period.closed_at && <>{!closeReview ? <Button disabled={busy || !included.length} onClick={() => setCloseReview(true)}>Vérifier la clôture</Button> : <div className="space-y-3 rounded-xl border border-amber-400/30 p-4"><p>Émettre la facture définitive pour {included.length} dossiers, soit {money(total)} ? {lines.length - included.length} ligne(s) contestée(s) ou exclue(s) resteront hors facture.</p><Button disabled={busy} onClick={() => mutate(async () => { await api.post(`billing/periods/${activePeriod}/close/`, {}); setCloseReview(false); }, 'Période clôturée. La facture PDF sera disponible après traitement.')}>Confirmer la clôture et émettre la facture</Button><Button onClick={() => setCloseReview(false)}>Annuler</Button></div>}</>}
        </>}
        {!period && <p className="text-sm text-slate-500">Aucun relevé pour ce mois : un relevé s’ouvre automatiquement à la première livraison d’un cabinet.</p>}
      </Panel>
      <Panel title="Factures et avoirs"><Paged rows={data.invoices}>{rows => <div className="space-y-4">{rows.map(invoice => <InvoiceCard key={invoice.id} invoice={invoice} credits={data.credits.filter(c => c.invoice === invoice.id)} busy={busy} mutate={mutate} />)}{!rows.length && <p className="text-sm text-slate-500">Aucune facture pour le moment : une facture est émise à la clôture d’un relevé, après la fin du mois de livraison.</p>}</div>}</Paged></Panel>
      <Panel title="Contestations"><Paged rows={data.disputes}>{rows => <div className="space-y-4">{rows.map(d => <DisputeCard key={`${d.id}:${d.status}`} dispute={d} busy={busy} mutate={mutate} />)}{!rows.length && <p className="text-sm text-slate-500">Aucune contestation : un dentiste peut contester une ligne depuis son dossier.</p>}</div>}</Paged></Panel>
    </>}
    <CatalogFinance />
  </div>;
}
function LineAdjustment({ line, closed, busy, mutate }) {
  const [contested, setContested] = useState(line.contested); const [excluded, setExcluded] = useState(line.excluded); const [reason, setReason] = useState(line.dispute_reason || '');
  const [open, setOpen] = useState(false);
  const flags = [line.contested && 'Contestée', line.excluded && 'Exclue'].filter(Boolean).join(' · ');
  if (!open) return <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-slate-200/80 px-4 py-3 text-sm"><span>{line.snapshot?.patient_ref || line.prescription} · {money(sumAmounts([line.base_amount, line.express_surcharge]))}{flags && ` · ${flags}`}</span><span className="text-xs text-slate-500">Livraison : {line.snapshot?.delivered_at ? new Date(line.snapshot.delivered_at).toLocaleString('fr-FR', { timeZone: 'Africa/Casablanca' }) : 'Non renseignée'}</span>{!closed && <Button disabled={busy} onClick={() => setOpen(true)}>Ajuster</Button>}</div>;
  return <div className="space-y-3 rounded-xl border border-slate-200/80 p-4"><p className="text-sm">{line.snapshot?.patient_ref || line.prescription} · {money(sumAmounts([line.base_amount, line.express_surcharge]))}</p><p className="text-xs text-slate-500">Livraison : {line.snapshot?.delivered_at ? new Date(line.snapshot.delivered_at).toLocaleString('fr-FR', { timeZone: 'Africa/Casablanca' }) : 'Non renseignée'}</p><fieldset disabled={closed || busy} className="space-y-3"><div className="flex gap-5 text-sm"><label className="flex gap-2"><input type="checkbox" checked={contested} onChange={e => setContested(e.target.checked)} />Contestée</label><label className="flex gap-2"><input type="checkbox" checked={excluded} onChange={e => setExcluded(e.target.checked)} />Exclue</label></div><Field label="Motif de l’ajustement"><input className={control} value={reason} onChange={e => setReason(e.target.value)} /></Field>{!closed && <div className="flex flex-wrap gap-3"><Button disabled={!reason.trim() || busy} onClick={() => mutate(() => api.post(`billing/statement-lines/${line.id}/adjust/`, { contested, excluded, reason }))}>Enregistrer l’ajustement</Button><Button disabled={busy} onClick={() => setOpen(false)}>Fermer</Button></div>}</fieldset></div>;
}
function InvoiceCard({ invoice, credits, busy, mutate }) {
  const [caseId, setCaseId] = useState(''); const [amount, setAmount] = useState(''); const [reason, setReason] = useState(''); const request = useRef(retryableRequest());
  const selected = invoice.lines.find(line => line.case_id === caseId);
  const available = selected ? sumAmounts([selected.total_amount, ...credits.filter(c => c.prescription === caseId).map(c => '-' + c.amount)]) : '0.00';
  return <div className="space-y-3 rounded-xl border border-slate-200/80 p-4"><p>{invoice.number} · {invoice.clinic_name} · {money(invoice.total_amount)}</p><p className={`text-sm ${invoice.payment_status === 'TROP_PERCU' ? 'text-amber-800' : invoice.payment_status === 'PAYEE' ? 'text-emerald-800' : 'text-slate-700'}`}>{paymentStatusLabel(invoice.payment_status)}</p>
    {invoice.balance != null && <><p>Reste à payer : {money(invoice.balance)} · Reçu : {money(invoice.paid_amount)}</p><p className="text-sm text-slate-600">Échéance : {new Date(`${invoice.due_date}T12:00:00Z`).toLocaleDateString('fr-FR', { timeZone: 'Africa/Casablanca' })} · délai {invoice.terms_days} jours</p>{Number(invoice.balance) > 0 && invoice.days_overdue > 0 && <p className="text-sm text-red-800">En retard de {invoice.days_overdue} jours</p>}{invoice.payment_status === 'TROP_PERCU' && <p className="text-sm text-amber-800">Montant à régulariser séparément ; aucun remboursement ou report automatique.</p>}</>}
    <Button disabled={busy} onClick={() => mutate(() => download(api, `billing/invoices/${invoice.id}/pdf/`, `${invoice.number}.pdf`), 'Facture téléchargée.')}>Télécharger le PDF</Button><details><summary className="cursor-pointer text-sm text-teal-700">Émettre un avoir sur une ligne</summary><form className="mt-3 space-y-3" onSubmit={e => { e.preventDefault(); mutate(async () => { await request.current(api, `billing/invoices/${invoice.id}/credit/`, { prescription: caseId, amount, reason }); setAmount(''); setReason(''); }, 'Avoir émis. Son PDF sera disponible après traitement.'); }}><fieldset disabled={busy} className="space-y-3"><Field label="Dossier facturé"><select required className={control} value={caseId} onChange={e => setCaseId(e.target.value)}><option value="">Choisir</option>{invoice.lines.map(line => <option key={line.case_id} value={line.case_id}>{line.patient_ref || line.case_id} · {money(line.total_amount)}</option>)}</select></Field><p className="text-xs text-slate-500">Montant restant ajustable : {money(available)}</p><Field label="Montant de l’avoir (MAD)"><input className={control} required type="number" min="0.01" max={Number(available) > 0 ? available : '0.00'} step="0.01" value={amount} onChange={e => setAmount(e.target.value)} /></Field><Field label="Motif"><input className={control} required value={reason} onChange={e => setReason(e.target.value)} /></Field><Button type="submit" disabled={!selected || available <= 0}>Émettre l’avoir</Button></fieldset></form></details>{credits.map(c => <div key={c.id} className="text-sm text-amber-800">Avoir · {money(c.amount)} · {c.reason} <Button disabled={busy} onClick={() => mutate(() => download(api, `billing/credit-notes/${c.id}/pdf/`, `avoir-${c.id}.pdf`), 'Avoir téléchargé.')}>PDF</Button></div>)}</div>;
}
function DisputeCard({ dispute, busy, mutate }) {
  const [notes, setNotes] = useState(''); const [amount, setAmount] = useState('');
  return <div className="space-y-3 rounded-xl border border-slate-200/80 p-4"><p className="text-sm">Dossier {dispute.prescription} · {labelFor(dispute.status)}</p><p className="text-sm text-slate-500">{dispute.reason}</p>{dispute.status === 'OPEN' && <fieldset disabled={busy} className="space-y-3"><Field label="Justification de la décision"><textarea className={control} value={notes} onChange={e => setNotes(e.target.value)} /></Field>{dispute.invoice && <Field label="Montant de l’avoir si accepté (MAD)"><input className={control} type="number" min="0.01" step="0.01" value={amount} onChange={e => setAmount(e.target.value)} /></Field>}<div className="flex gap-3">{[['ACCEPTED','Accepter'],['REJECTED','Rejeter']].map(([decision,label]) => <Button key={decision} disabled={!notes.trim() || (decision === 'ACCEPTED' && dispute.invoice && !(Number(amount) > 0))} onClick={() => mutate(() => api.post(`billing/disputes/${dispute.id}/resolve/`, { decision, notes, ...(dispute.invoice ? { amount } : {}) }))}>{label}</Button>)}</div></fieldset>}</div>;
}
function DeliveredOrders({ data }) {
  const [month, setMonth] = useState(currentLabMonth()); const [clinic, setClinic] = useState('');
  const [selected, setSelected] = useState(null); const [error, setError] = useState(''); const opener = useRef(null);
  const all = deliveredRows(data).filter(row => row.month === month && (!clinic || String(row.clinicId) === clinic));
  const { visible, toggle } = useTestCaseFilter(all);
  const total = sumAmounts(visible.filter(row => !row.excluded).map(row => row.amount));
  async function open(row, event) {
    opener.current = event.currentTarget; setError('');
    try { setSelected((await api.get(`prescriptions/${row.caseId}/`)).data); } catch (e) { setError(errorText(e)); }
  }
  return <Panel title="Commandes livrées"><div className="flex flex-wrap items-end gap-3"><Field label="Mois de livraison"><input type="month" className={control} value={month} onChange={e => setMonth(e.target.value)} /></Field><Field label="Cabinet"><select className={control} value={clinic} onChange={e => setClinic(e.target.value)}><option value="">Tous les cabinets</option>{data.clinics.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}</select></Field>{toggle}</div><Feedback error={error} />
    {!visible.length ? <p className="text-sm text-slate-500">Aucune commande livrée sur cette période. Les dossiers apparaissent ici dès la confirmation de livraison.</p> : <div className="overflow-x-auto"><table className="w-full min-w-[720px] text-left text-sm"><caption className="sr-only">Commandes livrées du mois</caption><thead><tr className="text-xs text-slate-500"><th className="p-2">Réf. patient</th><th className="p-2">Cabinet</th><th className="p-2">Livraison</th><th className="p-2">Travail</th><th className="p-2">Service</th><th className="p-2 text-right">Montant</th><th className="p-2">Statut</th></tr></thead>
      <tbody>{visible.map(row => <tr key={row.id} className="border-t border-slate-200 align-top"><td className="p-2"><button className="text-teal-800 underline" onClick={event => open(row, event)}>{row.patientRef}</button></td><td className="p-2">{row.clinicName}</td><td className="p-2">{row.deliveredLabel}</td><td className="p-2">{row.work}</td><td className="p-2">{serviceLabels[row.service] || row.service}</td><td className="p-2 text-right">{money(row.amount)}</td><td className="p-2">{row.statusLabel}</td></tr>)}</tbody>
      <tfoot><tr className="border-t-2 border-slate-300 font-semibold"><td className="p-2" colSpan={5}>Total ({visible.filter(row => !row.excluded).length} dossier(s), lignes exclues non comptées)</td><td className="p-2 text-right">{money(total)}</td><td /></tr></tfoot></table></div>}
    {selected && <CaseWorkspace key={selected.id} order={selected} returnFocus={opener} onClose={() => setSelected(null)} />}
  </Panel>;
}
function CatalogFinance() {
  const [month, setMonth] = useState(currentLabMonth()); const [result, setResult] = useState(null); const [error, setError] = useState(''); const [busy, setBusy] = useState(false);
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
  return <Panel title="Catalogues mensuels"><p className="text-sm text-slate-500">Synthèse analytique des factures émises (brut, avoirs, net) ; les montants apparaissent après la clôture d’un relevé.</p><div className="flex flex-wrap items-end gap-3"><Field label="Mois"><input type="month" className={control} value={month} onChange={e => setMonth(e.target.value)} /></Field><Button disabled={busy} onClick={load}>Consulter les catalogues</Button></div><Feedback error={error} />{result && <><p className="text-xs text-slate-500">Dernière actualisation : {result.analytics?.last_refreshed_at || 'Jamais'} · {result.analytics?.stale ? 'Données à actualiser' : 'À jour'}{result.analytics?.refresh_failed ? ' · Échec du dernier rafraîchissement' : ''}</p><p className="text-sm">Livraisons : {result.statements.length} · Brut : {money(sumAmounts(result.finances.map(row => row.gross_amount)))} · Avoirs : {money(sumAmounts(result.finances.map(row => row.credited_amount)))} · Net : {money(sumAmounts(result.finances.map(row => row.net_amount)))}</p><Paged rows={result.finances}>{rows => <div className="space-y-2 text-sm">{rows.map(row => <p key={row.invoice_id}>{row.closing_month.slice(0,7)} · {row.clinic_name} · {row.number} · Net {money(row.net_amount)}</p>)}</div>}</Paged><details><summary className="cursor-pointer text-sm">Détail des livraisons du catalogue</summary><Paged rows={result.statements}>{rows => <div className="space-y-2 text-sm">{rows.map(row => <p key={row.prescription_id}>{row.patient_ref} · {row.closing_month.slice(0,7)} · {money(row.total_amount)}{row.contested ? ' · Contestée' : ''}{row.excluded ? ' · Exclue' : ''}{row.billed ? ' · Facturée' : ''}</p>)}</div>}</Paged></details></>}</Panel>;
}
