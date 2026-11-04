import { useEffect, useRef, useState } from 'react';
import api from './api/client';
import platform from './api/platform';
import { acceptsQuantity, allRows, quantityInput, quantityText, workstation } from './api/contracts';
import LabConfiguration from './LabConfiguration';

const roles = [['RECEPTION', 'Réception'], ['CAO', 'CAO'], ['FAO', 'FAO'], ['QUALITE', 'Qualité'], ['COURSIER', 'Coursier']];
const sections = {
  personnel: {
    label: 'Personnel', endpoint: 'employee-profiles', singular: 'un profil',
    description: 'Rôles métier, contrats et disponibilité de votre équipe.',
    fields: [
      { key: 'user', label: 'Identifiant du collaborateur', type: 'number', min: 1, step: 1, hint: 'Identifiant du compte associé au membre de l’équipe.' },
      { key: 'role', label: 'Rôle', options: roles },
      { key: 'contract_type', label: 'Contrat', options: [['CDI', 'CDI'], ['CDD', 'CDD'], ['STAGE', 'Stage']] },
      { key: 'hire_date', label: 'Date d’embauche', type: 'date' },
      { key: 'is_available', label: 'Disponible', type: 'checkbox', initial: true },
    ],
    columns: [['user', 'Utilisateur'], ['role', 'Rôle'], ['contract_type', 'Contrat'], ['hire_date', 'Embauche'], ['is_available', 'Disponibilité']],
  },
  machines: {
    label: 'Parc Machine', endpoint: 'machines', singular: 'une machine',
    description: 'Capacité de production et état de vos équipements.',
    fields: [
      { key: 'name', label: 'Nom', maxLength: 120 },
      { key: 'machine_type', label: 'Type', options: [['SCANNER', 'Scanner'], ['USINEUSE_CNC', 'Usineuse CNC'], ['FOUR_FRITTAGE', 'Four de frittage']] },
      { key: 'capacity', label: 'Éléments simultanés', type: 'number', min: 1, step: 1 },
      { key: 'status', label: 'État', options: [['ACTIF', 'Actif'], ['MAINTENANCE', 'Maintenance'], ['PANNE', 'En panne']] },
    ],
    columns: [['name', 'Machine'], ['machine_type', 'Type'], ['capacity', 'Capacité'], ['status', 'État']],
  },
  stock: {
    label: 'Stock', endpoint: 'inventory', singular: 'un consommable',
    description: 'Consommables et seuils de réapprovisionnement.',
    fields: [
      { key: 'material_name', label: 'Matériau', maxLength: 120 },
      { key: 'quantity', label: 'Quantité initiale', type: 'number', min: 0, step: '0.01', decimal: true, createOnly: true, hint: 'Après création, le solde suit les mouvements de stock.' },
      { key: 'unit', label: 'Unité', createOnly: true, options: [['DISQUE', 'Disque'], ['GRAMMES', 'Grammes'], ['UNITES', 'Unités']] },
      { key: 'alert_threshold', label: 'Seuil d’alerte', type: 'number', min: 0, step: '0.01', decimal: true },
      { key: 'unit_cost', label: 'Coût unitaire de référence (MAD)', type: 'number', min: 0, step: '0.01', decimal: true, optional: true, hint: 'Facultatif. Conservé dans chaque nouveau mouvement pour valoriser les pertes.' },
    ],
    columns: [['material_name', 'Matériau'], ['quantity', 'Quantité'], ['unit', 'Unité'], ['alert_threshold', 'Seuil'], ['is_low_stock', 'Niveau']],
  },
  cabinets: {
    label: 'Cabinets', endpoint: 'partner-clinics', singular: 'un cabinet',
    description: 'Partenaires et adresses de ramassage pour vos coursiers.',
    fields: [
      { key: 'name', label: 'Nom du cabinet', maxLength: 120 },
      { key: 'pickup_address', label: 'Adresse de ramassage', type: 'textarea' },
      { key: 'contact_phone', label: 'Téléphone', type: 'tel', maxLength: 30 },
      { key: 'contact_email', label: 'E-mail du cabinet', type: 'email', optional: true },
      { key: 'platform_dentist', label: 'Compte dentiste de la plateforme', type: 'number', min: 1, step: 1, hint: 'Associez le compte pour rendre ce cabinet disponible dans ses prescriptions.' },
      { key: 'linked_dentist', label: 'ID utilisateur du dentiste', type: 'number', min: 1, step: 1, optional: true, hint: 'Facultatif : identifiant d’un utilisateur Django existant.' },
    ],
    columns: [['name', 'Cabinet'], ['pickup_address', 'Adresse de ramassage'], ['contact_phone', 'Téléphone'], ['linked_dentist', 'Dentiste']],
  },
};
const tabs = Object.keys(sections);
const inputClass = 'w-full rounded-xl border border-slate-200/80 bg-white px-3 py-2.5 text-sm text-slate-900 outline-none focus:border-sky-400 focus:ring-1 focus:ring-sky-400 disabled:opacity-50';
const buttonClass = 'rounded-xl border border-slate-200/80 px-3 py-2 text-sm text-slate-600 hover:bg-white focus-visible:outline-2 focus-visible:outline-sky-400 disabled:opacity-40';
const initialForm = section => Object.fromEntries(section.fields.map(field => [field.key, field.initial ?? field.options?.[0][0] ?? '']));
const rowName = row => row.name || row.material_name || `Utilisateur #${row.user}`;

function cellValue(section, row, key) {
  const value = row[key];
  if (key === 'is_available' || key === 'is_low_stock' || key === 'status') {
    const warning = key === 'is_available' ? !value : key === 'is_low_stock' ? value : value !== 'ACTIF';
    const label = key === 'is_available' ? (value ? 'Disponible' : 'Indisponible') : key === 'is_low_stock' ? (value ? 'Stock bas' : 'Suffisant') : section.fields.find(field => field.key === key)?.options.find(([id]) => id === value)?.[1];
    return <span className={`inline-flex whitespace-nowrap rounded-full border px-2.5 py-1 text-xs ${warning ? 'border-amber-400/20 bg-amber-400/10 text-amber-700' : 'border-emerald-400/20 bg-emerald-400/10 text-emerald-700'}`}>{label}</span>;
  }
  if (value == null || value === '') return '—';
  if (['quantity', 'alert_threshold', 'unit_cost'].includes(key)) return quantityText(value);
  const options = section.fields.find(field => field.key === key)?.options;
  if (options) return options.find(([id]) => id === value)?.[1] || value;
  if (key === 'user') return row.name || `#${value}`;
  if (key === 'linked_dentist') return `#${value}`;
  if (key === 'hire_date') return new Intl.DateTimeFormat('fr-FR').format(new Date(`${value}T12:00:00`));
  return typeof value === 'number' ? value.toLocaleString('fr-FR') : value;
}

function ResourceTable({ section, active, labelledBy }) {
  const [dentists, setDentists] = useState([]);
  const role = workstation();
  const canWrite = (section.endpoint === 'partner-clinics' ? ['MANAGER', 'RECEPTION'] : ['inventory', 'machines'].includes(section.endpoint) ? ['MANAGER', 'FAO'] : ['MANAGER']).includes(role);
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [reload, setReload] = useState(0);
  const [query, setQuery] = useState('');
  const [editor, setEditor] = useState(null);
  const [form, setForm] = useState(() => initialForm(section));
  const [fieldErrors, setFieldErrors] = useState({});
  const [deleting, setDeleting] = useState(null);
  const [saving, setSaving] = useState(false);
  const busy = useRef(false);
  const editorTitle = useRef(null);

  useEffect(() => {
    const controller = new AbortController();
    allRows(api, `${section.endpoint}/`, {}, controller.signal).then(data => {
      if (!controller.signal.aborted) setRows(data);
    }).catch(cause => {
      if (!controller.signal.aborted) setError(cause.response?.data?.detail || 'Impossible de charger les fiches. Vérifiez votre connexion et votre accès au laboratoire.');
    }).finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [section.endpoint, reload]);

  useEffect(() => {
    if (section.endpoint !== 'partner-clinics' || !canWrite) return;
    const controller = new AbortController();
    platform.get('dentists/', { signal: controller.signal }).then(({ data }) => setDentists(data)).catch(() => {});
    return () => controller.abort();
  }, [section.endpoint, canWrite]);

  useEffect(() => { if (editor) editorTitle.current?.focus(); }, [editor]);

  function refresh() { setLoading(true); setError(''); setReload(value => value + 1); }
  function openEditor(row = null) {
    setEditor({ id: row?.id ?? null });
    setForm(row ? Object.fromEntries(section.fields.map(field => [field.key, row[field.key] ?? ''])) : initialForm(section));
    setFieldErrors({}); setError(''); setNotice(''); setDeleting(null);
  }

  async function save(event) {
    event.preventDefault();
    if (busy.current) return;
    busy.current = true; setSaving(true); setFieldErrors({}); setError('');
    const payload = Object.fromEntries(section.fields.filter(field => !(editor.id && field.createOnly)).map(field => [field.key,
      field.type === 'number' ? (form[field.key] === '' ? null : field.decimal ? form[field.key] : Number(form[field.key])) :
        typeof form[field.key] === 'string' ? form[field.key].trim() : form[field.key],
    ]));
    try {
      if (editor.id) await api.patch(`${section.endpoint}/${editor.id}/`, payload);
      else await api.post(`${section.endpoint}/`, payload);
      setEditor(null); setNotice('Fiche enregistrée.'); refresh();
    } catch (cause) {
      const detail = cause.response?.data;
      setFieldErrors(detail && typeof detail === 'object' ? detail : {});
      setError(detail?.detail || 'Enregistrement impossible. Vérifiez les champs et réessayez.');
    } finally { busy.current = false; setSaving(false); }
  }

  async function remove() {
    if (busy.current) return;
    busy.current = true; setSaving(true); setError('');
    try { await api.delete(`${section.endpoint}/${deleting.id}/`); setDeleting(null); setNotice('Fiche supprimée.'); refresh(); }
    catch (cause) { setError(cause.response?.data?.detail || 'Suppression impossible. Cette fiche peut être liée à d’autres données.'); }
    finally { busy.current = false; setSaving(false); }
  }

  const visibleRows = rows.filter(row => section.columns.some(([key]) => String(row[key] ?? '').toLocaleLowerCase('fr').includes(query.toLocaleLowerCase('fr'))));
  return <section role="tabpanel" id={`config-panel-${active}`} aria-labelledby={labelledBy || `config-tab-${active}`} className="space-y-5 rounded-2xl border border-slate-200/80 bg-slate-50 p-4 backdrop-blur-md sm:p-6">
    <div className="flex flex-wrap items-center justify-between gap-4"><div><h2 className="text-lg font-semibold">{section.label}</h2><p className="mt-1 text-sm text-slate-500">{section.description}</p></div><button type="button" disabled={saving || loading || !canWrite} onClick={() => openEditor()} className="rounded-xl bg-teal-600 px-4 py-2.5 text-sm font-semibold text-slate-900 hover:bg-teal-700 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-sky-400 disabled:opacity-40">+ Ajouter {section.singular}</button></div>
    {error && <div role="alert" className="rounded-xl border border-red-400/20 bg-red-400/10 p-3 text-sm text-red-800">{error}{!editor && <button type="button" onClick={refresh} disabled={loading || saving} className="ml-3 underline disabled:opacity-40">Réessayer</button>}</div>}
    {notice && <p role="status" className="rounded-xl bg-emerald-400/10 p-3 text-sm text-emerald-700">{notice}</p>}
    {editor && <form onSubmit={save} className="space-y-5 rounded-xl border border-sky-400/20 bg-slate-50 p-5">
      <h3 ref={editorTitle} tabIndex={-1} className="font-medium outline-none">{editor.id ? 'Modifier la fiche' : `Ajouter ${section.singular}`}</h3>
      <p className="text-xs text-slate-500">Les champs marqués * sont obligatoires.</p>
      <fieldset disabled={saving} className="grid gap-4 sm:grid-cols-2">{section.fields.map(field => {
        const id = `config-field-${field.key}`;
        const shared = { id, disabled: Boolean(editor.id && field.createOnly), 'aria-invalid': Boolean(fieldErrors[field.key]), 'aria-describedby': `${id}-help ${id}-error`, required: !field.optional, className: inputClass };
        return <div key={field.key} className={field.type === 'textarea' ? 'sm:col-span-2' : ''}>
          <label htmlFor={id} className="mb-2 block text-sm text-slate-600">{field.label}{!field.optional && field.type !== 'checkbox' ? ' *' : ''}</label>
          {field.key === 'platform_dentist' && dentists.length ? <select {...shared} value={form[field.key]} onChange={event => setForm(previous => ({ ...previous, [field.key]: event.target.value }))}><option value="">Choisir un dentiste</option>{dentists.map(d => <option key={d.id} value={d.id}>{d.name}</option>)}</select> : field.options ? <select {...shared} value={form[field.key]} onChange={event => setForm(previous => ({ ...previous, [field.key]: event.target.value }))}>{field.options.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select> : field.type === 'textarea' ? <textarea {...shared} rows={3} value={form[field.key]} onChange={event => setForm(previous => ({ ...previous, [field.key]: event.target.value }))} /> : field.type === 'checkbox' ? <input id={id} type="checkbox" checked={Boolean(form[field.key])} onChange={event => setForm(previous => ({ ...previous, [field.key]: event.target.checked }))} className="h-5 w-5 accent-sky-400" /> : <input {...shared} type={field.type || 'text'} min={field.min} step={field.step} maxLength={field.maxLength} value={field.decimal ? quantityInput(form[field.key]) : form[field.key]} onChange={event => { if (!field.decimal || acceptsQuantity(event.target.value)) setForm(previous => ({ ...previous, [field.key]: field.decimal ? event.target.value.replace(',', '.') : event.target.value })); }} />}
          <p id={`${id}-help`} className="mt-1 text-xs text-slate-500">{field.hint}</p>
          <p id={`${id}-error`} className="mt-1 text-xs text-red-700">{[].concat(fieldErrors[field.key] || []).join(' ')}</p>
        </div>;
      })}</fieldset>
      {fieldErrors.non_field_errors && <p role="alert" className="text-sm text-red-700">{[].concat(fieldErrors.non_field_errors).join(' ')}</p>}
      <div className="flex justify-end gap-3"><button type="button" disabled={saving} onClick={() => setEditor(null)} className={buttonClass}>Annuler</button><button disabled={saving} className="rounded-xl bg-teal-600 px-4 py-2 text-sm font-semibold hover:bg-teal-700 disabled:opacity-40">{saving ? 'Enregistrement…' : 'Enregistrer'}</button></div>
    </form>}
    {deleting && <div role="alert" className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-red-400/20 bg-red-400/10 p-4 text-sm"><p>Supprimer « {rowName(deleting)} » ? Cette action est définitive.</p><div className="flex gap-3"><button type="button" disabled={saving} onClick={() => setDeleting(null)} className={buttonClass}>Annuler</button><button type="button" disabled={saving} onClick={remove} className="rounded-xl bg-red-500 px-3 py-2 disabled:opacity-40">{saving ? 'Suppression…' : 'Confirmer la suppression'}</button></div></div>}
    <div className="flex flex-wrap items-center gap-3"><input type="search" aria-label={`Rechercher dans ${section.label}`} placeholder="Rechercher dans les fiches…" value={query} onChange={event => setQuery(event.target.value)} className={`${inputClass} sm:max-w-sm`} /><button type="button" disabled={loading || saving} onClick={refresh} className={buttonClass}>Actualiser</button><span className="text-xs text-slate-500">{visibleRows.length} fiche(s)</span></div>
    <div aria-busy={loading} className="overflow-x-auto rounded-xl border border-slate-200/80"><table className="w-full min-w-[640px] text-left text-sm"><caption className="sr-only">{section.label} du laboratoire</caption><thead className="bg-white text-xs uppercase tracking-wide text-slate-500"><tr>{section.columns.map(([key, label]) => <th scope="col" key={key} className="px-4 py-3 font-medium">{label}</th>)}<th scope="col" className="px-4 py-3 text-right font-medium">Actions</th></tr></thead><tbody>
      {loading ? <tr><td colSpan={section.columns.length + 1} role="status" className="p-10 text-center text-slate-500">Chargement…</td></tr> : !visibleRows.length ? <tr><td colSpan={section.columns.length + 1} className="p-10 text-center text-slate-500">{error ? 'Les fiches ne sont pas disponibles.' : query ? 'Aucun résultat pour cette recherche.' : 'Aucune fiche. Ajoutez votre première entrée.'}</td></tr> : visibleRows.map(row => <tr key={row.id} className="border-t border-slate-200/80 text-slate-600 hover:bg-white">{section.columns.map(([key]) => <td key={key} className="max-w-xs whitespace-pre-line break-words px-4 py-4">{cellValue(section, row, key)}</td>)}<td className="px-4 py-4"><div className="flex justify-end gap-2"><button type="button" disabled={saving || !canWrite} aria-label={`Modifier ${rowName(row)}`} onClick={() => openEditor(row)} className={buttonClass}>Modifier</button><button type="button" disabled={saving || !canWrite || section.endpoint === 'inventory'} title={section.endpoint === 'inventory' ? 'Historique de stock conservé' : undefined} aria-label={`Supprimer ${rowName(row)}`} onClick={() => { setDeleting(row); setEditor(null); setNotice(''); }} className={`${buttonClass} text-red-700`}>Supprimer</button></div></td></tr>)}
    </tbody></table></div>
  </section>;
}

export function LaboratoryResource({ resource, labelledBy }) {
  const key = resource === 'materials' ? 'stock' : resource;
  const section = resource === 'materials' ? { ...sections.stock, label: 'Matériaux', description: 'Catalogue des matières et consommables pour la fabrication des prothèses.' } : sections[key];
  return <ResourceTable active={`inventory-${resource}`} labelledBy={labelledBy} section={section} />;
}

export default function LabBusinessConfiguration({ target }) {
  const [active, setActive] = useState('personnel');
  const [legacy, setLegacy] = useState(Boolean(target));
  if (legacy) return <div className="space-y-5"><button type="button" onClick={() => setLegacy(false)} className={buttonClass}>← Configuration métier</button><LabConfiguration target={target} /></div>;
  return <div className="space-y-6">
    <div className="flex flex-wrap items-start justify-between gap-4"><div><p className="text-xs font-semibold uppercase tracking-[0.2em] text-teal-700">Administration du laboratoire</p><h1 className="mt-2 text-2xl font-semibold tracking-tight sm:text-3xl">Configuration</h1><p className="mt-2 text-sm text-slate-500">Organisez les ressources et les partenaires de votre laboratoire.</p></div><button type="button" onClick={() => setLegacy(true)} className={buttonClass}>Anciennes fiches</button></div>
    <div role="tablist" aria-label="Configuration du laboratoire" className="flex gap-1 overflow-x-auto rounded-xl border border-slate-200/80 bg-slate-50 p-1 backdrop-blur-md">{tabs.map(key => <button key={key} type="button" role="tab" id={`config-tab-${key}`} aria-controls={`config-panel-${key}`} aria-selected={active === key} tabIndex={active === key ? 0 : -1} onClick={() => setActive(key)} onKeyDown={event => {
      if (!['ArrowRight', 'ArrowLeft', 'Home', 'End'].includes(event.key)) return;
      event.preventDefault();
      const index = tabs.indexOf(key);
      const next = event.key === 'Home' ? tabs[0] : event.key === 'End' ? tabs.at(-1) : tabs[(index + (event.key === 'ArrowRight' ? 1 : -1) + tabs.length) % tabs.length];
      setActive(next); document.getElementById(`config-tab-${next}`)?.focus();
    }} className={`flex-1 whitespace-nowrap rounded-lg px-5 py-3 text-sm font-medium focus-visible:outline-2 focus-visible:outline-sky-400 ${active === key ? 'bg-slate-100 text-slate-900 shadow-sm' : 'text-slate-500 hover:bg-white hover:text-slate-900'}`}>{sections[key].label}</button>)}</div>
    <ResourceTable key={active} active={active} section={sections[active]} />
  </div>;
}
