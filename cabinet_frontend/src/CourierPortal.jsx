import { useRef, useState } from 'react';
import api from './api/client';
import { errorText, retryableRequest } from './api/contracts';
import { labelFor } from './api/messages';
import { notify } from './notifications';
import ActionDialog from './ActionDialog';
import { Button, control, Field, Paged, Panel } from './IntegrationUI';

export default function CourierPortal({ orders, refresh }) {
  return <div className="space-y-5"><h1 className="text-2xl font-semibold">Collectes et livraisons</h1>
    <p className="text-sm text-slate-500">Ouvrez le lecteur pour la remise concernée. La collecte, l’arrivée au laboratoire et la livraison sont enregistrées séparément.</p>
    <Paged rows={orders}>{rows => <div className="space-y-5">{rows.map(order => <CourierCase key={order.id} order={order} refresh={refresh} />)}{!rows.length && <p>Aucune mission disponible.</p>}</div>}</Paged>
  </div>;
}

function CourierCase({ order, refresh }) {
  const [open, setOpen] = useState(false);
  const [qr, setQr] = useState(''); const [pin, setPin] = useState(''); const [busy, setBusy] = useState(false);
  const [confirmed, setConfirmed] = useState(null);
  const request = useRef(retryableRequest());
  const action = { ATTENTE_RAMASSAGE: 'pickup', EN_ROUTE_LABO: 'lab-deposit', PRET_EXPEDITION: 'checkout', EN_ROUTE_CABINET: 'confirm-delivery' }[order.status];
  const titles = { pickup: 'Confirmer la collecte', 'lab-deposit': 'Scanner à l’arrivée au laboratoire', checkout: 'Sortir du laboratoire', 'confirm-delivery': 'Confirmer la livraison' };
  const success = { pickup: 'Collecte confirmée. Le dossier est en route vers le laboratoire.', 'lab-deposit': 'Arrivée au laboratoire enregistrée.', checkout: 'Sortie du laboratoire enregistrée.', 'confirm-delivery': 'Livraison confirmée par PIN.' };
  const displayed = confirmed?.source === order.status ? confirmed.order : order;
  const canAct = action && confirmed?.source !== order.status;
  async function submit(event) {
    event.preventDefault(); if (busy || !canAct) return;
    if (action === 'confirm-delivery' ? !/^\d{4}$/.test(pin) : !qr.trim()) {
      notify(action === 'confirm-delivery' ? 'Saisissez le PIN de livraison à quatre chiffres.' : 'Scannez ou collez le contenu du QR du dossier.', 'error');
      return;
    }
    setBusy(true);
    try {
      const response = await request.current(api, `prescriptions/${order.id}/command/`, { action, data: action === 'confirm-delivery' ? { pin } : { qr_token: qr.trim() } });
      setConfirmed({ source: order.status, order: response.data.case || order });
      setQr(''); setPin(''); setOpen(false);
      notify(success[action]);
      try { await refresh(); } catch { notify('Remise enregistrée. Actualisez les commandes pour afficher le nouvel état.', 'error'); }
    } catch (error) { notify(errorText(error), 'error'); }
    finally { setBusy(false); }
  }
  return <Panel title={order.patient_ref}>
    <p className="text-sm">{order.clinic_name} · {order.dentist_name}</p>
    <p className="text-sm text-slate-500">{order.pickup_address} · {order.contact_phone}</p>
    <p className="text-sm text-teal-700">{labelFor(displayed.status)}</p>
    {canAct ? <Button onClick={() => setOpen(true)}>{titles[action]}</Button> : <p className="text-sm text-slate-500">Remise enregistrée. La liste des missions se met à jour automatiquement.</p>}
    <ActionDialog open={open} busy={busy} onClose={() => setOpen(false)} title={`${titles[action] || 'Remise'} — ${order.patient_ref}`}>
      <form onSubmit={submit} noValidate className="space-y-4"><fieldset disabled={busy} className="space-y-4">
        {action === 'confirm-delivery' ? <Field label="PIN réel de livraison (4 chiffres)"><input autoFocus className={control} inputMode="numeric" maxLength={4} value={pin} onChange={event => setPin(event.target.value.replace(/\D/g, ''))} /></Field>
          : <Field label="Contenu du QR signé du dossier"><textarea autoFocus className={control} value={qr} onChange={event => setQr(event.target.value)} /></Field>}
        <p className="text-sm text-slate-500">{action === 'lab-deposit' ? 'Validez ce scan uniquement à l’arrivée au laboratoire : il enregistre le dépôt dans l’historique du dossier.' : 'Cette validation enregistre la remise dans l’historique du dossier.'}</p>
        <Button type="submit">{busy ? 'Validation…' : action === 'lab-deposit' ? 'Valider le QR d’arrivée' : titles[action]}</Button>
      </fieldset></form>
    </ActionDialog>
  </Panel>;
}
