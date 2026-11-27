import { useEffect, useState } from 'react';
import { Button, control, Field } from './IntegrationUI';
import { frenchMessage, labelFor } from './api/messages';
import { labDate, labDateTime, labLongDate, labTime, taskLabels } from './planningTime';
import FilePicker from './FilePicker';
import LotPanel from './LotPanel';
import { explainAssignment } from './planningExplain';
import ReasonNote from './ReasonNote';
import { clinicalNotePresets, progressNotePresets } from './technicianNotes';
import { assignmentPending, checksByStage, dentistProgressText, latestInspection, phaseLabels, plannedPrefix, taskWaitReason } from './caseWorkspaceHelpers';

export function PrimaryButton(props) {
  return <Button {...props} data-primary-action className={`bg-teal-700 text-white ${props.className || ''}`} />;
}
export function WaitingNotice({ children }) {
  return <p className="rounded-xl border border-slate-200 bg-slate-50 p-4 text-sm text-slate-600">{frenchMessage(children)}</p>;
}
export function AcceptAction({ order, busy, command }) {
  return <div className="space-y-3"><p className="text-sm text-slate-600">Vérifiez la prescription et les documents avant de poursuivre.</p>
    {order.accepted ? <PrimaryButton disabled={busy} onClick={() => command('advance')}>Passer à l’analyse</PrimaryButton>
      : <PrimaryButton disabled={busy} onClick={() => command('accept')}>Accepter et analyser</PrimaryButton>}
  </div>;
}
export function ConfirmAction({ order, busy, command, evidence, attachments, notes, setNotes }) {
  const stage = order.current_step.inspection_stages?.[0];
  const analysis = order.status === 'ANALYSE_DEMANDE';
  return <div className="space-y-4">
    <PrimaryButton disabled={busy || !order.accepted} onClick={() => command('advance', { [order.current_step.confirm_field]: true })}>{analysis ? 'Analyse validée' : 'Réception confirmée'} → {order.current_step.next_label}</PrimaryButton>
    {!analysis && order.intake_version >= 2 && <details><summary>Contrôler les éléments reçus ou signaler une non-conformité</summary><div className="mt-4"><InspectAction order={order} stage={stage} busy={busy} command={command} evidence={evidence} attachments={attachments} notes={notes} setNotes={setNotes} confirmOnly /></div></details>}
  </div>;
}
export function PlanAction({ order, busy, command }) {
  const [method, setMethod] = useState(order.production_method || '');
  const [treatment, setTreatment] = useState(order.thermal_treatment || 'AUCUN');
  const [date, setDate] = useState(order.delivery_date || labDate(order.deadline_at));
  const [dateEdited, setDateEdited] = useState(false);
  const suggested = order.delivery_date || labDate(order.deadline_at);
  const value = dateEdited ? date : suggested;
  const target = order.current_step.planning_options?.[method];
  if (order.delivery_service === 'NEXT_DAY' && order.total_price == null) return <WaitingNotice>Devis J+1 requis par la comptabilité.</WaitingNotice>;
  return <div className="space-y-4"><div className="grid gap-4 sm:grid-cols-2"><Field label="Méthode de fabrication"><select className={control} value={method} onChange={e => setMethod(e.target.value)}><option value="">Choisir une méthode</option><option value="CFAO">CFAO / usinage CNC</option><option value="IMPRESSION_3D">Impression 3D</option><option value="CONVENTIONNEL">Fabrication conventionnelle</option></select></Field>
    <Field label="Livraison prévue"><input className={control} type="date" value={value} onChange={e => { setDateEdited(true); setDate(e.target.value); }} required /></Field></div>
    <p className="text-sm text-slate-600">{order.deadline_at ? `Échéance calculée : ${labLongDate(order.deadline_at)}` : 'Échéance en cours de calcul'}</p>
    {method === 'CFAO' && <Field label="Traitement après usinage"><select className={control} value={treatment} onChange={e => setTreatment(e.target.value)}><option value="AUCUN">Sans traitement thermique</option><option value="FRITTAGE">Frittage</option><option value="CRISTALLISATION">Cristallisation</option><option value="CUISSON">Cuisson</option></select></Field>}
    {method && !target?.next_label && <WaitingNotice>Actualisez le dossier pour charger la destination de ce parcours.</WaitingNotice>}
    <PrimaryButton disabled={busy || !method || !value || !target?.next_label} onClick={() => command('advance', { production_method: method, thermal_treatment: method === 'CFAO' ? treatment : 'AUCUN', delivery_date: value })}>Planifier{target?.next_label ? ` → ${target.next_label}` : ''}</PrimaryButton>
  </div>;
}
export function InspectAction({ order, stage = order.current_step.inspection_stages?.[0], busy, command, evidence, attachments, notes, setNotes, confirmOnly = false, onRework }) {
  const [checks, setChecks] = useState({}); const [photo, setPhoto] = useState(''); const [gap, setGap] = useState(false); const [repeat, setRepeat] = useState(false);
  const latest = latestInspection(order, evidence, stage);
  if (!checksByStage[stage]) return <WaitingNotice>Les critères du contrôle ne sont pas disponibles. Actualisez le dossier.</WaitingNotice>;
  if (latest?.passed && !repeat) return <div className="space-y-4"><p className="text-sm text-emerald-800">Contrôle conforme enregistré pour cette {stage === 'QUALITY' ? 'tentative' : 'révision'}.</p><Button onClick={() => setRepeat(true)}>Recontrôler</Button>{!confirmOnly && <PrimaryButton disabled={busy} onClick={() => command('advance')}>Valider → {order.current_step.next_label}</PrimaryButton>}</div>;
  if (latest?.passed === false && ['MODEL', 'QUALITY'].includes(stage) && !repeat) return <div className="space-y-4"><WaitingNotice>Contrôle non conforme enregistré. Documentez la cause et l’action corrective avant la reprise.</WaitingNotice><PrimaryButton disabled={busy} onClick={onRework}>Documenter la reprise</PrimaryButton><Button onClick={() => setRepeat(true)}>Recontrôler</Button></div>;
  const failed = !Object.keys(checksByStage[stage]).every(key => checks[key] === true);
  const advance = !failed && !gap && !confirmOnly;
  const SubmitButton = confirmOnly ? Button : PrimaryButton;
  async function submit() {
    const success = await command('inspection', { stage, checks: { ...Object.fromEntries(Object.keys(checksByStage[stage]).map(key => [key, checks[key] === true])), gap }, photo: photo || null, notes, ...(advance ? { advance: true } : {}) });
    if (success) { setChecks({}); setGap(false); setPhoto(''); setRepeat(false); }
  }
  return <div className="space-y-4"><h4 className="font-medium">Inspection · {labelFor(stage)}</h4>
    <fieldset className="space-y-3"><legend className="text-sm text-slate-600">Critères contrôlés</legend>
      <Button onClick={() => setChecks(Object.fromEntries(Object.keys(checksByStage[stage]).map(key => [key, true])))}>Tout conforme</Button>
      <div className="grid gap-3 sm:grid-cols-2">{Object.entries(checksByStage[stage]).map(([key, label]) => <label key={key} className="flex gap-3 text-sm"><input type="checkbox" checked={checks[key] === true} onChange={e => setChecks({ ...checks, [key]: e.target.checked })} />{label} conforme</label>)}</div>
    </fieldset>
    <label className="flex flex-wrap gap-3 rounded-xl border border-amber-200 bg-amber-50/60 p-3 text-sm"><input type="checkbox" checked={gap} onChange={e => setGap(e.target.checked)} />Écart nécessitant une photo<span className="text-xs text-slate-500">(signalement indépendant des critères)</span></label>
    <ReasonNote label="Notes et motif de l’action" value={notes} onChange={setNotes} presets={clinicalNotePresets(order, stage)} required={failed} />
    {(failed || gap) && <Field label="Photo de preuve (obligatoire en cas d’échec ou d’écart)"><select className={control} value={photo} onChange={e => setPhoto(e.target.value)}><option value="">Choisir</option>{attachments.filter(a => a.kind === 'PHOTO').map(a => <option key={a.id} value={a.id}>{a.original_name}</option>)}</select></Field>}
    {repeat && <Button onClick={() => setRepeat(false)}>Conserver le contrôle enregistré</Button>}
    <SubmitButton disabled={busy} onClick={submit}>{failed ? 'Enregistrer la non-conformité' : advance ? `Valider le contrôle → ${order.current_step.next_label}` : 'Enregistrer le contrôle'}</SubmitButton>
  </div>;
}
// Human acknowledgements remain explicit throughout the equipment cycle.
export function EquipmentControls({ task, busy, notes, command, ActionButton = Button }) {
  const phase = task.resource_phase;
  if (!phase || phase === 'MANUAL') return null;
  return <div className="mt-3 space-y-2"><p className="text-sm font-semibold">{phaseLabels[phase]}</p><p className="text-xs text-slate-500">Estimations : chargement {task.setup_minutes} min · cycle {task.estimated_duration_minutes - task.setup_minutes - task.unload_minutes} min · déchargement {task.unload_minutes} min. Une fin de cycle ne valide jamais la qualité clinique.</p>
    {task.can_operate && task.source_status === task.workflow_step && task.status === 'IN_PROGRESS' && <div className="flex flex-wrap gap-2">
      {phase === 'SETUP' && <ActionButton disabled={busy} onClick={() => command(task, 'launch-cycle')}>Chargement terminé : lancer le cycle</ActionButton>}
      {phase === 'CYCLE' && <ActionButton disabled={busy || !notes.trim()} onClick={() => command(task, 'cycle-finished')}>Confirmer la fin réelle du cycle</ActionButton>}
      {phase === 'AWAITING_UNLOAD' && <ActionButton disabled={busy} onClick={() => command(task, 'begin-unload')}>Commencer le déchargement</ActionButton>}
      {phase === 'UNLOADING' && <ActionButton disabled={busy} onClick={() => command(task, 'complete')}>Confirmer le déchargement et terminer</ActionButton>}
    </div>}
  </div>;
}
export function WorkAction({ order, task, tasks, busy, planningCommand, progressNotes, setProgressNotes, lots = [], createLot, role }) {
  const [supervised, setSupervised] = useState(false);
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => { const timer = setInterval(() => setNow(Date.now()), 1000); return () => clearInterval(timer); }, []);
  const reason = taskWaitReason(order, task, tasks, now);
  const future = task?.planned_start && Date.parse(task.planned_start) > now;
  const canSupervise = task?.can_start_now && task?.can_operate && task?.assigned_employee && ['READY', 'SCHEDULED', 'PAUSED', 'BLOCKED'].includes(task.status) && task.planned_start && (!reason || future && reason.startsWith(plannedPrefix));
  const pending = assignmentPending(task, tasks);
  const window = task?.planned_start && task?.planned_end ? (Date.parse(task.planned_end) - Date.parse(task.planned_start)) / 60000 : 0;
  const duration = task && (task.resource_phase && task.resource_phase !== 'MANUAL' && window > task.estimated_duration_minutes + 5
    ? `${task.estimated_duration_minutes} min de travail · machine réservée ${labTime(task.planned_start)}–${labTime(task.planned_end)}`
    : `${task.estimated_duration_minutes} min`);
  const allowed = !reason || Boolean(canSupervise && supervised);
  const start = ['READY', 'SCHEDULED'].includes(task?.status);
  const resume = ['PAUSED', 'BLOCKED'].includes(task?.status);
  return <div className="planning-step space-y-4"><div><strong>{task?.title || order.current_step.label}</strong><p>{task?.employee_name || (pending ? 'Affectation en cours…' : 'Responsable à affecter')}{task && ` · tentative ${task.production_attempt} · ${duration}`}</p>{task && <span className="text-xs text-teal-800">{pending ? 'Affectation en cours…' : taskLabels[task.status]}</span>}</div>
    {task?.assigned_employee && explainAssignment(task) && <p className="text-xs text-slate-600"><strong>Pourquoi cette affectation ?</strong> {explainAssignment(task)}</p>}
    {task && <p className="planning-times">Prévu : {labDateTime(task.planned_start)} → {labDateTime(task.planned_end)}<br />Réel : {labDateTime(task.actual_start)} → {labDateTime(task.actual_end)}</p>}
    {reason && <WaitingNotice>{reason}</WaitingNotice>}
    {canSupervise && <p className="text-sm text-teal-800">Vous pouvez commencer maintenant : cochez le démarrage supervisé et indiquez le motif.</p>}
    {task?.blocking_reason && !reason && !pending && <WaitingNotice>{task.blocking_reason}</WaitingNotice>}
    {order.current_step?.next_requires_lot && createLot && ['MANAGER', 'FAO'].includes(role) && <LotPanel order={order} lots={lots} busy={busy} createLot={createLot} />}
    {canSupervise && <label className="flex gap-3 text-sm"><input type="checkbox" checked={supervised} onChange={e => setSupervised(e.target.checked)} />Démarrage supervisé par le responsable</label>}
    {task?.can_operate && task.assigned_employee && !['COMPLETED', 'CANCELLED'].includes(task.status) && <ReasonNote label="Commentaire de progression / motif du blocage" value={progressNotes} onChange={setProgressNotes} presets={progressNotePresets(task)} required={task.resource_phase === 'CYCLE' || supervised && canSupervise} />}
    {allowed && task && <>
      {(start || resume) && <PrimaryButton disabled={busy || supervised && !progressNotes.trim()} onClick={async () => { if (await planningCommand(task, resume ? 'resume' : 'start', supervised ? { start_now: true } : {})) setSupervised(false); }}>{supervised ? 'Démarrer maintenant et replanifier' : resume ? 'Reprendre' : 'Démarrer'}</PrimaryButton>}
      {task.status === 'IN_PROGRESS' && (!task.resource_phase || task.resource_phase === 'MANUAL') && <PrimaryButton disabled={busy} onClick={() => planningCommand(task, 'complete')}>Terminer l’étape</PrimaryButton>}
      <EquipmentControls task={task} busy={busy} notes={progressNotes} command={planningCommand} ActionButton={PrimaryButton} />
    </>}
  </div>;
}
export function ReworkAction(props) { return <WorkAction {...props} />; }
export function DesignAction(props) {
  const [chosen, setChosen] = useState(''); const [file, setFile] = useState(null);
  const { order, busy, command, attachments, notes, setNotes, upload } = props;
  const designs = attachments.filter(a => a.kind === 'DESIGN');
  const latest = designs.reduce((last, row) => !last || Date.parse(row.created_at || 0) >= Date.parse(last.created_at || 0) ? row : last, null);
  const attachment = chosen || latest?.id || '';
  if (!order.design_validation_requested) return <WorkAction {...props} />;
  return <div className="space-y-4"><p className="text-sm text-slate-600">Téléversez le fichier de design, vérifiez la version puis soumettez-la au dentiste.</p>
    {upload && <div className="flex flex-wrap items-end gap-3"><FilePicker label="Fichier de design · 25 Mo maximum" file={file} onChange={setFile} accept=".stl,.jpg,.jpeg,.png,.pdf" disabled={busy} /><Button disabled={busy || !file} onClick={async () => { if (await upload(file, 'DESIGN')) { setFile(null); setChosen(''); } }}>Téléverser le design</Button></div>}
    <Field label="Version de design téléversée"><select className={control} value={attachment} onChange={e => setChosen(e.target.value)}><option value="">Choisir</option>{designs.map(a => <option key={a.id} value={a.id}>{a.original_name}</option>)}</select></Field>
    <ReasonNote label="Notes et motif de l’action" value={notes} onChange={setNotes} presets={clinicalNotePresets(order, null)} />
    <PrimaryButton disabled={busy || !attachment} onClick={() => command('design-request', { attachment, notes })}>Soumettre au dentiste et suspendre le délai</PrimaryButton>
  </div>;
}
export function DentistAction({ order, evidence, notes, setNotes, pin, setPin, busy, command, downloadFile }) {
  const [decision, setDecision] = useState('APPROVED');
  if (order.status === 'EN_ROUTE_CABINET') return <div className="space-y-4"><Field label="PIN de livraison"><input className={control} inputMode="numeric" maxLength={4} value={pin} onChange={e => setPin(e.target.value.replace(/\D/g, ''))} /></Field><PrimaryButton disabled={busy || !/^\d{4}$/.test(pin)} onClick={() => command('confirm-delivery', { pin })}>Valider le PIN</PrimaryButton></div>;
  if (order.status === 'VALIDATION_CAO') {
    const review = evidence?.design_reviews?.find(row => row.status === 'PENDING');
    if (!review) return <WaitingNotice>Aucune validation de design en attente. Actualisez le dossier ou contactez le laboratoire.</WaitingNotice>;
    return <div className="space-y-4"><p className="text-sm">Version {review.version} à examiner</p><Button onClick={() => downloadFile(`attachment/${review.attachment_id}/`, `design-v${review.version}`)}>Consulter le design</Button>
      <Field label="Décision du design"><select className={control} value={decision} onChange={e => setDecision(e.target.value)}><option value="APPROVED">Approuver</option><option value="CHANGES_REQUESTED">Demander des corrections</option></select></Field>
      <ReasonNote label="Notes et motif de l’action" value={notes} onChange={setNotes} presets={clinicalNotePresets(order, null, true)} required={decision === 'CHANGES_REQUESTED'} />
      <PrimaryButton disabled={busy || decision === 'CHANGES_REQUESTED' && !notes.trim()} onClick={() => command('design-decision', { review: review.id, decision, notes })}>{decision === 'APPROVED' ? 'Approuver' : 'Demander des corrections'}</PrimaryButton>
    </div>;
  }
  if (['LIVRE', 'ESSAYAGE', 'RETOUR_DEMANDE'].includes(order.status)) return <div className="space-y-4"><ReasonNote label="Notes et motif de l’action" value={notes} onChange={setNotes} presets={clinicalNotePresets(order, null, true)} />
    {order.status === 'RETOUR_DEMANDE' ? <><p className="text-sm text-slate-600">Corrigez les documents dans Dossier avant de soumettre la nouvelle révision.</p><PrimaryButton disabled={busy} onClick={() => command('resubmit', { notes })}>Soumettre à nouveau après correction des documents</PrimaryButton></>
      : <PrimaryButton disabled={busy} onClick={() => command('fitting', { passed: true, notes })}>Valider l’essayage clinique</PrimaryButton>}
  </div>;
  return <WaitingNotice>{dentistProgressText(order)}</WaitingNotice>;
}
