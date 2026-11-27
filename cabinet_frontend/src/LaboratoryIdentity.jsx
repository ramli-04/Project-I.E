import { useEffect, useRef, useState } from 'react';
import api from './api/client';
import { workstation } from './api/contracts';
import { errorMessage, frenchMessage } from './api/messages';
import { notify } from './notifications';

const fields = [
  ['legal_name', 'Dénomination légale', 'text', 255],
  ['city', 'Ville du laboratoire', 'text', 120],
  ['address', 'Adresse du laboratoire', 'textarea'],
  ['phone', 'Téléphone du laboratoire', 'tel', 50],
  ['email', 'E-mail du laboratoire', 'email', 254],
  ['ice', 'ICE (15 chiffres)', 'text', 15],
  ['identifiant_fiscal', 'Identifiant fiscal (IF)', 'text', 50],
  ['registre_commerce', 'Registre du commerce (RC)', 'text', 50],
  ['patente', 'Patente', 'text', 50],
];
const draft = data => Object.fromEntries(fields.map(([key]) => [key, data?.[key] ?? '']));
const inputClass = 'w-full rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-sm read-only:bg-slate-50 focus-visible:outline-2 focus-visible:outline-teal-600';

export default function LaboratoryIdentity() {
  const role = workstation();
  const canRead = ['MANAGER', 'COMPTABILITE'].includes(role);
  const canWrite = role === 'MANAGER';
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState(() => draft());
  const [profile, setProfile] = useState(null);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [reload, setReload] = useState(0);
  const [error, setError] = useState('');
  const [fieldErrors, setFieldErrors] = useState({});
  const busy = useRef(false);
  const iceInput = useRef(null);

  useEffect(() => {
    if (!open || !canRead) return;
    const controller = new AbortController();
    api.get('laboratory-profile/', { signal: controller.signal, feedback: false })
      .then(({ data }) => {
        if (!controller.signal.aborted) { setProfile(data); setForm(draft(data)); setError(''); setFieldErrors({}); }
      }).catch(cause => {
        if (!controller.signal.aborted) { const message = errorMessage(cause); setError(message); notify(message, 'error'); }
      }).finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [open, canRead, reload]);

  async function save(event) {
    event.preventDefault();
    if (busy.current || !canWrite || loading) return;
    if (form.ice && !/^[0-9]{15}$/.test(form.ice)) {
      const message = 'L\u2019ICE doit contenir exactement 15 chiffres. Ce champ peut rester vide.';
      setFieldErrors({ ice: [message] }); setError(message); notify(message, 'error'); iceInput.current?.focus(); return;
    }
    busy.current = true; setSaving(true); setError(''); setFieldErrors({});
    const payload = Object.fromEntries(fields.map(([key]) => [key, key === 'ice' ? form[key] : form[key].trim()]));
    try {
      const { data } = await api.put('laboratory-profile/', payload, { feedback: false });
      setProfile(data); setForm(draft(data)); notify('Identit\u00e9 du laboratoire enregistr\u00e9e.');
    } catch (cause) {
      const message = errorMessage(cause);
      setFieldErrors(cause.response?.data ?? {}); setError(message); notify(message, 'error');
    } finally { busy.current = false; setSaving(false); }
  }

  if (!canRead) return null;
  return <details className="rounded-2xl border border-slate-200 bg-white p-4 sm:p-6" onToggle={event => {
    const next = event.currentTarget.open;
    if (next && !open) setLoading(true);
    setOpen(next);
  }}>
    <summary className="cursor-pointer font-semibold focus-visible:outline-2 focus-visible:outline-teal-600">Identité du laboratoire</summary>
    {open && <div className="mt-4 space-y-4">
      <p className="text-sm text-slate-600">Cette identité apparaît sur les nouveaux documents. Les champs fiscaux sont facultatifs. Sans dénomination, le nom du laboratoire est utilisé.</p>
      {!canWrite && <p className="text-sm font-medium text-teal-700">Lecture seule — seul le responsable peut modifier ces informations.</p>}
      {error && <p role="alert" className="text-sm text-red-700">{error}</p>}
      {loading ? <p role="status">Chargement de l’identité…</p> : !profile ? <button type="button" onClick={() => { setLoading(true); setReload(value => value + 1); }}>Réessayer le chargement</button> : <form aria-label="Identité du laboratoire" noValidate onSubmit={save} className="space-y-4">
        <fieldset disabled={saving} className="grid gap-4 sm:grid-cols-2">
          <legend className="sr-only">Coordonnées et identifiants du laboratoire</legend>
          {fields.map(([key, label, type, maxLength]) => {
            const id = 'lab-identity-' + key;
            const messages = [].concat(fieldErrors[key] ?? []).map(value => frenchMessage(value));
            const props = { id, value: form[key], readOnly: !canWrite, maxLength, className: inputClass,
              'aria-invalid': messages.length > 0, 'aria-describedby': messages.length ? id + '-error' : undefined,
              onChange: event => setForm(previous => ({ ...previous, [key]: event.target.value })) };
            return <div key={key} className={type === 'textarea' ? 'sm:col-span-2' : ''}>
              <label htmlFor={id} className="mb-1 block text-sm text-slate-700">{label}</label>
              {type === 'textarea' ? <textarea {...props} rows={2} /> : <input {...props} type={type} inputMode={key === 'ice' ? 'numeric' : undefined} ref={key === 'ice' ? iceInput : undefined} />}
              {messages.length > 0 && <p id={id + '-error'} className="mt-1 text-sm text-red-700">{messages.join(' ')}</p>}
            </div>;
          })}
        </fieldset>
        {profile.updated_at && <p className="text-xs text-slate-500">Dernière mise à jour : {new Intl.DateTimeFormat('fr-FR', { dateStyle: 'short', timeStyle: 'short', timeZone: 'Africa/Casablanca' }).format(new Date(profile.updated_at))}</p>}
        {canWrite && <button type="submit" disabled={saving} className="rounded-xl bg-teal-700 px-4 py-2.5 text-sm font-medium text-white disabled:opacity-50">{saving ? 'Enregistrement…' : 'Enregistrer l’identité'}</button>}
      </form>}
    </div>}
  </details>;
}
