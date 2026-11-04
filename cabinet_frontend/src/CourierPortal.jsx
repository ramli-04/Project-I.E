import { useRef, useState } from 'react';
import api from './api/client';
import { errorText, retryableRequest } from './api/contracts';
import { Button, control, Feedback, Field, Paged, Panel } from './IntegrationUI';

export default function CourierPortal({ orders, refresh }) {
  return <div className="space-y-5"><h1 className="text-2xl font-semibold">Collectes et livraisons</h1><p className="text-sm text-slate-500">Lisez le QR du dossier avec votre lecteur, puis saisissez son contenu. La remise au cabinet nécessite le PIN communiqué par le dentiste.</p><Paged rows={orders}>{rows => <div className="space-y-5">{rows.map(order => <CourierCase key={`${order.id}:${order.status}`} order={order} refresh={refresh} />)}{!rows.length && <p>Aucune mission disponible.</p>}</div>}</Paged></div>;
}
function CourierCase({ order, refresh }) {
  const [qr, setQr] = useState(''); const [pin, setPin] = useState(''); const [busy, setBusy] = useState(false); const [error, setError] = useState(''); const [notice, setNotice] = useState('');
  const request = useRef(retryableRequest());
  const action = { ATTENTE_RAMASSAGE: 'pickup', EN_ROUTE_LABO: 'lab-deposit', PRET_EXPEDITION: 'checkout', EN_ROUTE_CABINET: 'confirm-delivery' }[order.status];
  const label = { pickup: 'Confirmer la collecte', 'lab-deposit': 'Confirmer le dépôt au labo', checkout: 'Sortir du laboratoire', 'confirm-delivery': 'Confirmer la livraison' }[action];
  async function submit(event) {
    event.preventDefault(); if (busy || !action) return;
    setBusy(true); setError(''); setNotice('');
    try { await request.current(api, `prescriptions/${order.id}/command/`, { action, data: action === 'confirm-delivery' ? { pin } : { qr_token: qr.trim() } }); setNotice('Remise enregistrée.'); await refresh(); }
    catch (e) { setError(errorText(e)); } finally { setBusy(false); }
  }
  return <Panel title={order.patient_ref}><p className="text-sm">{order.clinic_name} · {order.dentist_name}</p><p className="text-sm text-slate-500">{order.pickup_address} · {order.contact_phone}</p><p className="text-xs text-teal-700">{order.status}</p><Feedback error={error} notice={notice} /><form onSubmit={submit} className="space-y-3"><fieldset disabled={busy} className="space-y-3">{action === 'confirm-delivery' ? <Field label="PIN réel de livraison (4 chiffres)"><input required className={control} inputMode="numeric" pattern="[0-9]{4}" maxLength={4} value={pin} onChange={e => setPin(e.target.value.replace(/\D/g, ''))} /></Field> : <Field label="Contenu du QR signé du dossier"><textarea required className={control} value={qr} onChange={e => setQr(e.target.value)} /></Field>}<Button type="submit" disabled={!action || busy}>{busy ? 'Validation…' : label}</Button></fieldset></form></Panel>;
}
