import { useEffect, useId, useRef, useState } from 'react';
import api from './api/client';
import platform from './api/platform';
import { acceptsQuantity, allRows, download, errorText, quantityText, retryableRequest, workstation } from './api/contracts';
import { Button, control, Feedback, Field, Panel } from './IntegrationUI';
import ActionDialog from './ActionDialog';
import { labelFor } from './api/messages';
import ReasonNote from './ReasonNote';
import { clinicalNotePresets } from './technicianNotes';

const checksByStage = {
  PHYSICAL: { deformation: 'Absence de déformation', bubbles: 'Absence de bulles', limits: 'Limites lisibles', occlusion: 'Occlusion', hygiene: 'Hygiène' },
  DIGITAL: { margins: 'Marges', occlusion: 'Occlusion', space: 'Espace disponible', scan_quality: 'Qualité du scan' },
  MODEL: { model: 'Modèle', scan: 'Scan' },
  QUALITY: { margins: 'Marges', contacts: 'Contacts', shade: 'Teinte', occlusion: 'Occlusion', cosmetic: 'Esthétique', glazing: 'Glaçage', polishing: 'Polissage' },
};
const reworkStages = new Set(['SALLE_CAO','MODELE_TRAVAIL','COULEE_PLATRE','SCAN_LABO','CONTROLE_MODELE','PREPARATION_CNC','PREPARATION_3D','MODELAGE','FINITION','CONTROLE_QUALITE','LIVRE','ESSAYAGE','CLOTURE','USINAGE_CNC','IMPRESSION_3D','FABRICATION_MANUELLE','TRAITEMENT_THERMIQUE','FRITTAGE_9H','LAVAGE_SECHAGE','POST_POLYMERISATION']);

export default function BpmnCasePanel({ order, dentist = false, refresh, workflowControls, progress, autoOpen = false }) {
  const [open, setOpen] = useState(false); const [evidence, setEvidence] = useState(null); const [attachments, setAttachments] = useState([]);
  const [view, setView] = useState('clinical');
  const trigger = useRef(null); const tabsId = useId();
  const [usages, setUsages] = useState([]); const [busy, setBusy] = useState(false); const [error, setError] = useState(''); const [notice, setNotice] = useState('');
  const [notes, setNotes] = useState(''); const [pin, setPin] = useState(''); const [issuedPin, setIssuedPin] = useState('');
  const [kind, setKind] = useState('PHOTO'); const [file, setFile] = useState(null); const [designAttachment, setDesignAttachment] = useState('');
  const [checks, setChecks] = useState({}); const [photo, setPhoto] = useState(''); const [gap, setGap] = useState(false);
  const [origin, setOrigin] = useState('LAB'); const [cause, setCause] = useState(''); const [corrective, setCorrective] = useState(''); const [restart, setRestart] = useState('');
  const [losses, setLosses] = useState({}); const [attempt, setAttempt] = useState(''); const [surcharge, setSurcharge] = useState('');
  const request = useRef(retryableRequest()); const role = dentist ? 'DENTIST' : workstation();
  const can = roles => role === 'MANAGER' || roles.includes(role);
  const client = dentist ? platform : api;
  const base = dentist ? `dentist/orders/${order.laboratory_id}/${order.id}/` : `prescriptions/${order.id}/`;
  const stage = ['A_CONFIRMER', 'CONTROLE_DOSSIER'].includes(order.status) ? (order.impression_type === 'PHYSIQUE' ? 'PHYSICAL' : 'DIGITAL') : order.status === 'CONTROLE_MODELE' ? 'MODEL' : order.status === 'CONTROLE_QUALITE' ? 'QUALITY' : null;
  useEffect(() => {
    if (!open && !autoOpen) return;
    if (autoOpen) setOpen(true);
    setView(stage && order.status !== 'A_CONFIRMER' || order.design_validation_requested && ['SALLE_CAO', 'VALIDATION_CAO'].includes(order.status)
      ? 'clinical' : !workflowControls ? 'clinical' : ['ANALYSE_DEMANDE', 'A_CONFIRMER', 'PLANIFICATION', 'DEMANDE_RECUE'].includes(order.status) ? 'stage' : 'progress');
    setChecks({}); setGap(false); setPhoto(''); setError('');
    void perform(load, '');
  // Refresh evidence when a workflow command changes stage; do not reset a user's draft on polling.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [order.id, order.status, autoOpen]);
  async function load() {
    const [e, a, u] = await Promise.all([client.get(base + 'evidence/'), client.get(base + 'attachments/'), dentist ? [] : allRows(api, 'inventory-transactions/', { prescription: order.id })]);
    setEvidence(e.data); setAttachments(a.data); setUsages(u.filter(row => row.transaction_type === 'USAGE'));
  }
  async function perform(action, success = 'Action enregistrée.') {
    if (busy) return; setBusy(true); setError(''); setNotice('');
    try { await action(); setNotice(success); if (action !== load) { await load(); await refresh?.(); } }
    catch (e) { setError(errorText(e)); }
    finally { setBusy(false); }
  }
  const command = (action, data = {}) => perform(async () => {
    const response = await request.current(client, base + 'command/', { action, data });
    if (response.data.result?.pin_once) setIssuedPin(response.data.result.pin_once);
    if (action === 'confirm-delivery') setPin('');
    if (['rework', 'assess-loss'].includes(action)) setLosses({});
    if (action === 'inspection') { setChecks({}); setGap(false); setPhoto(''); }
    if (data.notes !== undefined) setNotes('');
  });
  const measuredLosses = () => Object.entries(losses).filter(([, quantity]) => quantity !== '' && Number(quantity) > 0).map(([usage_id, quantity]) => ({ usage_id, quantity }));
  const restartSteps = ['SALLE_CAO', 'FINITION', { CFAO: 'PREPARATION_CNC', IMPRESSION_3D: 'PREPARATION_3D', CONVENTIONNEL: 'MODELAGE' }[order.production_method] || 'COULEE_PLATRE', ...(order.impression_type === 'PHYSIQUE' ? ['COULEE_PLATRE', 'SCAN_LABO'] : [])];
  return <div className="space-y-4"><Button ref={trigger} onClick={() => { setOpen(true); setView('clinical'); void perform(load, 'Dossier chargé.'); }}>Ouvrir les documents et actions</Button>
    <Feedback error={error} notice={notice} />
    <ActionDialog open={open} busy={busy} returnFocus={trigger} onClose={() => setOpen(false)} title={`Dossier clinique — ${order.patient_ref}`}>
    <p className="mb-3 text-sm text-teal-800">{order.status_label || labelFor(order.status)}</p>
    {workflowControls && <nav className="clinical-dialog-tabs" role="tablist" aria-label="Sections du dossier clinique">
      {[['stage', 'Étape et choix techniques'], ['clinical', 'Contrôles et documents'], ['progress', 'Progression et machines']].map(([key, title], index) => <Button key={key} id={`${tabsId}-${key}`} role="tab" aria-controls={`${tabsId}-${key}-panel`} tabIndex={view === key ? 0 : -1} aria-selected={view === key} onClick={() => setView(key)} onKeyDown={event => {
        if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
        event.preventDefault(); const keys = ['stage', 'clinical', 'progress'];
        const next = event.key === 'Home' ? 0 : event.key === 'End' ? 2 : (index + (event.key === 'ArrowRight' ? 1 : 2)) % 3;
        setView(keys[next]); document.getElementById(`${tabsId}-${keys[next]}`)?.focus();
      }}>{title}</Button>)}
    </nav>}
    {issuedPin && <div role="status" className="rounded-xl bg-amber-400/10 p-4">Nouveau PIN, affiché une seule fois : <strong className="select-all font-mono">{issuedPin}</strong> <Button onClick={() => setIssuedPin('')}>Masquer</Button></div>}
    {workflowControls && <div id={`${tabsId}-stage-panel`} role="tabpanel" aria-labelledby={`${tabsId}-stage`} hidden={view !== 'stage'}>{workflowControls}</div>}
    {progress && <div id={`${tabsId}-progress-panel`} role="tabpanel" aria-labelledby={`${tabsId}-progress`} hidden={view !== 'progress'}>{progress}</div>}
    <fieldset id={`${tabsId}-clinical-panel`} role={workflowControls ? 'tabpanel' : undefined} aria-labelledby={workflowControls ? `${tabsId}-clinical` : undefined} hidden={view !== 'clinical'} disabled={busy} className="space-y-5">
      <ReasonNote label="Notes et motif de l’action" value={notes} onChange={setNotes} presets={clinicalNotePresets(order, stage, dentist)} />
      {!dentist && stage && can(['RECEPTION', 'QUALITE', 'CAO']) && <Panel title={`Inspection · ${labelFor(stage)}`}><div className="grid gap-3 sm:grid-cols-2">{Object.entries(checksByStage[stage]).map(([key, label]) => <label key={key} className="flex gap-3 text-sm"><input type="checkbox" checked={checks[key] === true} onChange={e => setChecks({ ...checks, [key]: e.target.checked })} />{label} conforme</label>)}</div><label className="flex gap-3 text-sm"><input type="checkbox" checked={gap} onChange={e => setGap(e.target.checked)} />Écart nécessitant une photo</label><Field label="Photo de preuve (obligatoire en cas d’échec ou d’écart)"><select className={control} value={photo} onChange={e => setPhoto(e.target.value)}><option value="">Choisir</option>{attachments.filter(a => a.kind === 'PHOTO').map(a => <option key={a.id} value={a.id}>{a.original_name}</option>)}</select></Field><Button onClick={() => command('inspection', { stage, checks: { ...Object.fromEntries(Object.keys(checksByStage[stage]).map(key => [key, checks[key] === true])), gap }, photo: photo || null, notes })}>Enregistrer le contrôle</Button></Panel>}
      {!dentist && can(['CAO']) && ['SALLE_CAO','VALIDATION_CAO'].includes(order.status) && order.design_validation_requested && <Panel title="Demander la validation du design"><Field label="Version de design téléversée"><select className={control} value={designAttachment} onChange={e => setDesignAttachment(e.target.value)}><option value="">Choisir</option>{attachments.filter(a => a.kind === 'DESIGN').map(a => <option key={a.id} value={a.id}>{a.original_name}</option>)}</select></Field><Button disabled={!designAttachment} onClick={() => command('design-request', { attachment: designAttachment, notes })}>Soumettre au dentiste et suspendre le délai</Button></Panel>}
      {evidence?.design_reviews?.length > 0 && <Panel title="Validations du design">{evidence.design_reviews.map(review => <div key={review.id} className="space-y-2 border-b border-slate-200/80 pb-3 text-sm"><p>Version {review.version} · {labelFor(review.status)} · {review.response_notes}</p><Button onClick={() => perform(() => download(client, base + `attachment/${review.attachment_id}/`, `design-v${review.version}`))}>Consulter le design</Button>{dentist && review.status === 'PENDING' && <div className="flex gap-3"><Button onClick={() => command('design-decision', { review: review.id, decision: 'APPROVED', notes })}>Approuver</Button><Button disabled={!notes.trim()} onClick={() => command('design-decision', { review: review.id, decision: 'CHANGES_REQUESTED', notes })}>Demander des corrections</Button></div>}</div>)}</Panel>}
      <div className="flex flex-wrap gap-3"><Button onClick={() => perform(load, 'Dossier actualisé.')}>Actualiser le dossier</Button>{(dentist || can(['RECEPTION'])) && <Button onClick={() => perform(() => download(client, base + 'qr/', `etiquette-${order.patient_ref}.png`), 'Étiquette téléchargée.')}>Étiquette QR</Button>}{dentist && <Button onClick={() => perform(() => download(client, base + 'invoice/', `facture-${order.patient_ref}.pdf`), 'Facture téléchargée.')}>Facture PDF</Button>}{!dentist && ['CONDITIONNEMENT','PRET_EXPEDITION','EN_ROUTE_CABINET','LIVRE','ESSAYAGE','CLOTURE'].includes(order.status) && <Button onClick={() => perform(() => download(api, base + 'delivery-slip/', `livraison-${order.patient_ref}.pdf`))}>Bon de livraison PDF</Button>}</div>
      <Panel title="Documents privés"><div className="flex flex-wrap items-end gap-3"><Field label="Type"><select className={control} value={kind} onChange={e => setKind(e.target.value)}><option value="PHOTO">Photo</option><option value="STL">STL</option><option value="DESIGN">Design</option></select></Field><Field label="Fichier · 25 Mo maximum"><input type="file" className={control} accept={kind === 'STL' ? '.stl' : kind === 'PHOTO' ? '.jpg,.jpeg,.png' : '.stl,.jpg,.jpeg,.png,.pdf'} onChange={e => setFile(e.target.files[0] || null)} /></Field><Button disabled={!file || busy} onClick={() => perform(async () => { if (!file.size || file.size > 25 * 1024 * 1024) throw new Error('Fichier non vide de 25 Mo maximum.'); const body = new FormData(); body.append('file', file); body.append('kind', kind); await client.post(base + 'attachments/', body); setFile(null); }, 'Fichier téléversé.')}>Téléverser</Button></div>
        <ul className="space-y-2 text-sm">{attachments.map(a => <li key={a.id}><Button onClick={() => perform(() => download(client, base + `attachment/${a.id}/`, a.original_name))}>{a.kind} · {a.original_name}</Button></li>)}</ul>
      </Panel>
      {!dentist && can(['RECEPTION','CAO','FAO','QUALITE']) && <Button disabled={!order.is_paused && !notes.trim()} onClick={() => command('pause', { paused: !order.is_paused, notes })}>{order.is_paused ? 'Reprendre le travail' : 'Suspendre avec motif'}</Button>}
      {order.status === 'RETOUR_DEMANDE' && can(['DENTIST','RECEPTION']) && <Button onClick={() => command('resubmit', { notes })}>Soumettre à nouveau après correction des documents</Button>}
      {dentist && !['LIVRE','ESSAYAGE','CLOTURE'].includes(order.status) && <Button onClick={() => command('issue-pin')}>Émettre un nouveau PIN de livraison</Button>}
      {dentist && order.status === 'EN_ROUTE_CABINET' && <Panel title="Confirmer la réception"><Field label="PIN de livraison"><input className={control} inputMode="numeric" maxLength={4} value={pin} onChange={e => setPin(e.target.value.replace(/\D/g, ''))} /></Field><Button disabled={!/^\d{4}$/.test(pin)} onClick={() => command('confirm-delivery', { pin })}>Valider le PIN</Button></Panel>}
      {dentist && ['LIVRE','ESSAYAGE'].includes(order.status) && <Button onClick={() => command('fitting', { passed: true, notes })}>Valider l’essayage clinique</Button>}
      {dentist && <Button disabled={!notes.trim()} onClick={() => command('dispute', { notes })}>Contester la ligne comptable</Button>}
      {!dentist && can(['COMPTABILITE']) && order.delivery_service === 'NEXT_DAY' && ['DEMANDE_RECUE','ANALYSE_DEMANDE','PLANIFICATION'].includes(order.status) && <Panel title="Devis manuel J+1"><Field label="Supplément urgence (MAD)"><input className={control} type="number" min="0" step="0.01" value={surcharge} onChange={e => setSurcharge(e.target.value)} /></Field><Button disabled={surcharge === ''} onClick={() => command('quote', { surcharge, notes })}>Confirmer le devis laboratoire</Button></Panel>}
      {!dentist && can(['RECEPTION','CAO','FAO','QUALITE','COMPTABILITE']) && <Button onClick={() => command('note', { notes, workstation: role })}>Enregistrer la remarque du poste</Button>}
      {reworkStages.has(order.status) && (dentist ? ['LIVRE','ESSAYAGE','CLOTURE'].includes(order.status) : can(['RECEPTION','CAO','FAO','QUALITE'])) && <Panel title="Reprise liée au dossier d’origine"><p className="text-xs text-slate-500">Dossier {order.id} · tentative {order.production_attempt}. Laisser les pertes vides pour une correction sans perte mesurée.</p><div className="grid gap-3 sm:grid-cols-2"><Field label="Origine"><select className={control} value={origin} onChange={e => setOrigin(e.target.value)}><option value="LAB">Laboratoire</option><option value="CLINIC">Cabinet</option></select></Field><Field label="Étape de reprise"><select className={control} value={restart} onChange={e => setRestart(e.target.value)}><option value="">Choisir</option>{[...new Set(restartSteps)].map(key => <option key={key} value={key}>{order.workflow_steps?.find(s => s.key === key)?.label || key}</option>)}</select></Field><Field label="Cause"><input className={control} value={cause} onChange={e => setCause(e.target.value)} /></Field><Field label="Action corrective"><input className={control} value={corrective} onChange={e => setCorrective(e.target.value)} /></Field></div>{!dentist && usages.filter(u => u.production_attempt === order.production_attempt && !u.source_history).map(u => <Field key={u.id} label={`Perte sur ${u.material_name_snapshot} (maximum ${quantityText(-Number(u.quantity_changed))} ${u.unit_snapshot})`}><input className={control} type="number" min="0" max={-Number(u.quantity_changed)} step="0.01" value={losses[u.id] || ''} onChange={e => { if (acceptsQuantity(e.target.value)) setLosses({ ...losses, [u.id]: e.target.value.replace(',', '.') }); }} /></Field>)}<Button disabled={!restart || !cause.trim() || !corrective.trim()} onClick={() => command('rework', { origin, cause, corrective_action: corrective, restart_status: restart, losses: measuredLosses(), notes })}>Enregistrer la reprise documentée</Button></Panel>}
      {!dentist && can(['RECEPTION','CAO','FAO','QUALITE']) && evidence?.reworks?.length > 0 && <Panel title="Évaluer les pertes d’une reprise antérieure"><Field label="Tentative d’origine"><select className={control} value={attempt} onChange={e => { setAttempt(e.target.value); setLosses({}); }}><option value="">Choisir</option>{evidence.reworks.map(r => <option key={r.id} value={r.attempt}>{r.attempt} · {r.cause}</option>)}</select></Field>{usages.filter(u => String(u.production_attempt) === attempt).map(u => <Field key={u.id} label={`${u.material_name_snapshot} · maximum ${quantityText(-Number(u.quantity_changed))} ${u.unit_snapshot}`}><input className={control} type="number" min="0" max={-Number(u.quantity_changed)} step="0.01" value={losses[u.id] || ''} onChange={e => { if (acceptsQuantity(e.target.value)) setLosses({ ...losses, [u.id]: e.target.value.replace(',', '.') }); }} /></Field>)}<Button disabled={!attempt || !measuredLosses().length} onClick={() => command('assess-loss', { attempt: Number(attempt), losses: measuredLosses(), notes })}>Classer les pertes mesurées</Button></Panel>}
      {evidence && <details><summary className="cursor-pointer text-sm text-slate-500">Historique et preuves</summary><div className="mt-3 space-y-3 text-xs text-slate-500">{['inspections','reworks','events','notifications'].map(key => <section key={key}><h3>{({ inspections: 'Inspections', reworks: 'Reprises', events: 'Événements', notifications: 'Notifications' })[key]}</h3>{evidence[key]?.map((row, index) => <p className="my-2 break-words" key={row.id || index}>{row.created_at} · {row.kind || row.stage || row.origin} · {row.notes || row.cause || JSON.stringify(row.payload)}</p>)}</section>)}</div></details>}
    </fieldset>
    </ActionDialog>
  </div>;
}
