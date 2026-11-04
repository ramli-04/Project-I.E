import { useEffect, useState } from 'react';
import api from './api/client';
import { allRows, errorText } from './api/contracts';
import { Button, control, Feedback, Field, Paged, Panel } from './IntegrationUI';
export default function OperationsDashboard() {
  const [events, setEvents] = useState([]); const [deliveries, setDeliveries] = useState([]); const [reload, setReload] = useState(0); const [error, setError] = useState(''); const [busy, setBusy] = useState(false);
  useEffect(() => {
    const abort = new AbortController();
    Promise.all([allRows(api, 'operations/outbox/', {}, abort.signal), allRows(api, 'operations/deliveries/', {}, abort.signal)])
      .then(([outbox, messages]) => { setEvents(outbox); setDeliveries(messages); }).catch(e => { if (!abort.signal.aborted) setError(errorText(e)); });
    return () => abort.abort();
  }, [reload]);
  async function act(path, payload) { if (busy) return; setBusy(true); setError(''); try { await api.post(path, payload); setReload(v => v + 1); } catch (e) { setError(errorText(e)); } finally { setBusy(false); } }
  return <div className="space-y-5"><h1 className="text-2xl font-semibold">Suivi des opérations</h1><p className="text-sm text-slate-500">Les tâches sont traitées par les workers. La réconciliation doit refléter le résultat vérifié auprès du fournisseur.</p><Feedback error={error} /><Button disabled={busy} onClick={() => { setError(''); setReload(v => v + 1); }}>Actualiser</Button><Panel title="Événements persistants"><Paged rows={events}>{rows => <div className="space-y-3">{rows.map(e => <div key={e.id} className="space-y-2 rounded-xl border border-slate-200/80 p-3 text-sm"><p>{e.event_type} · {e.processed_at ? 'Terminé' : e.failed_at ? 'Échec' : 'En attente'} · {e.attempts} essai(s)</p><p className="break-words text-xs text-slate-500">{e.last_error}</p>{!e.processed_at && <Button disabled={busy} onClick={() => act(`operations/outbox/${e.id}/retry/`, {})}>Planifier une nouvelle tentative</Button>}</div>)}</div>}</Paged></Panel><Panel title="Livraisons de messages"><Paged rows={deliveries}>{rows => <div className="space-y-3">{rows.map(d => <Delivery key={d.id} delivery={d} busy={busy} act={act} />)}</div>}</Paged></Panel></div>;
}
function Delivery({ delivery: d, busy, act }) {
  const [notes, setNotes] = useState('');
  return <div className="space-y-3 rounded-xl border border-slate-200/80 p-3 text-sm"><p>{d.channel} · {d.destination} · {d.status}</p><p className="text-xs text-slate-500">{d.last_error}</p>{['UNKNOWN','SENDING'].includes(d.status) && <><Field label="Preuve du résultat fournisseur"><textarea className={control} value={notes} onChange={e => setNotes(e.target.value)} /></Field><div className="flex gap-3"><Button disabled={busy || !notes.trim()} onClick={() => act(`operations/deliveries/${d.id}/reconcile/`, { sent: true, notes })}>Confirmer l’envoi effectif</Button><Button disabled={busy || !notes.trim()} onClick={() => act(`operations/deliveries/${d.id}/reconcile/`, { sent: false, notes })}>Confirmer l’absence d’envoi</Button></div></>}</div>;
}
