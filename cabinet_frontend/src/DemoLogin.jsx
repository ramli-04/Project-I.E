import { useEffect, useState } from 'react';
import { ArrowRight } from 'lucide-react';
import platform from './api/platform';
import { useTenant } from './contexts/useTenant';
import logo from './assets/logo.png';

const inputClass = 'mt-2 w-full rounded-xl border border-white/15 bg-slate-950 px-3 py-3 text-sm text-white outline-none focus:border-sky-400 focus:ring-1 focus:ring-sky-400 disabled:opacity-50';
const portals = [['LAB', 'Laboratoire'], ['DENTIST', 'Dentiste'], ['COURIER', 'Coursier'], ['ADMIN', 'Administration']];

export default function DemoLogin({ setUser }) {
  const [portal, setPortal] = useState('LAB');
  const [name, setName] = useState('');
  const [password, setPassword] = useState('');
  const [laboratory, setLaboratory] = useState('');
  const [laboratories, setLaboratories] = useState([]);
  const [loadingLabs, setLoadingLabs] = useState(true);
  const [labError, setLabError] = useState('');
  const [retry, setRetry] = useState(0);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const { setTenant, clearTenant } = useTenant();
  const needsLab = portal === 'LAB' || portal === 'COURIER';

  useEffect(() => {
    const controller = new AbortController();
    platform.get('laboratories/', { signal: controller.signal }).then(({ data }) => {
      if (!controller.signal.aborted) setLaboratories(data);
    }).catch(() => {
      if (!controller.signal.aborted) setLabError('Impossible de charger les laboratoires. Vérifiez que le serveur est démarré.');
    }).finally(() => { if (!controller.signal.aborted) setLoadingLabs(false); });
    return () => controller.abort();
  }, [retry]);

  async function submit(event) {
    event.preventDefault();
    if (busy) return;
    setBusy(true); setError('');
    try {
      let user;
      {
        const { data } = await platform.post('login/', { name: name.trim(), password, role: portal, ...(needsLab ? { laboratory } : {}) });
        const role = { ADMIN: 'Administrateur', DENTIST: 'Cabinet Dentaire', LAB: 'Laboratoire', COURIER: 'Coursier' }[data.account.role];
        user = { id: data.account.id, name: data.account.name, role, email: data.account.email, workstation_role: data.account.workstation_role };
        if (data.account.laboratory_id) setTenant(data.account.laboratory_id, data.account.laboratory_name);
        else clearTenant();
        sessionStorage.setItem('demo_token', data.token);
      }
      sessionStorage.setItem('demo_user', JSON.stringify(user)); setUser(user);
    } catch (err) {
      setError(err.response?.data?.detail || (portal === 'COURIER' ? err.message : 'Connexion impossible. Vérifiez votre identification, l’espace choisi et la connexion au serveur.'));
    } finally { setBusy(false); }
  }

  return <div className="flex min-h-screen items-center justify-center bg-[#0d0914] p-4 text-white sm:p-6"><section className="w-full max-w-lg rounded-3xl border border-white/10 bg-slate-900/50 p-6 shadow-2xl backdrop-blur-md sm:p-8">
    <img src={logo} alt="Cabinet 2.0" className="mx-auto mb-6 h-24 object-contain" />
    <h1 className="text-center text-2xl font-semibold">Votre espace Cabinet 2.0</h1><p className="mt-3 text-center text-sm text-slate-400">Choisissez votre espace, puis identifiez-vous.</p>
    <form onSubmit={submit} className="mt-7 space-y-5"><fieldset disabled={busy} className="space-y-5">
      <label className="block text-sm text-slate-300" htmlFor="login-portal">Votre espace<select id="login-portal" value={portal} onChange={event => { setPortal(event.target.value); setName(''); setError(''); }} className={inputClass}>{portals.map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select></label>
      {needsLab && <div><label htmlFor="login-laboratory" className="block text-sm text-slate-300">Laboratoire<select id="login-laboratory" required disabled={loadingLabs || Boolean(labError)} value={laboratory} onChange={event => { setLaboratory(event.target.value); setError(''); }} className={inputClass}><option value="">{loadingLabs ? 'Chargement…' : 'Choisir un laboratoire'}</option>{laboratories.map(lab => <option key={lab.identifier} value={lab.identifier}>{lab.name}</option>)}</select></label>
        {labError ? <p role="alert" className="mt-2 text-xs text-red-300">{labError} <button type="button" onClick={() => { setLoadingLabs(true); setLabError(''); setRetry(value => value + 1); }} className="underline">Réessayer</button></p> : !loadingLabs && !laboratories.length && <p role="status" className="mt-2 text-xs text-amber-300">Aucun laboratoire disponible. Contactez l’administration.</p>}
      </div>}
      <label htmlFor="login-name" className="block text-sm text-slate-300">{portal === 'COURIER' ? 'Nom du coursier' : 'Votre identification'}<input id="login-name" autoComplete="username" required maxLength={150} pattern=".*\S.*" value={name} onChange={event => setName(event.target.value)} placeholder={portal === 'LAB' || portal === 'COURIER' ? 'Mohamed' : portal === 'DENTIST' ? 'Dentiste 1' : 'Admin'} className={inputClass} />{portal === 'LAB' && <span className="mt-2 block text-xs text-slate-500">Exemple : sélectionnez Labo 1 et saisissez simplement Mohamed.</span>}</label>
      <label htmlFor="login-password" className="block text-sm text-slate-300">Mot de passe<input id="login-password" type="password" autoComplete="current-password" required maxLength={256} value={password} onChange={event => setPassword(event.target.value)} className={inputClass} /></label>
    </fieldset>
    {error && <p role="alert" className="rounded-xl border border-red-400/20 bg-red-400/10 p-3 text-sm text-red-300">{error}</p>}
    <button disabled={busy || (needsLab && (loadingLabs || Boolean(labError) || !laboratory))} className="flex w-full items-center justify-center gap-2 rounded-xl bg-sky-500 px-4 py-3 font-medium hover:bg-sky-400 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-sky-400 disabled:opacity-50">{busy ? 'Connexion…' : 'Accéder à mon espace'}<ArrowRight aria-hidden="true" className="h-4 w-4" /></button></form>
    <p className="mt-6 text-xs leading-relaxed text-slate-400">Accès personnel sécurisé. Pour obtenir un compte ou réinitialiser votre mot de passe, contactez l’administration.</p>
  </section></div>;
}
