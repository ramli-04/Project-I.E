import { useEffect, useRef, useState } from 'react';
import api from './api/client';
import { acceptsQuantity, allRows, errorText, money, quantityText, workstation } from './api/contracts';
import { Button, control, Feedback, Field, Paged, Panel } from './IntegrationUI';
import { LaboratoryResource } from './LabBusinessConfiguration';

export default function InventoryWorkspace({ orders }) {
  const [active, setActive] = useState('stock');
  const tabs = [['personnel', 'Personnel'], ['materials', 'Matériaux'], ['stock', 'Stock']];
  return <div className="space-y-5"><div><span className="section-kicker">RESSOURCES DU LABORATOIRE</span><h1 className="mt-2 text-2xl font-semibold">Stocks et lots de production</h1><p className="mt-2 text-sm text-slate-500">Votre équipe, vos matériaux et les stocks nécessaires à la fabrication des prothèses dentaires.</p></div>
    <div role="tablist" aria-label="Ressources du laboratoire" className="resource-tabs">{tabs.map(([key,label],index) => <button key={key} role="tab" id={`inventory-tab-${key}`} aria-controls={key === 'stock' ? 'inventory-stock-panel' : `config-panel-inventory-${key}`} aria-selected={active === key} tabIndex={active === key ? 0 : -1} onClick={() => setActive(key)} onKeyDown={event => {
      if (!['ArrowRight','ArrowLeft','Home','End'].includes(event.key)) return;
      event.preventDefault(); const next = event.key === 'Home' ? 0 : event.key === 'End' ? tabs.length - 1 : (index + (event.key === 'ArrowRight' ? 1 : -1) + tabs.length) % tabs.length;
      setActive(tabs[next][0]); document.getElementById(`inventory-tab-${tabs[next][0]}`)?.focus();
    }}>{label}</button>)}</div>
    {active === 'stock' ? <div id="inventory-stock-panel" role="tabpanel" aria-labelledby="inventory-tab-stock" className="page-enter"><StockWorkspace orders={orders} /></div> : <LaboratoryResource key={active} resource={active} labelledBy={`inventory-tab-${active}`} />}
  </div>;
}

function StockWorkspace({ orders }) {
  const [data, setData] = useState(null); const [error, setError] = useState(''); const [notice, setNotice] = useState(''); const [busy, setBusy] = useState(false);
  const [item, setItem] = useState(''); const [type, setType] = useState('RESTOCK'); const [quantity, setQuantity] = useState(''); const [caseId, setCaseId] = useState(''); const [lot, setLot] = useState(''); const [source, setSource] = useState(''); const [notes, setNotes] = useState('');
  const [code, setCode] = useState(''); const [machine, setMachine] = useState(''); const [lotItem, setLotItem] = useState(''); const [lotCases, setLotCases] = useState([]);
  const [filter, setFilter] = useState(''); const [reload, setReload] = useState(0);
  const pending = useRef(null); const role = workstation();
  const canMove = ['MANAGER','FAO','RECEPTION'].includes(role); const canLot = ['MANAGER','FAO'].includes(role);
  async function fetchData(signal) {
    const [inventory, movements, lots, machines] = await Promise.all(['inventory/','inventory-transactions/','production-lots/','machines/'].map(path => allRows(api, path, {}, signal)));
    return { inventory, movements, lots, machines };
  }
  useEffect(() => { const abort = new AbortController(); fetchData(abort.signal).then(setData).catch(e => { if (!abort.signal.aborted) setError(errorText(e)); }); return () => abort.abort(); }, [reload]);
  async function mutate(action, message) {
    if (busy) return; setBusy(true); setError(''); setNotice('');
    try { await action(); setNotice(message); setData(await fetchData()); } catch (e) { setError(errorText(e)); } finally { setBusy(false); }
  }
  async function movement(event) {
    event.preventDefault();
    const original = data.movements.find(row => row.id === source);
    const payload = type === 'REVERSAL' ? { inventory_item: original?.inventory_item, transaction_type: type, reversal_of: source, notes }
      : { inventory_item: Number(item), transaction_type: type, quantity_changed: `${type === 'USAGE' ? '-' : ''}${quantity}`, prescription: caseId || null, production_lot: lot || null, notes };
    if (pending.current?.fingerprint !== JSON.stringify(payload)) pending.current = { fingerprint: JSON.stringify(payload), key: crypto.randomUUID() };
    await mutate(async () => {
      try { await api.post('inventory-transactions/', { ...payload, idempotency_key: pending.current.key }); pending.current = null; setQuantity(''); }
      catch (e) { if (e.response && e.response.status < 500) pending.current = null; throw e; }
    }, 'Mouvement enregistré dans le journal.');
  }
  return <div className="space-y-5"><Feedback error={error} notice={notice} /><Button disabled={busy} onClick={() => { setError(''); setReload(v => v + 1); }}>Actualiser</Button>
    {!data ? <p>Chargement des stocks…</p> : <>
      <Panel title="Soldes des consommables"><div className="grid gap-3 sm:grid-cols-3">{data.inventory.map(i => <div key={i.id} className="rounded-xl bg-white p-3"><p>{i.material_name}</p><p className={i.is_low_stock ? 'text-amber-700' : 'text-teal-800'}>{quantityText(i.quantity)} {i.unit}{i.is_low_stock ? ' · Stock faible' : ''}</p></div>)}</div></Panel>
      {canMove && <Panel title="Enregistrer un mouvement"><form onSubmit={movement}><fieldset disabled={busy} className="grid gap-4 sm:grid-cols-2"><Field label="Mouvement"><select className={control} value={type} onChange={e => setType(e.target.value)}><option value="RESTOCK">Réapprovisionnement</option><option value="USAGE">Consommation de production</option><option value="REVERSAL">Correction compensatoire</option></select></Field>
        {type === 'REVERSAL' ? <Field label="Mouvement d’origine"><select required className={control} value={source} onChange={e => setSource(e.target.value)}><option value="">Choisir</option>{data.movements.filter(m => !m.source_history && !m.reclassifies && !data.movements.some(r => r.reversal_of === m.id)).map(m => <option key={m.id} value={m.id}>{m.material_name_snapshot} · {m.transaction_type} · {quantityText(m.quantity_changed)} · {m.id}</option>)}</select></Field> : <>
          <Field label="Consommable"><select required className={control} value={item} onChange={e => setItem(e.target.value)}><option value="">Choisir</option>{data.inventory.map(i => <option key={i.id} value={i.id}>{i.material_name} ({i.unit})</option>)}</select></Field><Field label="Quantité positive"><input required className={control} type="number" min="0.01" step="0.01" value={quantity} onChange={e => { if (acceptsQuantity(e.target.value)) setQuantity(e.target.value.replace(',', '.')); }} /></Field>
          <Field label="Dossier de production"><select required={type === 'USAGE'} className={control} value={caseId} onChange={e => { setCaseId(e.target.value); setLot(''); }}><option value="">Sans dossier</option>{orders.map(o => <option key={o.id} value={o.id}>{o.patient_ref} · {o.status_label}</option>)}</select></Field><Field label="Lot de production"><select className={control} value={lot} onChange={e => setLot(e.target.value)}><option value="">Sans lot</option>{data.lots.filter(l => !caseId || l.prescriptions.includes(caseId)).map(l => <option key={l.id} value={l.id}>{l.code}</option>)}</select></Field>
        </>}
        <Field label="Motif et traçabilité"><textarea required className={control} value={notes} onChange={e => setNotes(e.target.value)} /></Field><div className="self-end"><Button type="submit">Enregistrer le mouvement</Button></div>
      </fieldset></form><p className="mt-3 text-xs text-slate-500">Les pertes de reprise se classent depuis le dossier clinique en référence à une consommation mesurée.</p></Panel>}
      {canLot && <Panel title="Créer et lier un lot"><form onSubmit={e => { e.preventDefault(); mutate(async () => { await api.post('production-lots/', { code, machine: machine ? Number(machine) : null, inventory_item: lotItem ? Number(lotItem) : null, prescriptions: lotCases }); setCode(''); setLotCases([]); }, 'Lot créé et lié aux dossiers.'); }}><fieldset disabled={busy} className="grid gap-4 sm:grid-cols-2"><Field label="Code unique"><input required maxLength={80} className={control} value={code} onChange={e => setCode(e.target.value)} /></Field><Field label="Machine"><select className={control} value={machine} onChange={e => setMachine(e.target.value)}><option value="">Sans machine</option>{data.machines.map(m => <option key={m.id} value={m.id}>{m.name} · capacité {m.capacity} · {m.status}</option>)}</select></Field><Field label="Consommable du lot"><select className={control} value={lotItem} onChange={e => setLotItem(e.target.value)}><option value="">Sans consommable</option>{data.inventory.map(i => <option key={i.id} value={i.id}>{i.material_name}</option>)}</select></Field><Field label="Dossiers du lot (sélection multiple)"><select required multiple className={control} value={lotCases} onChange={e => setLotCases(Array.from(e.target.selectedOptions, option => option.value))}>{orders.map(o => <option key={o.id} value={o.id}>{o.patient_ref} · {o.status_label}</option>)}</select></Field><Button type="submit">Créer le lot</Button></fieldset></form></Panel>}
      <Panel title="Lots enregistrés">{data.lots.map(l => <p key={l.id} className="break-words text-sm">{l.code} · {l.prescriptions.map(id => orders.find(o => o.id === id)?.patient_ref || id).join(', ')}</p>)}</Panel>
      <Panel title="Journal immuable des mouvements"><Field label="Filtrer par consommable"><select className={control} value={filter} onChange={e => setFilter(e.target.value)}><option value="">Tous</option>{data.inventory.map(i => <option key={i.id} value={i.id}>{i.material_name}</option>)}</select></Field><Paged rows={[...data.movements].reverse().filter(m => !filter || String(m.inventory_item) === filter)}>{rows => <div className="overflow-x-auto"><table className="w-full text-left text-xs"><thead><tr>{['Date','Matériau','Type','Quantité','Solde','Dossier / lot','Motif'].map(h => <th key={h} className="p-2">{h}</th>)}</tr></thead><tbody>{rows.map(m => <tr key={m.id} className="border-t border-slate-200/80"><td className="p-2">{new Date(m.created_at).toLocaleString('fr-FR')}</td><td className="p-2">{m.material_name_snapshot}</td><td className="p-2">{m.transaction_type}</td><td className="p-2">{quantityText(m.quantity_changed)} {m.unit_snapshot}</td><td className="p-2">{quantityText(m.balance_after)}</td><td className="p-2">{orders.find(o => o.id === m.prescription)?.patient_ref} / {data.lots.find(l => l.id === m.production_lot)?.code}</td><td className="p-2">{m.notes}</td></tr>)}</tbody></table></div>}</Paged></Panel>
      {['MANAGER','FAO','QUALITE','COMPTABILITE'].includes(role) && <StockLossCatalog />}
    </>}
  </div>;
}

function StockLossCatalog() {
  const [month, setMonth] = useState(''); const [rows, setRows] = useState([]); const [metadata, setMetadata] = useState(null); const [busy, setBusy] = useState(false); const [error, setError] = useState('');
  async function load() {
    setBusy(true); setError('');
    try {
      const params = month ? { month } : {};
      const [data, first] = await Promise.all([allRows(api, 'analytics/stock-loss/', params), api.get('analytics/stock-loss/', { params })]);
      setRows(data); setMetadata(first.data.analytics);
    } catch (e) { setError(errorText(e)); } finally { setBusy(false); }
  }
  return <Panel title="Pertes mensuelles de matières"><div className="flex flex-wrap items-end gap-3"><Field label="Mois des pertes"><input className={control} type="month" value={month} onChange={e => setMonth(e.target.value)} /></Field><Button disabled={busy} onClick={load}>Consulter les pertes</Button></div><Feedback error={error} />{metadata && <p className="text-xs text-slate-500">Dernière actualisation : {metadata.last_refreshed_at || 'Jamais'} · {metadata.stale ? 'Données à actualiser' : 'À jour'}</p>}<Paged rows={rows}>{page => <div className="space-y-3 text-sm">{page.map(row => <div key={row.catalog_key}><p>{row.loss_month.slice(0,7)} · {row.material_name} · Perte {quantityText(row.lost_quantity)} {row.unit} · Valorisation connue : {row.valued_loss_amount == null ? 'Indisponible' : money(row.valued_loss_amount)}</p>{!row.complete_valuation && <p className="text-amber-800">Valorisation incomplète : {quantityText(row.unvalued_quantity)} {row.unit} sans coût de référence.</p>}</div>)}</div>}</Paged></Panel>;
}
