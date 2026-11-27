import { control, Field } from './IntegrationUI';
import { composeReasonNote, splitReasonNote } from './technicianNotes';

export default function ReasonNote({ label, value, onChange, presets, disabled = false, required = false }) {
  const { preset, detail } = splitReasonNote(value, presets);
  const remaining = 2000 - (preset ? preset.text.length + 1 : 0);
  return <div className="space-y-3">
    <Field label={`${label} — motif prédéfini`}><select className={control} disabled={disabled} value={preset?.id || ''} onChange={event => onChange(composeReasonNote(presets.find(row => row.id === event.target.value), detail))}>
      <option value="">Choisir un motif ou saisir une note libre</option>
      {presets.map(row => <option key={row.id} value={row.id}>{row.label}</option>)}
    </select></Field>
    <Field label={preset ? 'Précision (facultative)' : required ? 'Note libre (obligatoire)' : 'Note libre (facultative)'}><textarea aria-label={label} aria-required={required && !preset || undefined} className={control} rows={2} disabled={disabled} value={detail} maxLength={remaining} onChange={event => onChange(composeReasonNote(preset, event.target.value))} /></Field>
    {required && <p className="text-xs text-slate-600">Un motif prédéfini ou une note est obligatoire pour cette action.</p>}
    {value.length > 2000 && <p role="alert" className="text-sm text-red-700">La note doit contenir au maximum 2 000 caractères.</p>}
  </div>;
}
