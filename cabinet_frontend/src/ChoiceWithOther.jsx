import { useState } from 'react';
import { control, Field } from './IntegrationUI';

import { OTHER } from './prescriptionOptions';

// A dropdown of common values plus "Autre…", which reveals a free-text input.
// The stored value is always the plain text sent to the server.
export default function ChoiceWithOther({ label, value, onChange, options, maxLength, disabled = false }) {
  // "Autre…" stays open while empty; any non-listed value (e.g. copied from another tooth) also shows it.
  const [otherChosen, setOther] = useState(false);
  const other = (otherChosen && !options.includes(value)) || (Boolean(value) && !options.includes(value));
  const selected = other ? OTHER : options.includes(value) ? value : '';
  return <div className="space-y-2">
    <Field label={label}><select className={control} required disabled={disabled} value={selected} onChange={event => {
      const next = event.target.value;
      setOther(next === OTHER);
      onChange(next === OTHER ? '' : next);
    }}><option value="">Choisir</option>{options.map(option => <option key={option} value={option}>{option}</option>)}<option value={OTHER}>Autre…</option></select></Field>
    {other && <Field label={`${label} (autre)`}><input className={control} required disabled={disabled} maxLength={maxLength} value={value} onChange={event => onChange(event.target.value)} /></Field>}
  </div>;
}
