import { useEffect, useRef, useState } from 'react';
import FilePicker from './FilePicker';
import platform from './api/platform';
import { download, errorText, money, retryableRequest } from './api/contracts';
import { Button, control, Feedback, Field, Paged, Panel } from './IntegrationUI';
import CaseWorkspace from './CaseWorkspace';
import ToothPicker from './ToothPicker';
import ChoiceWithOther from './ChoiceWithOther';
import { formOptions, functionOptions, shadeOptions } from './prescriptionOptions';
import { applyFirstToAll, toggleTooth } from './toothPickerHelpers';
import shadeGuide from './assets/shade-guide.png';
import { dentistAction } from './workQueueHelpers';
import { caseStatusLabel } from './api/messages';
import { useTestCaseFilter } from './TestCaseToggle';

const casablancaDate = value => new Intl.DateTimeFormat('fr-FR', { dateStyle: 'long', timeZone: 'Africa/Casablanca' }).format(new Date(value));
const expectedDate = order => order.delivery_date ? casablancaDate(`${order.delivery_date}T12:00:00Z`) : order.deadline_at ? casablancaDate(order.deadline_at) : null;

function StageStrip({ order }) {
  if (!order.stages?.length) return null;
  return <ol className="stage-strip" aria-label={`Étapes du dossier ${order.patient_ref}`}>{order.stages.map(stage => <li key={stage.key} data-state={stage.state} aria-current={stage.state === 'current' ? 'step' : undefined}>{stage.state === 'done' && <span aria-hidden="true">✓ </span>}{stage.label}{stage.state === 'done' && <span className="sr-only"> (terminée)</span>}</li>)}</ol>;
}

export default function DentistPortal({ orders, refresh }) {
  const [chosenTab, setTab] = useState(null); const tab = chosenTab ?? (orders.length ? 'orders' : 'new'); const [query, setQuery] = useState('');
  const [selected, setSelected] = useState(null); const opener = useRef(null);
  const { visible, toggle } = useTestCaseFilter(orders);
  const actionable = visible.map(order => ({ order, action: dentistAction(order) })).filter(row => row.action);
  const active = selected && orders.find(order => order.id === selected.id && order.laboratory_id === selected.lab);
  return <div className="space-y-6"><Panel title={`À faire (${actionable.length})`}>
    {!actionable.length && <p className="text-sm text-slate-500">Aucune action attendue de votre part pour le moment.</p>}
    {actionable.map(({ order, action }) => <article key={`${order.laboratory_id}:${order.id}`} aria-label={`Action pour ${order.patient_ref}`} className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-slate-200 p-3"><div className="min-w-0"><p className="break-words font-medium">{order.patient_ref}</p><p className="break-words text-sm text-slate-500">{order.laboratory_name} · {caseStatusLabel(order)}</p></div><Button onClick={event => { opener.current = event.currentTarget; setSelected({ id: order.id, lab: order.laboratory_id, focus: action.focus }); }}>{action.label}</Button></article>)}
  </Panel>{active && <CaseWorkspace key={`${active.laboratory_id}:${active.id}`} order={active} dentist refresh={refresh} returnFocus={opener} focusAction={selected.focus} onClose={() => setSelected(null)} />}
    <div className="flex flex-wrap gap-3"><Button onClick={() => setTab('new')}>Nouvelle prescription</Button><Button onClick={() => setTab('orders')}>Mes commandes ({orders.length})</Button></div>
    {tab === 'new' ? <DentistForm onSuccess={async () => { await refresh(); setTab('orders'); }} /> : <>
      <input className={control} aria-label="Rechercher mes commandes" placeholder="Référence patient, laboratoire…" value={query} onChange={e => setQuery(e.target.value)} />
      {toggle}<Paged rows={visible.filter(o => `${o.patient_ref} ${o.laboratory_name}`.toLowerCase().includes(query.toLowerCase()))}>{rows => <div className="space-y-5">{rows.map(order => <Panel key={`${order.laboratory_id}:${order.id}`} title={`${order.patient_ref} · ${order.laboratory_name}`}><p className="text-sm text-slate-600">{caseStatusLabel(order)} · {money(order.total_price)}</p><StageStrip order={order} /><p className="text-sm text-slate-700">{expectedDate(order) ? `Livraison prévue : ${expectedDate(order)}` : 'Date à confirmer par le laboratoire'}</p><p className="text-xs text-slate-500">{order.clinical_items?.map(item => `${item.tooth_number} : ${item.function}, ${item.form}, ${item.material}, ${item.shade}`).join(' · ')}</p><Button onClick={event => { opener.current = event.currentTarget; setSelected({ id: order.id, lab: order.laboratory_id, focus: dentistAction(order)?.focus }); }}>Ouvrir le dossier {order.patient_ref}</Button></Panel>)}{!rows.length && <p>Aucune commande.</p>}</div>}</Paged>
    </>}
  </div>;
}

function DentistForm({ onSuccess }) {
  const [labs, setLabs] = useState([]); const [catalog, setCatalog] = useState(null);
  const [lab, setLab] = useState(''); const [clinics, setClinics] = useState([]); const [clinic, setClinic] = useState('');
  const [patient, setPatient] = useState(''); const [items, setItems] = useState([]);
  const [track, setTrack] = useState('PHYSIQUE'); const [service, setService] = useState('STANDARD');
  const [disinfected, setDisinfected] = useState(false); const [design, setDesign] = useState(false);
  const [file, setFile] = useState(null); const [created, setCreated] = useState(null); const [uploaded, setUploaded] = useState(false);
  const [busy, setBusy] = useState(false); const [error, setError] = useState(''); const [clinicError, setClinicError] = useState('');
  const [reload, setReload] = useState(0); const [pin, setPin] = useState('');
  const submitRequest = useRef(retryableRequest());
  const [capacity, setCapacity] = useState(null);
  const capacityTeeth = items.map(item => item.tooth_number).join(',');
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
  useEffect(() => {
    if (!lab || created) return;
    const abort = new AbortController();
    const timer = setTimeout(() => {
      platform.post('dentist/capacity-preview/', { laboratory_id: lab,
        delivery_service: service, impression_type: track, clinical_item_count: items.length },
      { signal: abort.signal, feedback: false }).then(({ data }) => { if (!abort.signal.aborted) setCapacity({ ...data, laboratory_id: lab, delivery_service: service, impression_type: track, clinical_item_count: items.length, teeth: capacityTeeth }); })
        .catch(() => { if (!abort.signal.aborted) setCapacity(null); });
    }, 350);
    return () => { clearTimeout(timer); abort.abort(); };
  }, [lab, service, track, items.length, capacityTeeth, created]);
  const capacityMatches = capacity?.laboratory_id === lab && capacity?.delivery_service === service && capacity?.impression_type === track && capacity?.clinical_item_count === items.length && capacity?.teeth === capacityTeeth;
  const update = (index, key, value) => setItems(items.map((item, i) => i === index ? { ...item, [key]: value } : item));
  const priced = catalog && items.every(item => Object.hasOwn(catalog.materials, item.material));
  const base = priced ? items.reduce((sum, item) => sum + Number(catalog.materials[item.material]), 0) : null;
  const estimate = base == null || service === 'NEXT_DAY' ? null : base * (service === 'EXPRESS' ? 1 + Number(catalog.express_rate) : 1);
  async function submit(event) {
    event.preventDefault(); if (busy) return;
    setBusy(true); setError('');
    try {
      if (!items.length) throw new Error('Sélectionnez au moins une dent sur le schéma.');
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
  if (created?.ready) return <Panel title="Prescription enregistrée"><p>Montant confirmé : {money(created.total_price)}</p><Feedback error={error} /><Button onClick={async () => { setError(''); try { await download(platform, `dentist/orders/${lab}/${created.id}/qr/`, `etiquette-${created.patient_ref}.png`); } catch (e) { setError(errorText(e)); } }}>Télécharger l’étiquette QR</Button><p className="text-xs text-slate-500">À joindre à l’empreinte : le coursier scanne ou importe ce QR à chaque remise.</p>{pin ? <p className="rounded-xl bg-amber-400/10 p-4">PIN de livraison, affiché une seule fois : <strong className="select-all font-mono text-xl">{pin}</strong></p> : <p>Vous pouvez émettre un nouveau PIN depuis le dossier.</p>}<Button onClick={onSuccess}>Voir mes commandes</Button></Panel>;
  return <form onSubmit={submit} className="space-y-5"><Panel title="Prescription clinique"><Feedback error={error || clinicError} />{(!catalog || error || clinicError) && <Button onClick={() => setReload(value => value + 1)}>Recharger les données</Button>}
    {created && <p role="status" className="text-amber-800">Le dossier est créé. Réessayez le téléversement du STL pour le compléter.</p>}
    <fieldset disabled={busy || Boolean(created)} className="min-w-0 space-y-5">
      <div className="grid gap-4 md:grid-cols-2"><Field label="Laboratoire destinataire"><select className={control} required value={lab} onChange={e => { setLab(e.target.value); setClinic(''); setClinics([]); }}><option value="">Choisir</option>{labs.map(l => <option key={l.identifier} value={l.identifier}>{l.name}</option>)}</select></Field>
        <Field label="Cabinet et adresse de collecte"><select className={control} required value={clinic} onChange={e => setClinic(e.target.value)}><option value="">Choisir un cabinet vérifié</option>{clinics.filter(c => c.pickup_address?.trim()).map(c => <option key={c.id} value={c.id}>{c.name} · {c.pickup_address}</option>)}</select></Field></div>
      {lab && !clinics.some(c => c.pickup_address?.trim()) && <p className="text-sm text-amber-800">Le laboratoire doit associer un cabinet avec une adresse à votre compte.</p>}
      <Field label="Référence patient anonyme"><input className={control} required maxLength={50} value={patient} onChange={e => setPatient(e.target.value)} /></Field>
      <img src={shadeGuide} alt="Guide de teintes VITA" className="max-h-40 rounded-xl bg-white object-contain" />
      <ToothPicker selected={items.map(item => item.tooth_number)} onToggle={tooth => setItems(current => toggleTooth(current, tooth))} disabled={busy || Boolean(created)} error={items.length ? '' : 'Sélectionnez au moins une dent sur le schéma.'} />
      <div className="space-y-4">{items.map((item, index) => <fieldset key={item.tooth_number} className="min-w-0 space-y-3 rounded-xl border border-slate-200/80 p-4"><legend className="px-1 font-medium text-slate-800">Dent {item.tooth_number}</legend><div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <ChoiceWithOther label="Fonction" options={functionOptions} maxLength={100} value={item.function} onChange={value => update(index, 'function', value)} />
        <ChoiceWithOther label="Forme" options={formOptions} maxLength={100} value={item.form} onChange={value => update(index, 'form', value)} />
        <ChoiceWithOther label="Teinte" options={shadeOptions} maxLength={10} value={item.shade} onChange={value => update(index, 'shade', value)} />
        <Field label="Matériau"><select className={control} required value={item.material} onChange={e => update(index, 'material', e.target.value)}><option value="">Choisir</option>{Object.entries(catalog?.materials || {}).map(([name, amount]) => <option key={name} value={name}>{name} · {money(amount)}</option>)}</select></Field>
      </div><div className="flex flex-wrap gap-3">{index === 0 && items.length > 1 && <Button onClick={() => setItems(applyFirstToAll(items))}>Appliquer à toutes les dents</Button>}<Button onClick={() => setItems(current => toggleTooth(current, item.tooth_number))}>Retirer cette dent</Button></div></fieldset>)}</div>
      <div className="grid gap-4 sm:grid-cols-2"><Field label="Empreinte"><select className={control} value={track} onChange={e => { setTrack(e.target.value); setFile(null); }}><option value="PHYSIQUE">Physique · collecte coursier</option><option value="NUMERIQUE">Numérique · fichier STL</option></select></Field><Field label="Service de livraison"><select className={control} value={service} onChange={e => setService(e.target.value)}><option value="STANDARD">Standard J+4</option><option value="EXPRESS">Express J+2 · +30 %</option><option value="NEXT_DAY">J+1 · devis manuel laboratoire</option></select></Field></div>
      <label className="flex gap-3 text-sm"><input type="checkbox" checked={design} onChange={e => setDesign(e.target.checked)} />Demander une validation du design avant fabrication</label>
      <label className="flex gap-3 text-sm"><input required type="checkbox" checked={disinfected} onChange={e => setDisinfected(e.target.checked)} />Je confirme la désinfection selon le protocole.</label>
    </fieldset>
    {track === 'NUMERIQUE' && <FilePicker label="Fichier STL réel · 25 Mo maximum" required={!uploaded} disabled={busy} accept=".stl" file={file} onChange={setFile} />}
    <p className="text-sm text-slate-600">Base catalogue : {base == null ? 'Choisir les matériaux' : money(base)} · Estimation : {money(estimate)}. Le serveur confirme le montant à l’enregistrement.</p>
    {capacityMatches && capacity.feasible === true && !created && <p role="status" className="text-sm text-slate-600">Première date estimée : {new Intl.DateTimeFormat('fr-FR', { dateStyle: 'long', timeZone: 'Africa/Casablanca' }).format(new Date(`${capacity.earliest_feasible_date}T12:00:00Z`))}. Date provisoire, hors transport et attente de validation ; le laboratoire confirme le parcours et la date.</p>}
    {capacityMatches && capacity.feasible === false && !created && <aside role="status" aria-label="Capacité indicative" className="space-y-3 rounded-xl border border-amber-300 bg-amber-50 p-4 text-amber-950">
      <p>Le laboratoire est chargé à cette date. Date de livraison réaliste : {new Intl.DateTimeFormat('fr-FR', { dateStyle: 'long', timeZone: 'Africa/Casablanca' }).format(new Date(`${capacity.earliest_feasible_date}T12:00:00Z`))}.</p>
      {capacity.reason_code === 'CLOSED_DAY' && <p>La date demandée correspond à un jour de fermeture.</p>}
      <p className="text-sm">Date provisoire, hors transport et attente de validation. Le laboratoire confirme le parcours et la date.</p>
      <div className="flex flex-wrap gap-3"><button type="submit" disabled={busy || !catalog || !clinic || Boolean(clinicError) || !items.length} className="rounded-xl border border-amber-600 px-4 py-2">Envoyer quand même</button>
        {service !== 'STANDARD' && <Button disabled={busy} onClick={() => { setCapacity(null); setService(service === 'NEXT_DAY' ? 'EXPRESS' : 'STANDARD'); }}>Choisir un délai plus long</Button>}
      </div>
    </aside>}
    <button disabled={busy || !catalog || !clinic || Boolean(clinicError) || !items.length} className="rounded-xl bg-teal-600 px-5 py-3 disabled:opacity-40">{busy ? 'Enregistrement…' : created ? 'Réessayer le téléversement STL' : 'Envoyer la prescription'}</button>
  </Panel></form>;
}
