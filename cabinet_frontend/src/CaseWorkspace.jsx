import { useCallback, useEffect, useRef, useState } from 'react';
import api from './api/client';
import platform from './api/platform';
import { allRows, download, errorText, money, retryableRequest, workstation } from './api/contracts';
import { caseStatusLabel, frenchMessage } from './api/messages';
import { previewMode } from './api/preview';
import ActionDialog from './ActionDialog';
import { Button, Feedback } from './IntegrationUI';
import { configurePlanningTime, labDateTime, labLongDate } from './planningTime';
import { riskLabels, serviceLabels } from './workQueueHelpers';
import { currentTask, ownsStep, waitingText } from './caseWorkspaceHelpers';
import { AcceptAction, ConfirmAction, PlanAction, InspectAction, DesignAction, WorkAction, ReworkAction, DentistAction, WaitingNotice } from './CaseActions';
import { CaseDossier, CaseProblems } from './CaseDetails';

const emptyData = { evidence: null, attachments: [], usages: [], tasks: [], queue: null, lots: [] };

export default function CaseWorkspace({ order, dentist = false, refresh, onClose, returnFocus, queueEntry, focusAction }) {
  const [committed, setCommitted] = useState(null);
  const sourceKey = `${order.laboratory_id || ''}:${order.id}:${order.status}:${order.state_version}:${order.updated_at}`;
  const current = committed?.source === sourceKey ? committed.order : order;
  const [data, setData] = useState(emptyData); const [ready, setReady] = useState(false); const [stale, setStale] = useState(false);
  const [busy, setBusy] = useState(false); const lock = useRef(false); const sequence = useRef(0); const mounted = useRef(true);
  const [error, setError] = useState(''); const [notice, setNotice] = useState('');
  const [notes, setNotes] = useState(''); const [progressNotes, setProgressNotes] = useState('');
  const [pin, setPin] = useState(''); const [issuedPin, setIssuedPin] = useState(''); const [events, setEvents] = useState([]);
  const request = useRef(retryableRequest()); const actionRegion = useRef(null); const focused = useRef(false);
  const refreshRef = useRef(refresh);
  useEffect(() => { refreshRef.current = refresh; }, [refresh]);
  const client = dentist ? platform : api; const role = dentist ? 'DENTIST' : workstation();
  const base = dentist ? `dentist/orders/${order.laboratory_id}/${order.id}/` : `prescriptions/${order.id}/`;
  const load = useCallback(async signal => {
    const ticket = ++sequence.current;
    const [evidence, attachments, usages, tasks, settings, queue, lots] = await Promise.all([
      client.get(base + 'evidence/', { signal }), client.get(base + 'attachments/', { signal }),
      dentist ? [] : allRows(api, 'inventory-transactions/', { prescription: order.id }, signal),
      dentist ? [] : allRows(api, 'planning/tasks/', { prescription: order.id, include_terminal: true }, signal),
      dentist ? null : api.get('planning/settings/', { signal }),
      dentist ? [] : allRows(api, 'work-queue/', { search: order.patient_ref }, signal),
      dentist || !order.current_step?.next_requires_lot ? [] : allRows(api, 'production-lots/', {}, signal),
    ]);
    if (mounted.current && ticket === sequence.current) {
      if (settings) configurePlanningTime(settings.data?.timezone);
      setData({ evidence: evidence.data, attachments: attachments.data, usages: usages.filter(row => row.transaction_type === 'USAGE'), tasks, queue: queue.find(row => row.id === order.id) || null, lots });
      setReady(true);
      setStale(false);
    }
  }, [base, client, dentist, order.id, order.patient_ref, order.current_step?.next_requires_lot]);
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; sequence.current += 1; }; }, []);
  useEffect(() => {
    const abort = new AbortController();
    const update = () => { if (document.visibilityState === 'visible' && !lock.current) void load(abort.signal).catch(e => { if (!abort.signal.aborted && mounted.current) setError(errorText(e)); }); };
    update(); const timer = previewMode ? null : setInterval(update, 10000);
    window.addEventListener('focus', update); document.addEventListener('visibilitychange', update);
    return () => { abort.abort(); clearInterval(timer); window.removeEventListener('focus', update); document.removeEventListener('visibilitychange', update); };
  }, [load, order.status, order.updated_at]);
  useEffect(() => {
    if (!ready || !focusAction || focused.current) return;
    const selector = focusAction === 'delivery' ? 'input' : 'button[data-primary-action]';
    const button = actionRegion.current?.querySelector(selector);
    if (button) { focused.current = true; button.focus({ preventScroll: true }); }
  }, [ready, focusAction]);
  async function perform(action, success = 'Action enregistrée.', synchronize = true) {
    if (lock.current) return false;
    if (stale && synchronize) { setError('Actualisez le dossier avant une nouvelle action.'); return false; }
    lock.current = true; setBusy(true); setError(''); setNotice('');
    try {
      await action();
      if (mounted.current) setNotice(success);
      if (synchronize) {
        try { await Promise.all([load(), refreshRef.current?.()]); }
        catch (e) { if (mounted.current) { setStale(true); setError(`Action enregistrée. Actualisez le dossier pour vérifier son nouvel état. ${errorText(e)}`); } }
      }
      return true;
    } catch (e) { if (mounted.current) setError(errorText(e)); return false; }
    finally { lock.current = false; if (mounted.current) setBusy(false); }
  }
  function applyCase(value) { if (value?.id === order.id) setCommitted({ source: sourceKey, order: value }); }
  const command = (action, values = {}) => perform(async () => {
    const response = await request.current(client, base + 'command/', { action, data: values });
    applyCase(response.data.case);
    if (response.data.result?.pin_once) setIssuedPin(response.data.result.pin_once);
    if (action === 'confirm-delivery') setPin('');
    if (values.notes !== undefined) setNotes('');
  });
  const planningCommand = (task, action, extra = {}, suppliedNotes = progressNotes) => perform(async () => {
    const response = await request.current(api, base + 'command/', { action: 'planning-' + action, data: { task: task.id, notes: suppliedNotes, ...extra } });
    applyCase(response.data.case); setProgressNotes('');
  }, 'Progression enregistrée.');
  const patch = (values, success = 'Enregistrement effectué.') => perform(async () => { const response = await api.patch(base, values); applyCase(response.data); }, success);
  const downloadFile = (path, name, success = 'Document téléchargé.') => perform(() => download(client, base + path, name), success, false);
  const upload = (file, kind) => perform(async () => {
    if (!file?.size || file.size > 25 * 1024 * 1024) throw new Error('Fichier non vide de 25 Mo maximum.');
    const body = new FormData(); body.append('file', file); body.append('kind', kind);
    await client.post(base + 'attachments/', body);
  }, 'Fichier téléversé.');
  const createLot = payload => perform(() => api.post('production-lots/', payload), 'Lot créé et lié au dossier.');
  const loadHistory = () => perform(async () => setEvents(await allRows(api, 'planning/events/', { prescription: order.id })), 'Historique du planning chargé.', false);
  const task = currentTask(current, data.tasks);
  const onRework = () => {
    const details = actionRegion.current?.parentElement.querySelector('.case-disclosure');
    if (details) { details.open = true; const field = details.querySelector('[data-rework-start]'); field?.scrollIntoView({ block: 'center' }); field?.focus({ preventScroll: true }); }
  };
  const shared = { order: current, busy, command, patch, upload, createLot, lots: data.lots, role, evidence: data.evidence, attachments: data.attachments, tasks: data.tasks, task, notes, setNotes, progressNotes, setProgressNotes, planningCommand, pin, setPin, downloadFile, onRework };
  let action;
  if (!ready) action = <WaitingNotice>{error ? 'Le dossier n’a pas pu être chargé. Utilisez Actualiser le dossier.' : 'Chargement du dossier…'}</WaitingNotice>;
  else if (stale) action = <WaitingNotice>Action enregistrée. Actualisez le dossier avant une nouvelle action.</WaitingNotice>;
  else if (!current.current_step) action = <WaitingNotice>Les informations de l’étape ne sont pas disponibles. Actualisez le dossier.</WaitingNotice>;
  else if (dentist) action = <DentistAction {...shared} />;
  else if (['CUSTODY', 'CLINIC', 'DONE'].includes(current.current_step.kind)) action = <WaitingNotice>{waitingText(current, false, data.evidence)}</WaitingNotice>;
  else if (!ownsStep(current, role)) action = <WaitingNotice>{role === 'COMPTABILITE' && current.delivery_service === 'NEXT_DAY' && current.total_price == null ? 'Le devis J+1 est à établir dans Dossier.' : waitingText(current, false, data.evidence)}</WaitingNotice>;
  else if (current.is_paused) action = <WaitingNotice>Ce dossier est suspendu. Ouvrez Signaler un problème pour reprendre le travail après résolution du motif.</WaitingNotice>;
  else {
    const Action = { ACCEPT: AcceptAction, CONFIRM: ConfirmAction, PLAN: PlanAction, INSPECT: InspectAction, DESIGN: DesignAction, WORK: WorkAction, REWORK: ReworkAction }[current.current_step.kind];
    action = Action ? <Action key={`${current.status}:${current.production_attempt}:${current.intake_revision}`} {...shared} /> : <WaitingNotice>{waitingText(current)}</WaitingNotice>;
  }
  const risk = data.queue?.risk || queueEntry?.risk;
  const deadline = data.queue?.deadline_at || queueEntry?.deadline_at || current.deadline_at;
  return <><Feedback error={error} notice={notice} /><ActionDialog open busy={busy} returnFocus={returnFocus} onClose={onClose} title={`Dossier clinique — ${current.patient_ref}`}>
    <div className="case-workspace space-y-5">
      <section aria-label="Résumé clinique" className="case-header space-y-3"><div className="flex flex-wrap items-start justify-between gap-3"><div><p className="font-semibold">{current.dentist_name}</p>{dentist && <p className="text-sm text-slate-600">{current.laboratory_name}</p>}</div><Button disabled={busy} onClick={() => perform(load, 'Dossier actualisé.', false)}>Actualiser le dossier</Button></div>
        <ul className="grid gap-2 text-sm sm:grid-cols-2">{current.clinical_items?.length ? current.clinical_items.map(item => <li key={item.tooth_number}><strong>Dent {item.tooth_number}</strong> · {item.function} · {item.form} · {item.material} · {item.shade}</li>) : <li>Dent {current.tooth_number} · {current.material} · {current.shade}</li>}</ul>
        <div className="flex flex-wrap gap-2 text-xs"><span>{current.impression_type === 'PHYSIQUE' ? 'Empreinte physique' : 'Empreinte numérique'}</span><span>· {({ CFAO: 'CFAO / usinage CNC', IMPRESSION_3D: 'Impression 3D', CONVENTIONNEL: 'Fabrication conventionnelle' })[current.production_method] || 'Méthode à planifier'}</span><span className="case-chip">{serviceLabels[current.delivery_service] || (current.is_fast_track ? 'Urgent' : 'Standard')}</span><span className="case-chip">{({ COMMANDE: 'Bon de commande', SITUATION: 'Au relevé mensuel', FACTURE: 'Facturé' })[current.billing_stage] || 'Bon de commande'} · {money(current.total_price)}</span></div>
        {dentist ? <p className="text-sm">Livraison prévue : {current.delivery_date || current.deadline_at ? labLongDate(current.delivery_date || current.deadline_at) : 'à confirmer par le laboratoire'}</p>
          : <p className="text-sm">Échéance : {labDateTime(deadline)} · <span className="case-chip">{riskLabels[risk] || (current.current_step?.kind === 'DONE' ? 'Dossier clôturé' : 'Risque en cours de calcul')}</span></p>}
        {current.is_paused && <p className="rounded-xl border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">En pause : {frenchMessage(current.pause_reason)}</p>}
      </section>
      <nav aria-label="Étapes du dossier"><ol className="case-stepper">{current.stages?.map(stage => <li key={stage.key} data-state={stage.state} aria-current={stage.state === 'current' ? 'step' : undefined}><span>{stage.state === 'done' && <span aria-hidden="true">✓ </span>}{stage.label}{stage.state === 'done' && <span className="sr-only"> (terminée)</span>}</span>{stage.state === 'current' && <small>{caseStatusLabel(current)}</small>}</li>)}</ol></nav>
      <section ref={actionRegion} aria-label="Votre action" className="case-current-action space-y-4"><div><h3 className="text-lg font-semibold">Votre action</h3><p className="mt-1 text-sm text-teal-800">{caseStatusLabel(current)}</p>{!dentist && current.current_step?.instruction && <p className="mt-2 text-sm text-slate-600">{current.current_step.instruction}</p>}</div><fieldset disabled={busy} className="space-y-4">{action}</fieldset></section>
      {issuedPin && <div role="status" className="rounded-xl bg-amber-50 p-4">Nouveau PIN, affiché une seule fois : <strong className="select-all font-mono">{issuedPin}</strong> <Button onClick={() => setIssuedPin('')}>Masquer</Button></div>}
      {ready && <><CaseProblems key={`problems:${current.id}:${current.status}`} {...shared} dentist={dentist} role={role} usages={data.usages} />
        <CaseDossier key={`${current.id}:${current.status}`} {...shared} dentist={dentist} role={role} upload={upload} planningHistory={events} loadHistory={loadHistory} initiallyOpen={focusAction === 'quote'} />
      </>}
    </div>
  </ActionDialog></>;
}
