import { useEffect, useRef, useState } from 'react';
import platform from './api/platform';
import { errorText, money, retryableRequest } from './api/contracts';
import { Button, control, Feedback, Field, Paged, Panel } from './IntegrationUI';
import BpmnCasePanel from './BpmnCasePanel';
import ClinicalDashboard from './ClinicalDashboard';
import shadeGuide from './assets/shade-guide.png';

const emptyItem = () => ({ tooth_number: 11, function: '', form: '', shade: 'A1', material: '' });
const teeth = [18,17,16,15,14,13,12,11,21,22,23,24,25,26,27,28,48,47,46,45,44,43,42,41,31,32,33,34,35,36,37,38];

export default function DentistPortal({ orders, refresh }) {
  const [tab, setTab] = useState('new'); const [query, setQuery] = useState('');
  return <div className="space-y-6"><div className="flex flex-wrap gap-3"><Button onClick={() => setTab('overview')}>Vue clinique</Button><Button onClick={() => setTab('new')}>Nouvelle prescription</Button><Button onClick={() => setTab('orders')}>Mes commandes ({orders.length})</Button></div>
    {tab === 'overview' ? <ClinicalDashboard orders={orders} onOpenOrders={() => setTab('orders')} /> : tab === 'new' ? <DentistForm onSuccess={async () => { await refresh(); setTab('orders'); }} /> : <>
      <input className={control} aria-label="Rechercher mes commandes" placeholder="Référence patient, laboratoire…" value={query} onChange={e => setQuery(e.target.value)} />
      <Paged rows={orders.filter(o => `${o.patient_ref} ${o.laboratory_name}`.toLowerCase().includes(query.toLowerCase()))}>{rows => <div className="space-y-5">{rows.map(order => <Panel key={`${order.laboratory_id}:${order.id}`} title={`${order.patient_ref} · ${order.laboratory_name}`}><p className="text-sm text-slate-600">{order.status_label || order.status} · {money(order.total_price)}</p><p className="text-xs text-slate-500">{order.clinical_items?.map(item => `${item.tooth_number} : ${item.function}, ${item.form}, ${item.material}, ${item.shade}`).join(' · ')}</p><BpmnCasePanel order={order} dentist refresh={refresh} /></Panel>)}{!rows.length && <p>Aucune commande.</p>}</div>}</Paged>
    </>}
  </div>;
}

function DentistForm({ onSuccess }) {
  const [labs, setLabs] = useState([]); const [catalog, setCatalog] = useState(null);
  const [lab, setLab] = useState(''); const [clinics, setClinics] = useState([]); const [clinic, setClinic] = useState('');
  const [patient, setPatient] = useState(''); const [items, setItems] = useState([emptyItem()]);
  const [track, setTrack] = useState('PHYSIQUE'); const [service, setService] = useState('STANDARD');
  const [disinfected, setDisinfected] = useState(false); const [design, setDesign] = useState(false);
  const [file, setFile] = useState(null); const [created, setCreated] = useState(null); const [uploaded, setUploaded] = useState(false);
  const [busy, setBusy] = useState(false); const [error, setError] = useState(''); const [clinicError, setClinicError] = useState('');
  const [reload, setReload] = useState(0); const [pin, setPin] = useState('');
  const submitRequest = useRef(retryableRequest());
  useEffect(() => {
    const abort = new AbortController();
    Promise.all([platform.get('laboratories/', { signal: abort.signal }), platform.get('pricing/', { signal: abort.signal })])
      .then(([laboratories, pricing]) => { setLabs(laboratories.data); setCatalog(pricing.data); setError(''); })
      .catch(e => { if (!abort.signal.aborted) setError(errorText(e)); });
    return () => abort.abort();
  }, [reload]);
  useEffect(() => {
    if (!lab) return;
    const abort = new AbortController();
    platform.get('dentist/clinics/', { params: { laboratory: lab }, signal: abort.signal }).then(({ data }) => { setClinics(data); setClinicError(''); })
      .catch(e => { if (!abort.signal.aborted) setClinicError(errorText(e)); });
    return () => abort.abort();
  }, [lab, reload]);
  const update = (index, key, value) => setItems(items.map((item, i) => i === index ? { ...item, [key]: value } : item));
  const priced = catalog && items.every(item => Object.hasOwn(catalog.materials, item.material));
  const base = priced ? items.reduce((sum, item) => sum + Number(catalog.materials[item.material]), 0) : null;
  const estimate = base == null || service === 'NEXT_DAY' ? null : base * (service === 'EXPRESS' ? 1 + Number(catalog.express_rate) : 1);
  async function submit(event) {
    event.preventDefault(); if (busy) return;
    setBusy(true); setError('');
    try {
      if (new Set(items.map(item => Number(item.tooth_number))).size !== items.length) throw new Error('Chaque dent doit être distincte.');
      if (track === 'NUMERIQUE' && !file && !uploaded) throw new Error('Choisissez le fichier STL à téléverser.');
      if (file && (!file.name.toLowerCase().endsWith('.stl') || !file.size || file.size > 25 * 1024 * 1024)) throw new Error('Choisissez un STL non vide de 25 Mo maximum.');
      let order = created;
      if (!order) {
        const response = await submitRequest.current(platform, 'dentist/orders/', {
          laboratory_id: lab, partner_clinic: Number(clinic), patient_ref: patient,
          clinical_items: items.map(item => ({ ...item, tooth_number: Number(item.tooth_number) })),
          impression_type: track, delivery_service: service, disinfected, design_validation_requested: design,
        });
        order = response.data; setCreated(order); setPin(order.delivery_pin_once || '');
      }
      if (track === 'NUMERIQUE' && !uploaded) {
        const body = new FormData(); body.append('file', file); body.append('kind', 'STL');
        await platform.post(`dentist/orders/${lab}/${order.id}/attachments/`, body);
        setUploaded(true);
      }
      setCreated({ ...order, ready: true });
    } catch (e) { setError(errorText(e)); }
    finally { setBusy(false); }
  }
  if (created?.ready) return <Panel title="Prescription enregistrée"><p>Montant confirmé : {money(created.total_price)}</p>{pin ? <p className="rounded-xl bg-amber-400/10 p-4">PIN de livraison, affiché une seule fois : <strong className="select-all font-mono text-xl">{pin}</strong></p> : <p>Vous pouvez émettre un nouveau PIN depuis le dossier.</p>}<Button onClick={onSuccess}>Voir mes commandes</Button></Panel>;
  return <form onSubmit={submit} className="space-y-5"><Panel title="Prescription clinique"><Feedback error={error || clinicError} />{(!catalog || error || clinicError) && <Button onClick={() => setReload(value => value + 1)}>Recharger les données</Button>}
    {created && <p role="status" className="text-amber-800">Le dossier est créé. Réessayez le téléversement du STL pour le compléter.</p>}
    <fieldset disabled={busy || Boolean(created)} className="space-y-5">
      <div className="grid gap-4 md:grid-cols-2"><Field label="Laboratoire destinataire"><select className={control} required value={lab} onChange={e => { setLab(e.target.value); setClinic(''); setClinics([]); }}><option value="">Choisir</option>{labs.map(l => <option key={l.identifier} value={l.identifier}>{l.name}</option>)}</select></Field>
        <Field label="Cabinet et adresse de collecte"><select className={control} required value={clinic} onChange={e => setClinic(e.target.value)}><option value="">Choisir un cabinet vérifié</option>{clinics.filter(c => c.pickup_address?.trim()).map(c => <option key={c.id} value={c.id}>{c.name} · {c.pickup_address}</option>)}</select></Field></div>
      {lab && !clinics.some(c => c.pickup_address?.trim()) && <p className="text-sm text-amber-800">Le laboratoire doit associer un cabinet avec une adresse à votre compte.</p>}
      <Field label="Référence patient anonyme"><input className={control} required maxLength={50} value={patient} onChange={e => setPatient(e.target.value)} /></Field>
      <img src={shadeGuide} alt="Guide de teintes VITA" className="max-h-40 rounded-xl bg-white object-contain" />
      <div className="space-y-4">{items.map((item, index) => <section key={index} className="space-y-3 rounded-xl border border-slate-200/80 p-4"><div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
        <Field label="Dent FDI"><input list="fdi-teeth" className={control} required type="number" value={item.tooth_number} onChange={e => update(index, 'tooth_number', e.target.value)} /></Field>
        <Field label="Fonction"><input className={control} required maxLength={100} placeholder="Couronne, bridge…" value={item.function} onChange={e => update(index, 'function', e.target.value)} /></Field>
        <Field label="Forme"><input className={control} required maxLength={100} value={item.form} onChange={e => update(index, 'form', e.target.value)} /></Field>
        <Field label="Teinte"><input className={control} required maxLength={10} value={item.shade} onChange={e => update(index, 'shade', e.target.value)} /></Field>
        <Field label="Matériau"><select className={control} required value={item.material} onChange={e => update(index, 'material', e.target.value)}><option value="">Choisir</option>{Object.entries(catalog?.materials || {}).map(([name, amount]) => <option key={name} value={name}>{name} · {money(amount)}</option>)}</select></Field>
      </div><Button disabled={items.length === 1} onClick={() => setItems(items.filter((_, i) => i !== index))}>Retirer cette dent</Button></section>)}</div>
      <datalist id="fdi-teeth">{teeth.map(tooth => <option key={tooth} value={tooth} />)}</datalist>
      <Button disabled={items.length >= 32} onClick={() => setItems([...items, emptyItem()])}>Ajouter une dent ({items.length}/32)</Button>
      <div className="grid gap-4 sm:grid-cols-2"><Field label="Empreinte"><select className={control} value={track} onChange={e => { setTrack(e.target.value); setFile(null); }}><option value="PHYSIQUE">Physique · collecte coursier</option><option value="NUMERIQUE">Numérique · fichier STL</option></select></Field><Field label="Service de livraison"><select className={control} value={service} onChange={e => setService(e.target.value)}><option value="STANDARD">Standard J+4</option><option value="EXPRESS">Express J+2 · +30 %</option><option value="NEXT_DAY">J+1 · devis manuel laboratoire</option></select></Field></div>
      <label className="flex gap-3 text-sm"><input type="checkbox" checked={design} onChange={e => setDesign(e.target.checked)} />Demander une validation du design avant fabrication</label>
      <label className="flex gap-3 text-sm"><input required type="checkbox" checked={disinfected} onChange={e => setDisinfected(e.target.checked)} />Je confirme la désinfection selon le protocole.</label>
    </fieldset>
    {track === 'NUMERIQUE' && <Field label="Fichier STL réel · 25 Mo maximum"><input className={control} type="file" required={!uploaded} disabled={busy} accept=".stl" onChange={e => setFile(e.target.files[0] || null)} /></Field>}
    <p className="text-sm text-slate-600">Base catalogue : {base == null ? 'Choisir les matériaux' : money(base)} · Estimation : {money(estimate)}. Le serveur confirme le montant à l’enregistrement.</p>
    <button disabled={busy || !catalog || !clinic || Boolean(clinicError)} className="rounded-xl bg-teal-600 px-5 py-3 disabled:opacity-40">{busy ? 'Enregistrement…' : created ? 'Réessayer le téléversement STL' : 'Envoyer la prescription'}</button>
  </Panel></form>;
}
