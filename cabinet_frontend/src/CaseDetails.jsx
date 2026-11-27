import platform from './api/platform';
import FilePicker from './FilePicker';
import { paymentStatusLabel } from './paymentHelpers';
import { useRef, useState } from 'react';
import { acceptsQuantity, errorText, money, quantityText } from './api/contracts';
import { frenchMessage, labelFor } from './api/messages';
import { Button, control, Feedback, Field, Panel } from './IntegrationUI';
import { labDateTime, taskLabels } from './planningTime';
import ReasonNote from './ReasonNote';
import { clinicalNotePresets, progressNotePresets } from './technicianNotes';
import { checksByStage, terminalTasks } from './caseWorkspaceHelpers';

export function CaseProblems({ order, dentist, role, evidence, usages, task, notes, progressNotes, busy, command, planningCommand }) {
  const [open, setOpen] = useState(false); const [reason, setReason] = useState('');
  const [origin, setOrigin] = useState('LAB'); const [cause, setCause] = useState(''); const [corrective, setCorrective] = useState(''); const [restart, setRestart] = useState('');
  const [losses, setLosses] = useState({}); const [attempt, setAttempt] = useState('');
  const can = roles => role === 'MANAGER' || roles.includes(role);
  const labProblems = !dentist && can(['RECEPTION', 'CAO', 'FAO', 'QUALITE']);
  const canRework = order.rework_restart_options?.length > 0 && (dentist ? ['LIVRE', 'ESSAYAGE', 'CLOTURE'].includes(order.status) : labProblems);
  const taskProblems = labProblems && task?.can_operate && !task.external && task.source_status === order.status && !terminalTasks.includes(task.status);
  const measuredLosses = () => Object.entries(losses).filter(([, value]) => value !== '' && Number(value) > 0).map(([usage_id, quantity]) => ({ usage_id, quantity }));
  const lossInput = usage => <Field key={usage.id} label={`Perte sur ${usage.material_name_snapshot} (maximum ${quantityText(-Number(usage.quantity_changed))} ${usage.unit_snapshot})`}><input className={control} type="number" min="0" max={-Number(usage.quantity_changed)} step="0.01" value={losses[usage.id] || ''} onChange={e => { if (acceptsQuantity(e.target.value)) setLosses({ ...losses, [usage.id]: e.target.value.replace(',', '.') }); }} /></Field>;
  async function send(action, data) { if (await command(action, { ...data, notes: reason })) { setReason(''); setLosses({}); } }
  return <details className="case-disclosure" open={open} onToggle={event => {
    const next = event.currentTarget.open; setOpen(next);
    if (next) setReason(value => value || progressNotes || notes);
  }}><summary>Signaler un problème</summary><fieldset disabled={busy} className="mt-5 space-y-5">
    <ReasonNote label="Motif du problème" value={reason} onChange={setReason} presets={task ? progressNotePresets(task) : clinicalNotePresets(order, order.current_step?.inspection_stages?.[0], dentist)} />
    <p className="text-xs text-slate-600">{dentist ? 'Un motif est obligatoire pour contester une ligne. Une reprise nécessite une cause et une action corrective.' : 'Un motif est obligatoire pour suspendre le dossier ou bloquer une tâche. Une reprise documentée nécessite une cause et une action corrective.'}</p>
    {labProblems && <div className="space-y-2"><p className="text-sm text-slate-600">La suspension du dossier est distincte de la pause d’une tâche et ne libère pas une machine chargée.</p>{!(order.is_paused && evidence?.design_reviews?.some(row => row.status === 'PENDING')) && <Button disabled={!order.is_paused && !reason.trim()} onClick={() => send('pause', { paused: !order.is_paused })}>{order.is_paused ? 'Reprendre le travail' : 'Suspendre avec motif'}</Button>}{order.is_paused && evidence?.design_reviews?.some(row => row.status === 'PENDING') && <p className="text-sm text-slate-600">La décision du dentiste est nécessaire avant la reprise.</p>}</div>}
    {taskProblems && <Panel title="Pause ou blocage de la tâche"><p className="text-sm text-slate-600">Un motif est obligatoire. Les réservations de l’équipement restent protégées.</p><div className="flex flex-wrap gap-3">{task.status === 'IN_PROGRESS' && <Button disabled={order.is_paused || !reason.trim()} onClick={async () => { if (await planningCommand(task, 'pause', {}, reason)) setReason(''); }}>Mettre en pause</Button>}<Button disabled={order.is_paused || !reason.trim()} onClick={async () => { if (await planningCommand(task, 'block', {}, reason)) setReason(''); }}>Bloquer la tâche</Button></div></Panel>}
    {!dentist && role === 'MANAGER' && (['WORK', 'REWORK'].includes(order.current_step?.kind) || order.current_step?.kind === 'DESIGN' && !order.design_validation_requested) && order.current_step.next_key && <div className="space-y-2"><p className="text-sm text-slate-600">Passage exceptionnel avec motif obligatoire. Les preuves cliniques, lots et confirmations de déchargement restent requis.</p><Button disabled={order.is_paused || !reason.trim()} onClick={() => send('advance', {})}>Forcer le passage à l’étape suivante</Button></div>}
    {canRework && <Panel title="Reprise liée au dossier d’origine"><p className="text-xs text-slate-500">Dossier {order.id} · tentative {order.production_attempt}. Laisser les pertes vides pour une correction sans perte mesurée.</p><div className="grid gap-3 sm:grid-cols-2"><Field label="Origine"><select className={control} data-rework-start value={origin} onChange={e => setOrigin(e.target.value)}><option value="LAB">Laboratoire</option><option value="CLINIC">Cabinet</option></select></Field><Field label="Étape de reprise"><select className={control} value={restart} onChange={e => setRestart(e.target.value)}><option value="">Choisir</option>{order.rework_restart_options.map(step => <option key={step.key} value={step.key}>{step.label}</option>)}</select></Field><Field label="Cause"><input className={control} value={cause} onChange={e => setCause(e.target.value)} /></Field><Field label="Action corrective"><input className={control} value={corrective} onChange={e => setCorrective(e.target.value)} /></Field></div>
      {!dentist && usages.filter(row => row.production_attempt === order.production_attempt && !row.source_history).map(lossInput)}
      <Button disabled={!restart || !cause.trim() || !corrective.trim()} onClick={() => send('rework', { origin, cause, corrective_action: corrective, restart_status: restart, losses: measuredLosses() })}>Enregistrer la reprise documentée</Button>
    </Panel>}
    {labProblems && evidence?.reworks?.length > 0 && <Panel title="Évaluer les pertes d’une reprise antérieure"><Field label="Tentative d’origine"><select className={control} value={attempt} onChange={e => { setAttempt(e.target.value); setLosses({}); }}><option value="">Choisir</option>{evidence.reworks.map(row => <option key={row.id} value={row.attempt}>{row.attempt} · {row.cause}</option>)}</select></Field>{usages.filter(row => String(row.production_attempt) === attempt).map(lossInput)}<Button disabled={!attempt || !measuredLosses().length} onClick={() => send('assess-loss', { attempt: Number(attempt), losses: measuredLosses() })}>Classer les pertes mesurées</Button></Panel>}
    {dentist && <Button disabled={!reason.trim()} onClick={() => send('dispute', {})}>Contester la ligne comptable</Button>}
    {!dentist && can(['RECEPTION', 'CAO', 'FAO', 'QUALITE', 'COMPTABILITE']) && <Button onClick={() => send('note', { workstation: role })}>Enregistrer la remarque du poste</Button>}
  </fieldset></details>;
}

export function CaseDossier({ order, dentist, role, evidence, attachments, tasks, busy, command, patch, upload, downloadFile, planningHistory, loadHistory, initiallyOpen = false }) {
  const can = roles => role === 'MANAGER' || roles.includes(role);
  const [file, setFile] = useState(null); const fileInput = useRef(null); const [kind, setKind] = useState('PHOTO');
  const [issues, setIssues] = useState(order.current_issues || ''); const [technical, setTechnical] = useState(order.technical_notes || ''); const [date, setDate] = useState(order.delivery_date || '');
  const [surcharge, setSurcharge] = useState(''); const [quoteNotes, setQuoteNotes] = useState('');
  const reception = !dentist && can(['RECEPTION']);
  const canSave = !dentist && can(['RECEPTION', 'CAO', 'FAO', 'QUALITE']);
  return <details className="case-disclosure" open={initiallyOpen || undefined}><summary>Dossier</summary><fieldset disabled={busy} className="mt-5 space-y-5">
    <div className="flex flex-wrap gap-3">{(dentist || can(['RECEPTION'])) && <Button onClick={() => downloadFile('qr/', `etiquette-${order.patient_ref}.png`, 'Étiquette téléchargée.')}>Étiquette QR</Button>}{dentist && <Button onClick={() => downloadFile('invoice/', `facture-${order.patient_ref}.pdf`, 'Facture téléchargée.')}>Facture PDF</Button>}{!dentist && ['CONDITIONNEMENT', 'PRET_EXPEDITION', 'EN_ROUTE_CABINET', 'LIVRE', 'ESSAYAGE', 'CLOTURE'].includes(order.status) && <Button onClick={() => downloadFile('delivery-slip/', `livraison-${order.patient_ref}.pdf`, 'Bon de livraison téléchargé.')}>Bon de livraison PDF</Button>}
      {dentist && !['LIVRE', 'ESSAYAGE', 'CLOTURE'].includes(order.status) && <Button onClick={() => command('issue-pin')}>Émettre un nouveau PIN de livraison</Button>}
    </div>
    {dentist && order.invoiced_at && <DentistInvoiceBalance key={`${order.laboratory_id}:${order.id}`} order={order} />}
    <Panel title="Documents privés"><div className="flex flex-wrap items-end gap-3"><Field label="Type"><select className={control} value={kind} onChange={e => setKind(e.target.value)}><option value="PHOTO">Photo</option><option value="STL">STL</option><option value="DESIGN">Design</option></select></Field><FilePicker label="Fichier · 25 Mo maximum" inputRef={fileInput} file={file} onChange={setFile} accept={kind === 'STL' ? '.stl' : kind === 'PHOTO' ? '.jpg,.jpeg,.png' : '.stl,.jpg,.jpeg,.png,.pdf'} /><Button disabled={!file} onClick={async () => { if (await upload(file, kind)) { setFile(null); if (fileInput.current) fileInput.current.value = ''; } }}>Téléverser</Button></div><ul className="space-y-2 text-sm">{attachments.map(row => <li key={row.id}><Button onClick={() => downloadFile(`attachment/${row.id}/`, row.original_name)}>{labelFor(row.kind)} · {row.original_name}</Button></li>)}</ul></Panel>
    {evidence?.design_reviews?.length > 0 && <Panel title="Validations du design">{evidence.design_reviews.map(row => <div key={row.id} className="space-y-2 border-b border-slate-200 pb-3 text-sm"><p>Version {row.version} · {labelFor(row.status)} · {row.response_notes}</p><Button onClick={() => downloadFile(`attachment/${row.attachment_id}/`, `design-v${row.version}`)}>Consulter le design</Button></div>)}</Panel>}
    {!dentist && <Panel title="Informations du dossier"><Field label="Problèmes actuels"><textarea className={control} value={issues} disabled={!reception} onChange={e => setIssues(e.target.value)} /></Field><Field label="Notes du dossier / consignes techniques"><textarea className={control} value={technical} disabled={!canSave} onChange={e => setTechnical(e.target.value)} /></Field><Field label="Livraison prévue (dossier)"><input className={control} type="date" value={date} disabled={!reception} onChange={e => setDate(e.target.value)} /></Field><Button disabled={!canSave} onClick={() => patch({ technical_notes: technical, ...(reception ? { current_issues: issues, delivery_date: date || null } : {}) })}>Enregistrer les informations</Button></Panel>}
    {!dentist && can(['COMPTABILITE']) && order.delivery_service === 'NEXT_DAY' && ['DEMANDE_RECUE', 'ANALYSE_DEMANDE', 'PLANIFICATION'].includes(order.status) && <Panel title="Devis manuel J+1"><p className="text-sm">Montant confirmé : {money(order.total_price)}</p><ReasonNote label="Motif du devis" value={quoteNotes} onChange={setQuoteNotes} presets={clinicalNotePresets(order, null)} /><Field label="Supplément urgence (MAD)"><input className={control} type="number" min="0" step="0.01" value={surcharge} onChange={e => setSurcharge(e.target.value)} /></Field><Button disabled={surcharge === ''} onClick={async () => { if (await command('quote', { surcharge, notes: quoteNotes })) { setSurcharge(''); setQuoteNotes(''); } }}>Confirmer le devis laboratoire</Button></Panel>}
    {evidence && <details><summary className="cursor-pointer text-sm text-teal-800">Historique et preuves</summary><div className="mt-3 space-y-4 text-xs text-slate-600">{['inspections', 'reworks', 'events', 'notifications'].map(key => <section key={key}><h3 className="font-medium">{({ inspections: 'Inspections', reworks: 'Reprises', events: 'Événements', notifications: 'Notifications' })[key]}</h3>{evidence[key]?.map((row, index) => <div className="my-2 break-words" key={row.id || index}><p>{labDateTime(row.created_at)} · {row.stage ? labelFor(row.stage) : row.origin ? ({ LAB: 'Laboratoire', CLINIC: 'Cabinet' })[row.origin] : 'Événement enregistré'} · {row.notes || row.cause || ''}</p>{row.checks && <p>{Object.entries(row.checks).map(([label, checked]) => `${checksByStage[row.stage]?.[label] || (label === 'gap' ? 'Écart' : 'Critère')} : ${checked ? 'oui' : 'non'}`).join(' · ')}</p>}{row.corrective_action && <p>Action corrective : {row.corrective_action}</p>}</div>)}</section>)}</div></details>}
    <details><summary className="cursor-pointer text-sm text-teal-800">Parcours détaillé</summary><ol className="mt-3 space-y-2 text-sm">{order.workflow_steps?.map(step => <li key={step.key} aria-current={step.key === order.status ? 'step' : undefined}>{step.label}</li>)}</ol></details>
    {!dentist && <><details><summary className="cursor-pointer text-sm text-teal-800">Toutes les tâches du parcours</summary><ol className="mt-3 space-y-2 text-xs">{[...tasks].sort((a, b) => a.production_attempt - b.production_attempt || a.sequence - b.sequence || a.generation - b.generation).map(task => <li key={task.id}>{task.title} · {task.employee_name || 'Responsable à affecter'} · {taskLabels[task.status] || 'État de la tâche indisponible'} · {labDateTime(task.planned_start)} → {labDateTime(task.planned_end)}{task.blocking_reason && <p>{frenchMessage(task.blocking_reason)}</p>}</li>)}</ol></details><details onToggle={e => { if (e.currentTarget.open) void loadHistory(); }}><summary className="cursor-pointer text-sm text-teal-800">Historique du planning</summary><ul className="mt-3 space-y-2 text-xs text-slate-600">{planningHistory.map(row => <li key={row.id}>{labDateTime(row.created_at)} · Événement du planning · {row.actor} · {row.notes || ''}</li>)}</ul></details></>}
  </fieldset></details>;
}


function DentistInvoiceBalance({ order }) {
  const [data, setData] = useState(null); const [busy, setBusy] = useState(false);
  const [error, setError] = useState(''); const [notice, setNotice] = useState('');
  async function load() {
    if (busy) return; setBusy(true); setError(''); setNotice('');
    try {
      const response = await platform.get(`dentist/orders/${order.laboratory_id}/${order.id}/invoice-balance/`);
      setData(response.data); setNotice('Solde actualisé.');
    } catch (cause) { setError(errorText(cause)); } finally { setBusy(false); }
  }
  return <Panel title="Solde de ma facture"><Feedback error={error} notice={notice} /><Button disabled={busy} onClick={load}>{data ? 'Actualiser le solde' : 'Consulter le solde'}</Button>
    {data && <div className="space-y-2 text-sm"><p>{paymentStatusLabel(data.payment_status)}</p><p>Reste à payer : {money(data.balance)}</p><p>Échéance : {new Date(`${data.due_date}T12:00:00Z`).toLocaleDateString('fr-FR', { timeZone: 'Africa/Casablanca' })} · délai {data.terms_days} jours</p>
      {Number(data.balance) > 0 && data.days_overdue > 0 && <p>En retard de {data.days_overdue} jours</p>}</div>}
  </Panel>;
}
