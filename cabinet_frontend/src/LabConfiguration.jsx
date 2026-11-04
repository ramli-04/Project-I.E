import { useEffect, useState } from 'react';
import { Users, Settings, Package, Plus, Pencil, Trash2, Search, X, AlertTriangle } from 'lucide-react';
import api from './api/client';

const availability = [['DISPONIBLE', 'Disponible'], ['OCCUPE', 'Occupé'], ['ABSENT', 'Absent']];
const equipmentAvailability = [['DISPONIBLE', 'Disponible'], ['EN_SERVICE', 'En service'], ['MAINTENANCE', 'Maintenance'], ['HORS_SERVICE', 'Hors service']];
const accountStatus = [['A_CREER', 'À créer'], ['ACTIF', 'Actif'], ['SUSPENDU', 'Suspendu']];
const today = () => {
  const date = new Date();
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`;
};
const sections = {
  staff: {
    title: 'Personnel', singular: 'une personne', icon: Users,
    description: 'Équipe, rôles, qualifications et disponibilités.',
    fields: [
      { key: 'reference', label: 'Matricule / ID', required: true, maxLength: 50, placeholder: 'PERS-001' },
      { key: 'name', label: 'Nom complet', required: true, maxLength: 120 },
      { key: 'contract_end_date', label: 'Date de fin de contrat', type: 'date' },
      { key: 'qualification_expiry_date', label: 'Validité des qualifications jusqu’au', type: 'date' },
      { key: 'role', label: 'Rôle', required: true, maxLength: 80, placeholder: 'Prothésiste, responsable CFAO…' },
      { key: 'qualifications', label: 'Qualifications', type: 'textarea', placeholder: 'Diplômes, compétences, habilitations…' },
      { key: 'email', label: 'E-mail', type: 'email', maxLength: 254 },
      { key: 'phone', label: 'Téléphone', type: 'tel', maxLength: 30 },
      { key: 'account_username', label: 'Identifiant du compte', maxLength: 100 },
      { key: 'account_status', label: 'Statut du compte', options: accountStatus, default: 'A_CREER' },
      { key: 'availability', label: 'Disponibilité', options: availability, default: 'DISPONIBLE' },
      { key: 'schedule', label: 'Horaires de travail', maxLength: 255, placeholder: 'Lun–Ven, 09:00–18:00' },
      { key: 'available_from', label: 'Disponible à partir du', type: 'date' },
    ],
    columns: [['name', 'Personnel'], ['role', 'Rôle et qualifications'], ['account_status', 'Compte'], ['availability', 'Disponibilité']],
  },
  equipment: {
    title: 'Matériel', singular: 'un appareil', icon: Settings,
    description: 'Parc des appareils, capacités et tâches réalisables.',
    fields: [
      { key: 'reference', label: 'ID de l’appareil', required: true, maxLength: 50, placeholder: 'CNC-001' },
      { key: 'name', label: 'Nom de l’appareil', required: true, maxLength: 120 },
      { key: 'availability', label: 'Disponibilité', options: equipmentAvailability, default: 'DISPONIBLE' },
      { key: 'capacity', label: 'Capacité', type: 'number', required: true, min: 1, step: 1 },
      { key: 'capacity_unit', label: 'Unité de capacité', required: true, maxLength: 60, default: 'éléments / cycle', placeholder: 'éléments / cycle, pièces / jour…' },
      { key: 'tasks', label: 'Tâches réalisées', type: 'textarea', required: true, placeholder: 'Usinage zircone, frittage, numérisation…' },
      { key: 'available_from', label: 'Disponible à partir du', type: 'date' },
      { key: 'maintenance_date', label: 'Prochaine maintenance', type: 'date' },
    ],
    columns: [['name', 'Appareil'], ['capacity', 'Capacité et tâches'], ['availability', 'Disponibilité'], ['maintenance_date', 'Maintenance']],
  },
  stock: {
    title: 'Stock', singular: 'un article', icon: Package,
    description: 'Articles, lots, quantités et dates de réception / péremption.',
    fields: [
      { key: 'reference', label: 'Référence / ID', required: true, maxLength: 50, placeholder: 'ZIR-001' },
      { key: 'name', label: 'Nom de l’article', required: true, maxLength: 120 },
      { key: 'quantity', label: 'Quantité en stock', type: 'number', required: true, min: 0, step: '0.01', default: '0' },
      { key: 'unit', label: 'Unité', required: true, maxLength: 30, default: 'pièces', placeholder: 'pièces, disques, g, ml…' },
      { key: 'minimum_quantity', label: 'Seuil d’alerte', type: 'number', required: true, min: 0, step: '0.01', default: '0' },
      { key: 'lot_number', label: 'Numéro de lot', maxLength: 80 },
      { key: 'received_date', label: 'Date de réception', type: 'date', required: true, default: today },
      { key: 'expiry_date', label: 'Date de péremption', type: 'date' },
    ],
    columns: [['name', 'Article'], ['quantity', 'Quantité'], ['received_date', 'Réception'], ['expiry_date', 'Péremption']],
  },
};
const initialForm = (section) => Object.fromEntries(section.fields.map(field => [field.key, typeof field.default === 'function' ? field.default() : field.default ?? '']));
const dateLabel = value => value ? new Intl.DateTimeFormat('fr-FR').format(new Date(`${value}T12:00:00`)) : '—';
const labelFor = (options, value) => options.find(([key]) => key === value)?.[1] || value;
const isLow = item => Number(item.quantity) <= Number(item.minimum_quantity);
const isExpired = item => Boolean(item.expiry_date && item.expiry_date < today());
const inputClass = 'w-full rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-sm text-slate-900 outline-none focus:border-sky-400 focus:ring-1 focus:ring-sky-400 disabled:opacity-50';
const fetchConfiguration = async () => Object.fromEntries(await Promise.all(Object.keys(sections).map(async key => [key, (await api.get(`${key}/`)).data])));

function Badge({ children, warning = false }) {
  return <span className={`inline-flex rounded-full border px-2.5 py-1 text-xs ${warning ? 'border-amber-400/30 bg-amber-400/10 text-amber-700' : 'border-sky-400/20 bg-sky-400/10 text-teal-800'}`}>{children}</span>;
}

function Cell({ section, field, row }) {
  const detail = value => value && <div className="mt-1 text-xs text-slate-500 whitespace-pre-line break-words">{value}</div>;
  if (field === 'name') return <><div className="font-medium text-slate-900">{row.name}</div>{detail(row.reference)}{section === 'staff' && detail([row.email, row.phone].filter(Boolean).join(' · '))}{section === 'stock' && detail(row.lot_number && `Lot : ${row.lot_number}`)}</>;
  if (field === 'role') return <>{row.role}{detail(row.qualifications)}{row.contract_end_date && detail(`Fin de contrat : ${dateLabel(row.contract_end_date)}`)}{row.qualification_expiry_date && detail(`Qualifications valides jusqu’au : ${dateLabel(row.qualification_expiry_date)}`)}</>;
  if (field === 'account_status') return <><Badge warning={row.account_status !== 'ACTIF'}>{labelFor(accountStatus, row.account_status)}</Badge>{detail(row.account_username)}</>;
  if (field === 'availability') return <><Badge warning={row.availability !== 'DISPONIBLE'}>{labelFor(section === 'staff' ? availability : equipmentAvailability, row.availability)}</Badge>{detail(row.schedule)}{row.available_from && detail(`À partir du ${dateLabel(row.available_from)}`)}</>;
  if (field === 'capacity') return <>{row.capacity} {row.capacity_unit}{detail(row.tasks)}</>;
  if (field === 'quantity') return <><div>{Number(row.quantity).toLocaleString('fr-FR')} {row.unit}</div>{detail(`Seuil : ${Number(row.minimum_quantity).toLocaleString('fr-FR')} ${row.unit}`)}{isLow(row) && <div className="mt-2"><Badge warning>Stock bas</Badge></div>}</>;
  if (field === 'expiry_date') return <>{dateLabel(row.expiry_date)}{isExpired(row) && <div className="mt-2"><Badge warning>Périmé</Badge></div>}</>;
  return dateLabel(row[field]);
}

export default function LabConfiguration({ target }) {
  const [active, setActive] = useState(target?.section || 'staff');
  const [data, setData] = useState({ staff: [], equipment: [], stock: [] });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [query, setQuery] = useState('');
  const [editor, setEditor] = useState(null);
  const [form, setForm] = useState({});
  const [fieldErrors, setFieldErrors] = useState({});
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState(null);
  const section = sections[active];

  async function load() {
    setLoading(true);
    setError('');
    try {
      setData(await fetchConfiguration());
    } catch {
      setError('Impossible de charger la configuration. Vérifiez la connexion au laboratoire puis réessayez.');
    } finally { setLoading(false); }
  }
  useEffect(() => {
    let cancelled = false;
    fetchConfiguration().then(result => {
      if (!cancelled) {
        setData(result);
        if (target) {
          const row = result[target.section]?.find(item => item.id === target.id);
          if (row) {
            setEditor({ id: row.id });
            setForm(Object.fromEntries(sections[target.section].fields.map(field => [field.key, row[field.key] ?? ''])));
          } else setError('La fiche à l’origine de cette alerte a été supprimée.');
        }
      }
    }).catch(() => {
      if (!cancelled) setError('Impossible de charger la configuration. Vérifiez la connexion au laboratoire puis réessayez.');
    }).finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [target]);

  function openEditor(row = null) {
    setEditor({ id: row?.id ?? null });
    setForm(row ? Object.fromEntries(section.fields.map(field => [field.key, row[field.key] ?? ''])) : initialForm(section));
    setFieldErrors({}); setNotice(''); setError(''); setDeleting(null);
  }
  function switchSection(key) {
    setActive(key); setQuery(''); setEditor(null); setDeleting(null); setNotice(''); setFieldErrors({});
  }
  async function save(event) {
    event.preventDefault();
    setSaving(true); setFieldErrors({}); setError(''); setNotice('');
    const payload = Object.fromEntries(section.fields.map(field => [field.key, field.type === 'date' && !form[field.key] ? null : typeof form[field.key] === 'string' ? form[field.key].trim() : form[field.key]]));
    try {
      const response = editor.id ? await api.patch(`${active}/${editor.id}/`, payload) : await api.post(`${active}/`, payload);
      setData(previous => ({ ...previous, [active]: editor.id ? previous[active].map(row => row.id === editor.id ? response.data : row) : [...previous[active], response.data] }));
      setEditor(null); setNotice('Enregistrement effectué.');
      window.dispatchEvent(new Event('lab-resources-changed'));
    } catch (err) {
      setFieldErrors(err.response?.data || {});
      setError('Enregistrement impossible. Vérifiez les champs ou votre connexion.');
    } finally { setSaving(false); }
  }
  async function remove() {
    setSaving(true); setError(''); setNotice('');
    try {
      await api.delete(`${active}/${deleting.id}/`);
      setData(previous => ({ ...previous, [active]: previous[active].filter(row => row.id !== deleting.id) }));
      setDeleting(null); setNotice('Suppression effectuée.');
      window.dispatchEvent(new Event('lab-resources-changed'));
    } catch { setError('Suppression impossible. Réessayez.'); }
    finally { setSaving(false); }
  }
  const rows = data[active].filter(row => section.fields.some(field => String(row[field.key] ?? '').toLocaleLowerCase('fr').includes(query.toLocaleLowerCase('fr'))));
  const summary = [
    ['Personnel disponible', `${data.staff.filter(row => row.availability === 'DISPONIBLE').length} / ${data.staff.length}`, Users],
    ['Appareils disponibles', `${data.equipment.filter(row => row.availability === 'DISPONIBLE').length} / ${data.equipment.length}`, Settings],
    ['Articles à surveiller', data.stock.filter(row => isLow(row) || isExpired(row)).length, AlertTriangle],
  ];

  return <div className="space-y-6">
    <div><h2 className="text-2xl font-semibold">Configuration du laboratoire</h2><p className="mt-2 text-sm text-slate-500">Organisez les ressources de votre laboratoire et suivez leur disponibilité.</p></div>
    <div className="grid gap-4 md:grid-cols-3">{summary.map(([label, count, Icon]) => <div key={label} className="rounded-2xl border border-slate-200/80 bg-white p-5"><div className="flex items-center justify-between text-sm text-slate-500">{label}<Icon className="h-5 w-5 text-teal-700" /></div><div className="mt-3 text-2xl font-semibold">{loading ? '—' : count}</div></div>)}</div>
    <div className="rounded-2xl border border-slate-200/80 bg-white overflow-hidden">
      <div className="flex flex-wrap gap-2 border-b border-slate-200/80 p-3" role="tablist" aria-label="Configuration du laboratoire">{Object.entries(sections).map(([key, config]) => <button key={key} role="tab" aria-selected={active === key} disabled={saving} onClick={() => switchSection(key)} className={`flex items-center gap-2 rounded-xl px-4 py-2 text-sm transition-colors ${active === key ? 'bg-teal-600/15 text-teal-700' : 'text-slate-500 hover:bg-white hover:text-slate-900'}`}><config.icon className="h-4 w-4" />{config.title}<span className="rounded-md bg-slate-100 px-1.5 text-xs">{loading ? '—' : data[key].length}</span></button>)}</div>
      <div className="space-y-5 p-5">
        {error && <div role="alert" className="rounded-xl border border-red-400/30 bg-red-400/10 p-3 text-sm text-red-800">{error} {!editor && <button onClick={load} className="ml-2 underline">Réessayer</button>}</div>}
        {notice && <div role="status" className="rounded-xl bg-emerald-500/10 p-3 text-sm text-emerald-700">{notice}</div>}
        <div className="flex flex-wrap items-center justify-between gap-4"><div><h3 className="font-semibold">{section.title}</h3><p className="mt-1 text-sm text-slate-500">{section.description}</p></div><button disabled={loading || saving} onClick={() => openEditor()} className="flex items-center gap-2 rounded-xl bg-teal-600 px-4 py-2.5 text-sm font-medium text-slate-900 hover:bg-teal-700 disabled:opacity-50"><Plus className="h-4 w-4" />Ajouter {section.singular}</button></div>
        {editor && <form onSubmit={save} className="rounded-2xl border border-sky-400/20 bg-slate-50 p-5 space-y-4">
          <div className="flex justify-between gap-3"><h4 className="font-semibold">{editor.id ? 'Modifier la fiche' : `Ajouter ${section.singular}`}</h4><button type="button" disabled={saving} onClick={() => setEditor(null)} aria-label="Fermer le formulaire"><X className="h-5 w-5" /></button></div>
          {active === 'staff' && <p className="text-xs text-slate-500">Le compte est suivi à titre administratif. La connexion de démonstration n’applique pas encore les rôles et statuts saisis ici.</p>}
          <p className="text-xs text-slate-500">* Champ obligatoire</p>
          <fieldset disabled={saving} className="grid gap-4 md:grid-cols-2">{section.fields.map(field => <div key={field.key} className={field.type === 'textarea' ? 'md:col-span-2' : ''}>
            <label htmlFor={`config-${field.key}`} className="mb-1.5 block text-sm text-slate-600">{field.label}{field.required ? ' *' : ''}</label>
            {field.options ? <select id={`config-${field.key}`} value={form[field.key]} onChange={event => setForm({ ...form, [field.key]: event.target.value })} className={inputClass}>{field.options.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select> : field.type === 'textarea' ? <textarea id={`config-${field.key}`} rows={3} required={field.required} placeholder={field.placeholder} value={form[field.key]} onChange={event => setForm({ ...form, [field.key]: event.target.value })} className={inputClass} /> : <input id={`config-${field.key}`} type={field.type || 'text'} required={field.required || (field.key === 'account_username' && form.account_status === 'ACTIF')} min={field.key === 'expiry_date' ? form.received_date || undefined : field.min} step={field.step} maxLength={field.maxLength} placeholder={field.placeholder} value={form[field.key]} onChange={event => setForm({ ...form, [field.key]: event.target.value })} className={inputClass} />}
            {fieldErrors[field.key] && <p role="alert" className="mt-1 text-xs text-red-700">{[].concat(fieldErrors[field.key]).join(' ')}</p>}
          </div>)}</fieldset>
          {fieldErrors.non_field_errors && <p role="alert" className="text-sm text-red-700">{[].concat(fieldErrors.non_field_errors).join(' ')}</p>}
          <div className="flex justify-end gap-3"><button type="button" disabled={saving} onClick={() => setEditor(null)} className="rounded-xl border border-slate-200 px-4 py-2 text-sm">Annuler</button><button disabled={saving} className="rounded-xl bg-teal-600 px-4 py-2 text-sm font-medium disabled:opacity-50">{saving ? 'Enregistrement…' : 'Enregistrer'}</button></div>
        </form>}
        {deleting && <div role="alert" className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-red-400/30 bg-red-400/10 p-4 text-sm"><span>Supprimer définitivement « {deleting.name} » ({deleting.reference}) ?</span><div className="flex gap-3"><button disabled={saving} onClick={() => setDeleting(null)}>Annuler</button><button disabled={saving} onClick={remove} className="rounded-lg bg-red-500 px-3 py-2">{saving ? 'Suppression…' : 'Supprimer'}</button></div></div>}
        <div className="relative"><Search className="absolute left-3 top-3 h-4 w-4 text-slate-500" /><input aria-label={`Rechercher dans ${section.title}`} value={query} onChange={event => setQuery(event.target.value)} placeholder="Rechercher par nom, ID, rôle, tâche…" className={`${inputClass} pl-10`} /></div>
        {loading ? <p role="status" className="py-10 text-center text-sm text-slate-500">Chargement de la configuration…</p> : rows.length === 0 ? <div className="py-10 text-center text-slate-500"><section.icon className="mx-auto mb-3 h-8 w-8 text-slate-600" /><p>{query ? 'Aucun résultat pour cette recherche.' : `Aucune fiche dans ${section.title.toLowerCase()} pour le moment.`}</p>{!query && <p className="mt-2 text-sm">Utilisez le bouton Ajouter pour créer votre première fiche.</p>}</div> : <div className="overflow-x-auto"><table className="w-full min-w-[720px] text-left text-sm"><thead><tr className="border-b border-slate-200/80 text-xs uppercase tracking-wide text-slate-500">{section.columns.map(([key, label]) => <th key={key} scope="col" className="px-3 py-3 font-medium">{label}</th>)}<th scope="col" className="px-3 py-3 text-right font-medium">Actions</th></tr></thead><tbody>{rows.map(row => <tr key={row.id} className="border-b border-slate-100 align-top text-slate-600 hover:bg-slate-50">{section.columns.map(([key]) => <td key={key} className="max-w-xs break-words px-3 py-4"><Cell section={active} field={key} row={row} /></td>)}<td className="px-3 py-4"><div className="flex justify-end gap-2"><button disabled={saving} onClick={() => openEditor(row)} aria-label={`Modifier ${row.name}`} className="rounded-lg p-2 text-slate-500 hover:bg-teal-600/10 hover:text-teal-700"><Pencil className="h-4 w-4" /></button><button disabled={saving} onClick={() => { setDeleting(row); setEditor(null); setNotice(''); }} aria-label={`Supprimer ${row.name}`} className="rounded-lg p-2 text-slate-500 hover:bg-red-500/10 hover:text-red-700"><Trash2 className="h-4 w-4" /></button></div></td></tr>)}</tbody></table></div>}
      </div>
    </div>
  </div>;
}
