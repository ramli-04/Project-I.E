import { useState } from 'react';
import platform from './api/platform';

export default function SupportButton() {
  const [open, setOpen] = useState(false);
  const [subject, setSubject] = useState('');
  const [message, setMessage] = useState('');
  const [status, setStatus] = useState('');
  const [busy, setBusy] = useState(false);
  async function send(event) {
    event.preventDefault(); setBusy(true); setStatus('');
    try { await platform.post('support/', { subject, message }); setSubject(''); setMessage(''); setStatus('Signalement envoyé à l’administrateur.'); }
    catch { setStatus('Envoi impossible. Réessayez.'); }
    finally { setBusy(false); }
  }
  return <div className="relative"><button onClick={() => setOpen(!open)} aria-expanded={open} className="rounded-xl border border-slate-200/80 px-3 py-2 text-sm text-slate-500 hover:text-slate-900">Assistance</button>{open && <section aria-label="Signaler un problème" className="absolute right-0 top-full mt-3 w-80 max-w-[85vw] rounded-2xl border border-slate-200 bg-white p-5 shadow-2xl"><h2 className="font-semibold">Signaler un problème technique</h2><form onSubmit={send} className="mt-4 space-y-3"><input aria-label="Sujet du problème" required maxLength={150} value={subject} onChange={event => setSubject(event.target.value)} placeholder="Sujet" className="w-full rounded-xl border border-slate-200 bg-slate-50 p-3 text-sm" /><textarea aria-label="Description du problème" required maxLength={5000} rows={4} value={message} onChange={event => setMessage(event.target.value)} placeholder="Décrivez le problème rencontré…" className="w-full rounded-xl border border-slate-200 bg-slate-50 p-3 text-sm" />{status && <p role="status" className="text-xs text-teal-700">{status}</p>}<div className="flex justify-end gap-3"><button type="button" onClick={() => setOpen(false)} className="text-sm text-slate-500">Fermer</button><button disabled={busy} className="rounded-xl bg-teal-600 px-3 py-2 text-sm disabled:opacity-50">{busy ? 'Envoi…' : 'Envoyer'}</button></div></form></section>}</div>;
}
