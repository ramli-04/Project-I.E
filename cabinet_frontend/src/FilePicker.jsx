import { useId, useRef } from 'react';

export default function FilePicker({ label, file, onChange, accept, inputRef, required = false, disabled = false }) {
  const id = 'file-picker-' + useId();
  const localInput = useRef(null);
  const button = useRef(null);
  const field = inputRef || localInput;
  return <div className="w-full min-w-0 sm:w-auto sm:flex-1">
    <label id={id + '-label'} htmlFor={id} className="mb-2 block text-sm text-slate-600">{label}</label>
    <div className="flex min-w-0 flex-wrap items-center gap-2 rounded-xl border border-slate-200 bg-white p-2">
      <button ref={button} type="button" disabled={disabled} aria-describedby={id + '-label ' + id + '-name'} onClick={() => field.current?.click()} className="shrink-0 rounded-lg border border-teal-200 px-3 py-2 text-sm text-teal-800 focus-visible:outline-2 focus-visible:outline-teal-600 disabled:opacity-50">Choisir un fichier</button>
      <span id={id + '-name'} aria-live="polite" className="min-w-0 flex-1 break-all text-sm text-slate-600">{file?.name || 'Aucun fichier sélectionné'}</span>
      <input id={id} ref={field} type="file" className="sr-only" tabIndex={-1} accept={accept} required={required} disabled={disabled} onInvalid={event => { event.preventDefault(); button.current?.focus(); }} onChange={event => onChange(event.target.files?.[0] || null)} />
    </div>
  </div>;
}
