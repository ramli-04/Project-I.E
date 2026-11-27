import { useEffect, useState } from 'react';
import api from './api/client';
import { allRows } from './api/contracts';
import { Button, control, Field } from './IntegrationUI';

// Lot creation where the work happens: the current case is preselected and the
// server rule (a lot before manufacturing) stays the authority.
export default function LotPanel({ order, lots, busy, createLot }) {
  const linked = lots.filter(lot => (lot.prescriptions || []).map(String).includes(String(order.id)));
  const [machines, setMachines] = useState([]); const [inventory, setInventory] = useState([]);
  const [code, setCode] = useState(`LOT-${order.patient_ref}`); const [machine, setMachine] = useState(''); const [item, setItem] = useState('');
  useEffect(() => {
    if (linked.length) return undefined;
    const abort = new AbortController();
    Promise.all([allRows(api, 'machines/', {}, abort.signal), allRows(api, 'inventory/', {}, abort.signal)])
      .then(([m, i]) => { setMachines(m); setInventory(i); }).catch(() => {});
    return () => abort.abort();
  }, [linked.length]);
  if (linked.length) return <p className="rounded-xl border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-900">Lot lié : {linked.map(lot => lot.code).join(', ')}</p>;
  return <section aria-label="Lot de production" className="space-y-3 rounded-xl border border-amber-200 bg-amber-50/60 p-4">
    <p className="text-sm">Un lot de production est requis avant la fabrication. Il est créé pour ce dossier.</p>
    <div className="grid gap-3 sm:grid-cols-3">
      <Field label="Code du lot"><input className={control} maxLength={80} value={code} onChange={e => setCode(e.target.value)} /></Field>
      <Field label="Machine du lot"><select className={control} value={machine} onChange={e => setMachine(e.target.value)}><option value="">Sans machine</option>{machines.map(m => <option key={m.id} value={m.id}>{m.name}</option>)}</select></Field>
      <Field label="Consommable"><select className={control} value={item} onChange={e => setItem(e.target.value)}><option value="">Sans consommable</option>{inventory.map(i => <option key={i.id} value={i.id}>{i.material_name}</option>)}</select></Field>
    </div>
    <Button disabled={busy || !code.trim()} onClick={() => createLot({ code: code.trim(), machine: machine ? Number(machine) : null, inventory_item: item ? Number(item) : null, prescriptions: [order.id] })}>Créer et lier le lot</Button>
  </section>;
}
