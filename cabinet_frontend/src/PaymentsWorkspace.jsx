import { useEffect, useRef, useState } from 'react';
import api from './api/client';
import ActionDialog from './ActionDialog';
import { Button, control, Feedback, Field, Paged, Panel } from './IntegrationUI';
import { allRows, errorText, money, retryableRequest } from './api/contracts';
import { labDate } from './planningTime';
import { agingLabel, allocateOldest, allocationTotal, cents, decimal, paymentMethodLabel } from './paymentHelpers';

const day = value => value ? new Date(`${value}T12:00:00Z`).toLocaleDateString('fr-FR', { timeZone: 'Africa/Casablanca' }) : '—';
const bucketKeys = ['0_30', '31_60', '61_90', '90_plus'];

export default function PaymentsWorkspace({ invoices, clinics, onChanged }) {
  const [data, setData] = useState(null); const [error, setError] = useState('');
  const [reload, setReload] = useState(0); const [record, setRecord] = useState(false); const [reverse, setReverse] = useState(null);
  const opener = useRef(null);
  useEffect(() => {
    const abort = new AbortController();
    Promise.all([allRows(api, 'billing/payments/', {}, abort.signal), allRows(api, 'billing/receivables/', {}, abort.signal)])
      .then(([payments, receivables]) => { setData({ payments, receivables }); setError(''); })
      .catch(cause => { if (!abort.signal.aborted) setError(errorText(cause)); });
    return () => abort.abort();
  }, [invoices, reload]);
  async function changed() { await onChanged(); setReload(value => value + 1); }
  return <><Feedback error={error} /><Panel title="Encaissements"><div className="flex flex-wrap gap-3">
    <Button onClick={event => { opener.current = event.currentTarget; setRecord(true); }}>Enregistrer un encaissement</Button>
    <Button onClick={() => setReload(value => value + 1)}>Actualiser les encaissements</Button></div>
    {!data ? <p>Chargement des encaissements…</p> : <Paged rows={data.payments}>{rows => <div className="space-y-3">{rows.map(payment => <article key={payment.id} className="space-y-2 rounded-xl border border-slate-200 p-3">
      <p>{clinics.find(clinic => clinic.id === payment.clinic)?.name || 'Cabinet'} · {paymentMethodLabel(payment.method)} · {money(payment.amount)}</p>
      <p className="break-words text-sm text-slate-600">Reçu le {day(payment.received_on)}{payment.reference && ` · Réf. ${payment.reference}`}{payment.due_on && ` · Échéance ${day(payment.due_on)}`}</p>
      {payment.reversal ? <p className="text-sm text-amber-800">{payment.reversal.reason === 'IMPAYE' ? 'Signalé impayé' : 'Saisie annulée'} · preuve conservée</p>
        : <Button onClick={event => { opener.current = event.currentTarget; setReverse(payment); }}>{['CHEQUE', 'LCN'].includes(payment.method) ? 'Marquer comme impayé / Annuler la saisie' : 'Annuler la saisie'}</Button>}
    </article>)}{!rows.length && <p>Aucun encaissement enregistré.</p>}</div>}</Paged>}
  </Panel><Panel title="Impayés"><p className="text-sm text-slate-600">Ancienneté depuis l’échéance. Les trop-perçus restent séparés des montants dus ; aucune compensation automatique.</p>
    {!data ? <p>Chargement des créances…</p> : <div role="region" aria-label="Ancienneté des créances" tabIndex={0} className="max-w-full overflow-x-auto"><table className="w-full min-w-[760px] text-left text-sm"><thead><tr>{['Cabinet', 'Délai', 'Total dû', 'Non échu', ...bucketKeys.map(agingLabel), 'Trop-perçu à régulariser'].map(label => <th key={label} scope="col" className="p-2">{label}</th>)}</tr></thead>
      <tbody>{data.receivables.map(row => <tr key={row.clinic} className="border-t border-slate-200"><th scope="row" className="p-2">{clinics.find(clinic => clinic.id === row.clinic)?.name || 'Cabinet'}</th><td className="p-2">{row.terms_days} jours</td><td className="p-2">{money(row.total_due)}</td><td className="p-2">{money(row.not_due)}</td>{bucketKeys.map(key => <td key={key} className="p-2">{money(row.buckets[key])}</td>)}<td className="p-2">{money(row.overpaid_amount)}</td></tr>)}</tbody></table>{!data.receivables.length && <p>Aucune créance.</p>}</div>}
  </Panel>{record && <PaymentDialog invoices={invoices} clinics={clinics} onSaved={changed} onClose={() => setRecord(false)} returnFocus={opener} />}
    {reverse && <ReversalDialog payment={reverse} onSaved={changed} onClose={() => setReverse(null)} returnFocus={opener} />}</>;
}

function PaymentDialog({ invoices, clinics, onSaved, onClose, returnFocus }) {
  const [clinic, setClinic] = useState(''); const [method, setMethod] = useState('CHEQUE'); const [amount, setAmount] = useState('');
  const [received, setReceived] = useState(() => labDate(new Date())); const [due, setDue] = useState('');
  const [reference, setReference] = useState(''); const [bank, setBank] = useState(''); const [notes, setNotes] = useState('');
  const [allocations, setAllocations] = useState({}); const [busy, setBusy] = useState(false); const [saved, setSaved] = useState(false);
  const [error, setError] = useState(''); const [notice, setNotice] = useState('');
  const [request] = useState(() => retryableRequest({ idempotencyKey: crypto.randomUUID() }));
  const available = invoices.filter(invoice => String(invoice.clinic) === clinic && invoice.balance != null && !String(invoice.balance).startsWith('-') && cents(invoice.balance) > 0n);
  function prefill(value, clinicId) {
    try { setAllocations(allocateOldest(value, invoices.filter(invoice => String(invoice.clinic) === clinicId && invoice.balance != null))); }
    catch { setAllocations({}); }
  }
  let total = null;
  try { total = decimal(allocationTotal(allocations)); } catch { /* The submit validation explains an incomplete amount. */ }
  async function refresh() {
    try { await onSaved(); onClose(); } catch (cause) { setError(errorText(cause)); }
  }
  async function submit(event) {
    event.preventDefault(); if (busy || saved) return;
    setBusy(true); setError('');
    try {
      if (cents(amount) <= 0n || allocationTotal(allocations) !== cents(amount)) throw new Error('Le total réparti doit correspondre exactement au montant encaissé.');
      const allocationRows = Object.entries(allocations).filter(([, value]) => value !== '' && cents(value) > 0n)
        .map(([invoice, value]) => ({ invoice, amount: decimal(cents(value)) })).sort((a, b) => a.invoice.localeCompare(b.invoice));
      await request(api, 'billing/payments/', { clinic: Number(clinic), method, amount: decimal(cents(amount)), received_on: received,
        due_on: ['CHEQUE', 'LCN'].includes(method) && due ? due : null, reference: method === 'ESPECES' ? '' : reference,
        bank: method === 'ESPECES' ? '' : bank, notes, allocations: allocationRows });
      setSaved(true); setNotice('Encaissement enregistré.'); await refresh();
    } catch (cause) { setError(errorText(cause)); }
    finally { setBusy(false); }
  }
  return <ActionDialog open title="Enregistrer un encaissement" busy={busy} onClose={onClose} returnFocus={returnFocus}><Feedback error={error} notice={notice} />
    {saved ? <div className="space-y-3"><p>Encaissement enregistré. Actualisez les soldes avant une nouvelle opération.</p><Button onClick={refresh}>Actualiser les soldes et fermer</Button></div>
      : <form onSubmit={submit} className="space-y-4"><fieldset disabled={busy} className="space-y-4"><div className="grid gap-4 sm:grid-cols-2">
        <Field label="Cabinet payeur"><select className={control} required value={clinic} onChange={event => { setClinic(event.target.value); prefill(amount, event.target.value); }}><option value="">Choisir</option>{clinics.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}</select></Field>
        <Field label="Moyen de paiement"><select className={control} value={method} onChange={event => setMethod(event.target.value)}>{['CHEQUE', 'LCN', 'VIREMENT', 'ESPECES'].map(value => <option key={value} value={value}>{paymentMethodLabel(value)}</option>)}</select></Field>
        <Field label="Montant encaissé (MAD)"><input className={control} type="number" min="0.01" step="0.01" required value={amount} onChange={event => { setAmount(event.target.value); prefill(event.target.value, clinic); }} /></Field>
        <Field label="Date de réception du paiement"><input className={control} type="date" required value={received} onChange={event => setReceived(event.target.value)} /></Field>
        {method !== 'ESPECES' && <><Field label="Référence du paiement"><input className={control} required maxLength={60} value={reference} onChange={event => setReference(event.target.value)} /></Field><Field label="Banque"><input className={control} required maxLength={80} value={bank} onChange={event => setBank(event.target.value)} /></Field></>}
        {['CHEQUE', 'LCN'].includes(method) && <Field label={method === 'LCN' ? 'Échéance LCN (obligatoire)' : 'Échéance du chèque (facultative)'}><input className={control} type="date" required={method === 'LCN'} value={due} onChange={event => setDue(event.target.value)} /></Field>}
      </div>{method === 'ESPECES' && <p className="text-sm text-slate-600">Conservez un reçu signé.</p>}
      <p className="text-sm text-slate-600">Délai du cabinet : {clinics.find(item => String(item.id) === clinic)?.payment_terms_days ?? 60} jours. Répartition préremplie par échéance la plus ancienne ; vous pouvez la modifier.</p>
      <div className="space-y-3">{available.map(invoice => <div key={invoice.id} className="space-y-2 rounded-xl border border-slate-200 p-3"><p className="break-words text-sm">{invoice.number} · échéance {day(invoice.due_date)} · reste {money(invoice.balance)}</p><Field label={`Affectation à ${invoice.number} (MAD)`}><input className={control} type="number" min="0" max={invoice.balance} step="0.01" value={allocations[invoice.id] || ''} onChange={event => setAllocations(previous => ({ ...previous, [invoice.id]: event.target.value }))} /></Field></div>)}{clinic && !available.length && <p>Aucune facture avec un solde positif pour ce cabinet.</p>}</div>
      <p role="status">Total réparti : {total == null ? 'Montant à vérifier' : money(total)}. Aucun montant ne peut rester sans affectation.</p>
      <Field label="Notes de l’encaissement (facultatives)"><textarea className={control} value={notes} onChange={event => setNotes(event.target.value)} /></Field>
      <Button type="submit" disabled={!clinic || !available.length}>Enregistrer le paiement</Button></fieldset></form>}
  </ActionDialog>;
}

function ReversalDialog({ payment, onSaved, onClose, returnFocus }) {
  const [reason, setReason] = useState(['CHEQUE', 'LCN'].includes(payment.method) ? 'IMPAYE' : 'ANNULE');
  const [notes, setNotes] = useState(''); const [busy, setBusy] = useState(false); const [saved, setSaved] = useState(false);
  const [error, setError] = useState(''); const [notice, setNotice] = useState('');
  async function refresh() { try { await onSaved(); onClose(); } catch (cause) { setError(errorText(cause)); } }
  async function submit(event) {
    event.preventDefault(); if (busy || saved) return;
    setBusy(true); setError('');
    try { await api.post(`billing/payments/${payment.id}/reverse/`, { reason, notes }); setSaved(true); setNotice('Annulation enregistrée ; les soldes ont été rouverts.'); await refresh(); }
    catch (cause) { setError(errorText(cause)); } finally { setBusy(false); }
  }
  return <ActionDialog open title="Annuler ou signaler un impayé" busy={busy} onClose={onClose} returnFocus={returnFocus}><Feedback error={error} notice={notice} />
    {saved ? <div className="space-y-3"><p>Annulation enregistrée. Actualisez les soldes.</p><Button onClick={refresh}>Actualiser les soldes et fermer</Button></div>
      : <form onSubmit={submit} className="space-y-4"><p>{paymentMethodLabel(payment.method)} · {money(payment.amount)} · {payment.reference}</p><p>Cette action conserve la preuve du paiement et ajoute une annulation. Les factures concernées redeviennent dues.</p>
        <fieldset disabled={busy} className="space-y-4"><Field label="Motif de l’annulation"><select className={control} value={reason} onChange={event => setReason(event.target.value)}>{['CHEQUE', 'LCN'].includes(payment.method) && <option value="IMPAYE">Chèque / LCN impayé</option>}<option value="ANNULE">Saisie annulée</option></select></Field>
        <Field label="Précision (facultative)"><textarea className={control} value={notes} onChange={event => setNotes(event.target.value)} /></Field>
        <div className="flex flex-wrap gap-3"><Button type="submit">Confirmer l’annulation du paiement</Button><Button onClick={onClose}>Conserver le paiement</Button></div></fieldset></form>}
  </ActionDialog>;
}
