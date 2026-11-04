import { useEffect, useState } from 'react';
import { Building2, Users, Activity, LifeBuoy, KeyRound, RefreshCw, X } from 'lucide-react';
import platform from './api/platform';

const control = 'w-full rounded-xl border border-white/15 bg-[#171321] px-3 py-2.5 text-sm text-white outline-none focus:border-sky-400';
const roles = { ADMIN: 'Administrateur', LAB: 'Laboratoire', DENTIST: 'Dentiste', COURIER: 'Coursier' };
const ticketLabels = { OPEN: 'Ouvert', IN_PROGRESS: 'En cours', RESOLVED: 'Résolu' };
const emptyAccount = { name: '', email: '', role: 'DENTIST', laboratory: '', is_active: true };
async function fetchAdminData() {
  const results = await Promise.all(['overview/', 'laboratories/', 'accounts/', 'logs/', 'support/'].map(url => platform.get(url)));
  return { overview: results[0].data, laboratories: results[1].data, accounts: results[2].data, logs: results[3].data, tickets: results[4].data };
}
function failure(err) {
  return err.response?.data ? Object.values(err.response.data).flat().join(' ') : 'Connexion au serveur impossible.';
}

export default function AdminPortal() {
  const [tab, setTab] = useState('overview');
  const [data, setData] = useState(null);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [busy, setBusy] = useState(false);
  const [lab, setLab] = useState({ name: '', identifier: '' });
  const [form, setForm] = useState(emptyAccount);
  const [editId, setEditId] = useState(null);
  const [resetId, setResetId] = useState(null);
  const [password, setPassword] = useState(null);
  useEffect(() => {
    let cancelled = false;
    fetchAdminData().then(result => { if (!cancelled) setData(result); }).catch(err => { if (!cancelled) setError(failure(err)); });
    return () => { cancelled = true; };
  }, []);
  async function refresh() {
    setBusy(true); setError('');
    try { setData(await fetchAdminData()); } catch (err) { setError(failure(err)); }
    finally { setBusy(false); }
  }
  async function mutate(action, message) {
    setBusy(true); setError(''); setNotice('');
    try { await action(); setData(await fetchAdminData()); setNotice(message); }
    catch (err) { setError(failure(err)); }
    finally { setBusy(false); }
  }
  function saveLab(event) {
    event.preventDefault();
    mutate(async () => { await platform.post('laboratories/', lab); setLab({ name: '', identifier: '' }); }, 'Laboratoire créé. Vous pouvez maintenant lui affecter des comptes.');
  }
  function saveAccount(event) {
    event.preventDefault();
    const payload = { ...form, laboratory: ['LAB', 'COURIER'].includes(form.role) ? Number(form.laboratory) : null };
    mutate(async () => {
      if (editId) await platform.patch(`accounts/${editId}/`, payload);
      else { const result = await platform.post('accounts/', payload); if (result.data.temporary_password) setPassword({ name: result.data.name, value: result.data.temporary_password }); }
      setForm(emptyAccount); setEditId(null);
    }, 'Compte enregistré. Le nom saisi permet la connexion automatique.');
  }
  function reset(account) {
    mutate(async () => {
      const response = await platform.post(`accounts/${account.id}/reset-password/`);
      if (response.data.token) sessionStorage.setItem('demo_token', response.data.token);
      setPassword({ name: account.name, value: response.data.temporary_password }); setResetId(null);
    }, 'Mot de passe réinitialisé. Les anciennes sessions de ce compte sont expirées.');
  }
  const tabs = [['overview', 'Vue d’ensemble', Activity], ['laboratories', 'Laboratoires', Building2], ['accounts', 'Comptes et affectations', Users], ['logs', 'Connexions et journal', Activity], ['support', 'Assistance', LifeBuoy]];
  return <div className="space-y-6"><div className="flex flex-wrap items-start justify-between gap-4"><div><p className="text-xs uppercase tracking-widest text-sky-400">Administration du projet</p><h1 className="mt-2 text-2xl font-semibold">Pilotage de la plateforme</h1><p className="mt-2 text-sm text-slate-400">Laboratoires, clients dentistes, affectations et assistance technique.</p></div><button disabled={busy} onClick={refresh} className="flex items-center gap-2 rounded-xl border border-white/15 px-4 py-2 text-sm text-slate-300 disabled:opacity-50"><RefreshCw className="h-4 w-4" />Actualiser</button></div>
    <p className="rounded-xl border border-sky-400/20 bg-sky-400/5 p-3 text-xs text-sky-200">Mode démonstration : la connexion se fait par nom, sans mot de passe. La réinitialisation prépare le futur accès par mot de passe.</p>
    <div className="flex flex-wrap gap-2 border-b border-white/10">{tabs.map(([key, label, Icon]) => <button key={key} onClick={() => setTab(key)} className={`flex items-center gap-2 border-b-2 px-3 py-3 text-sm ${tab === key ? 'border-sky-400 text-sky-300' : 'border-transparent text-slate-400'}`}><Icon className="h-4 w-4" />{label}</button>)}</div>
    {error && <p role="alert" className="rounded-xl bg-red-400/10 p-3 text-sm text-red-300">{error}</p>}{notice && <p role="status" className="rounded-xl bg-emerald-400/10 p-3 text-sm text-emerald-300">{notice}</p>}
    {password && <section aria-label="Mot de passe temporaire" className="rounded-xl border border-amber-400/30 bg-amber-400/5 p-4"><div className="flex justify-between gap-3"><h2 className="text-sm font-medium text-amber-200">Mot de passe temporaire — {password.name}</h2><button onClick={() => setPassword(null)} aria-label="Masquer le mot de passe"><X className="h-4 w-4" /></button></div><code className="mt-3 block select-all break-all text-lg">{password.value}</code><p className="mt-2 text-xs text-slate-400">Affiché uniquement ici ; aucun envoi automatique. Le mode démonstration reste sans mot de passe.</p></section>}
    {!data ? !error && <p className="py-10 text-sm text-slate-400">Chargement de l’administration…</p> : <>
      {tab === 'overview' && <><div className="grid gap-4 md:grid-cols-4">{[['Laboratoires', data.laboratories.length], ['Clients dentistes', data.overview.dentist_count], ['Comptes', data.overview.account_count], ['Incidents ouverts', data.overview.open_tickets]].map(([label, value]) => <div key={label} className="rounded-2xl border border-white/10 bg-white/5 p-5"><p className="text-sm text-slate-400">{label}</p><p className="mt-3 text-3xl font-semibold text-sky-300">{value}</p></div>)}</div><div className="grid gap-4 lg:grid-cols-2">{data.overview.laboratories.map(item => <section key={item.id} className="rounded-2xl border border-white/10 bg-white/[0.03] p-5"><h2 className="font-semibold">{item.name}</h2><p className="mt-1 text-xs text-slate-500">{item.identifier}</p><div className="mt-4 flex flex-wrap gap-5 text-sm text-slate-300"><span>{item.order_count} commande(s)</span><span>{item.paused_count} en pause</span><span>{item.account_count} compte(s) affecté(s)</span></div></section>)}</div></>}
      {tab === 'laboratories' && <div className="grid items-start gap-5 lg:grid-cols-[320px_1fr]"><form onSubmit={saveLab} className="rounded-2xl border border-white/10 bg-white/5 p-5 space-y-4"><h2 className="font-semibold">Ajouter un laboratoire</h2><label className="block space-y-2 text-sm text-slate-300"><span>Nom du laboratoire</span><input aria-label="Nom du laboratoire" required maxLength={100} className={control} value={lab.name} onChange={event => setLab({ ...lab, name: event.target.value })} /></label><label className="block space-y-2 text-sm text-slate-300"><span>Identifiant du labo</span><input aria-label="Identifiant du nouveau labo" required pattern="[a-z][a-z0-9]{0,29}" placeholder="labo4" className={control} value={lab.identifier} onChange={event => setLab({ ...lab, identifier: event.target.value })} /></label><p className="text-xs text-slate-500">Lettres minuscules et chiffres, sans espace. La création prépare son espace de données.</p><button disabled={busy} className="rounded-xl bg-sky-500 px-4 py-2 text-sm disabled:opacity-50">{busy ? 'Création…' : 'Créer le laboratoire'}</button></form><div className="space-y-3">{data.laboratories.map(item => <div key={item.id} className="flex justify-between rounded-xl border border-white/10 p-4"><span>{item.name}</span><span className="text-sm text-sky-300">{item.identifier}</span></div>)}</div></div>}
      {tab === 'accounts' && <div className="space-y-5"><form onSubmit={saveAccount} className="rounded-2xl border border-white/10 bg-white/5 p-5 space-y-4"><h2 className="font-semibold">{editId ? 'Modifier un compte' : 'Créer un compte'}</h2><div className="grid gap-4 md:grid-cols-2"><label className="space-y-2 text-sm text-slate-300"><span>Nom de connexion</span><input aria-label="Nom de connexion" required maxLength={120} className={control} value={form.name} onChange={event => setForm({ ...form, name: event.target.value })} /></label><label className="space-y-2 text-sm text-slate-300"><span>E-mail</span><input aria-label="E-mail du compte" type="email" className={control} value={form.email} onChange={event => setForm({ ...form, email: event.target.value })} /></label><label className="space-y-2 text-sm text-slate-300"><span>Type de compte</span><select aria-label="Type de compte" className={control} value={form.role} onChange={event => setForm({ ...form, role: event.target.value })}>{Object.entries(roles).map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select></label>{['LAB', 'COURIER'].includes(form.role) && <label className="space-y-2 text-sm text-slate-300"><span>Laboratoire affecté</span><select aria-label="Laboratoire affecté" required className={control} value={form.laboratory} onChange={event => setForm({ ...form, laboratory: event.target.value })}><option value="">Choisir un labo</option>{data.laboratories.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>}</div><label className="flex items-center gap-2 text-sm text-slate-300"><input type="checkbox" checked={form.is_active} onChange={event => setForm({ ...form, is_active: event.target.checked })} />Compte actif</label><div className="flex gap-3"><button disabled={busy} className="rounded-xl bg-sky-500 px-4 py-2 text-sm disabled:opacity-50">Enregistrer le compte</button>{editId && <button type="button" onClick={() => { setEditId(null); setForm(emptyAccount); }} className="text-sm text-slate-400">Annuler</button>}</div></form><div className="overflow-x-auto rounded-2xl border border-white/10"><table className="w-full min-w-[700px] text-left text-sm"><thead className="bg-white/5 text-slate-400"><tr>{['Compte', 'Type', 'Laboratoire', 'État', 'Actions'].map(label => <th key={label} className="p-4 font-medium">{label}</th>)}</tr></thead><tbody>{data.accounts.map(account => <tr key={account.id} className="border-t border-white/5"><td className="p-4">{account.name}<div className="mt-1 text-xs text-slate-500">{account.email}</div></td><td className="p-4 text-slate-400">{roles[account.role]}</td><td className="p-4 text-sky-300">{account.laboratory_name || '—'}</td><td className="p-4 text-slate-400">{account.is_active ? 'Actif' : 'Désactivé'}</td><td className="p-4"><div className="flex flex-wrap gap-3"><button disabled={busy} aria-label={`Modifier ${account.name}`} onClick={() => { setEditId(account.id); setForm({ name: account.name, email: account.email, role: account.role, laboratory: account.laboratory || '', is_active: account.is_active }); }} className="text-sky-300">Modifier</button><button disabled={busy} aria-label={`Réinitialiser le mot de passe de ${account.name}`} onClick={() => setResetId(account.id)} className="inline-flex items-center gap-1 text-amber-300"><KeyRound className="h-3 w-3" />Réinitialiser</button></div>{resetId === account.id && <div className="mt-3 space-y-2 text-xs text-amber-200"><p>Réinitialiser ce mot de passe et fermer les anciennes sessions ?</p><button disabled={busy} onClick={() => reset(account)} className="mr-3 underline">Confirmer</button><button onClick={() => setResetId(null)} className="text-slate-400">Annuler</button></div>}</td></tr>)}</tbody></table></div></div>}
      {tab === 'logs' && <div className="overflow-x-auto rounded-2xl border border-white/10"><p className="p-4 text-xs text-slate-500">200 événements les plus récents. Connexions de démonstration et actions d’administration.</p><table className="w-full min-w-[700px] text-left text-sm"><thead className="bg-white/5 text-slate-400"><tr>{['Date', 'Compte', 'Événement', 'Résultat', 'Détails'].map(label => <th key={label} className="p-3 font-medium">{label}</th>)}</tr></thead><tbody>{data.logs.map(log => <tr key={log.id} className="border-t border-white/5"><td className="p-3 text-xs text-slate-500">{new Date(log.created_at).toLocaleString('fr-FR')}</td><td className="p-3">{log.name}</td><td className="p-3 text-xs text-sky-300">{log.event}</td><td className={`p-3 text-xs ${log.success ? 'text-emerald-300' : 'text-red-300'}`}>{log.success ? 'Réussi' : 'Échec'}</td><td className="p-3 text-xs text-slate-400">{log.details}</td></tr>)}</tbody></table></div>}
      {tab === 'support' && <div className="space-y-4">{!data.tickets.length && <p className="py-10 text-sm text-slate-400">Aucun problème signalé.</p>}{data.tickets.map(ticket => <article key={ticket.id} className="rounded-2xl border border-white/10 p-5"><div className="flex flex-wrap justify-between gap-3"><div><h2 className="font-semibold">{ticket.subject}</h2><p className="mt-1 text-xs text-slate-500">{ticket.name}{ticket.laboratory ? ` · ${ticket.laboratory}` : ''} · {new Date(ticket.created_at).toLocaleString('fr-FR')}</p></div><select aria-label={`Statut du signalement ${ticket.id}`} disabled={busy} value={ticket.status} onChange={event => mutate(() => platform.patch(`support/${ticket.id}/`, { status: event.target.value }), 'Signalement mis à jour.')} className="rounded-lg border border-white/15 bg-[#171321] p-2 text-sm">{Object.entries(ticketLabels).map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select></div><p className="mt-4 whitespace-pre-wrap text-sm text-slate-300">{ticket.message}</p></article>)}</div>}
    </>}
  </div>;
}
