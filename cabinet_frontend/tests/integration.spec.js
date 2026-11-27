import { test, expect } from '@playwright/test';

for (const viewport of [{ width: 1440, height: 1000 }, { width: 912, height: 768 }, { width: 390, height: 640 }]) {
  test(`account menu stays above stock controls and logout works at ${viewport.width}px`, async ({ page }) => {
    await page.setViewportSize(viewport);
    await session(page);
    await mocks(page);
    await page.goto('/static/');
    if (viewport.width <= 650) await page.getByRole('button', { name: 'Ouvrir la navigation', exact: true }).click();
    await page.getByRole('button', { name: 'Stocks et lots', exact: true }).click();
    if (viewport.width === 912) await page.getByRole('button', { name: 'Réduire la navigation', exact: true }).click();
    await page.getByRole('button', { name: 'Mon compte', exact: true }).click();
    const panel = page.locator('#account-panel');
    await expect(panel).toBeVisible();
    const bounds = await panel.boundingBox();
    expect(bounds.x).toBeGreaterThanOrEqual(0);
    expect(bounds.x + bounds.width).toBeLessThanOrEqual(viewport.width);
    const logout = panel.getByRole('button', { name: 'Déconnexion', exact: true });
    await logout.scrollIntoViewIfNeeded();
    await expect.poll(() => logout.evaluate(button => {
      const rect = button.getBoundingClientRect();
      return button.contains(document.elementFromPoint(rect.x + rect.width / 2, rect.y + rect.height / 2));
    })).toBe(true);
    await logout.click();
    await expect(page.locator('#login-portal')).toBeVisible();
    expect(await page.evaluate(() => sessionStorage.getItem('demo_user'))).toBeNull();
  });
}

const id = 'd3f16d2a-4910-47cb-920d-8c1011539c01';
const queueRow = overrides => ({ id, patient_ref: 'PAT-QUEUE', dentist_name: 'Dentiste file', status: 'CONTROLE_DOSSIER', current_step: { kind: 'INSPECT', label: 'Contrôle du dossier', stage_label: "Contrôle d’entrée" }, group: 'TODO', primary_action: { label: "Contrôler l’empreinte", view: 'clinical', command: 'inspection' }, task: null, deadline_at: '2026-11-13T17:00:00Z', risk: 'AT_RISK', delivery_service: 'EXPRESS', ...overrides });
// Explicit server descriptors for mocked API cases. Production UI never maps statuses to roles.
const caseSteps = {
  DEMANDE_RECUE: ['ACCEPT', 'RECEPTION', 'COMMANDE', 'Demande reçue', 'ANALYSE_DEMANDE'],
  ANALYSE_DEMANDE: ['CONFIRM', 'RECEPTION', 'COMMANDE', 'Analyse de la demande', 'ATTENTE_RAMASSAGE'],
  A_CONFIRMER: ['CONFIRM', 'RECEPTION', 'RECEPTION', 'Réception', 'CONTROLE_DOSSIER'],
  CONTROLE_DOSSIER: ['INSPECT', 'RECEPTION', 'CONTROLE_ENTREE', 'Contrôle du dossier', 'COULEE_PLATRE'],
  CONTROLE_MODELE: ['INSPECT', 'RECEPTION', 'MODELE', 'Contrôle modèle et scan', 'PLANIFICATION'],
  PLANIFICATION: ['PLAN', 'RECEPTION', 'CONCEPTION', 'Planification', 'SALLE_CAO'],
  SALLE_CAO: ['DESIGN', 'CAO', 'CONCEPTION', 'Conception CAO', 'PREPARATION_CNC'],
  VALIDATION_CAO: ['CLINIC', 'CAO', 'CONCEPTION', 'Validation du design', 'PREPARATION_CNC'],
  PREPARATION_CNC: ['WORK', 'FAO', 'FABRICATION', 'Préparation FAO', 'USINAGE_CNC'],
  USINAGE_CNC: ['WORK', 'FAO', 'FABRICATION', 'Usinage CNC', 'FINITION'],
  A_REFAIRE: ['REWORK', 'FAO', 'FABRICATION', 'Reprise de fabrication', 'SALLE_CAO'],
  FINITION: ['WORK', 'FAO', 'FINITION_QC', 'Finition', 'CONTROLE_QUALITE'],
  CONTROLE_QUALITE: ['INSPECT', 'QUALITE', 'FINITION_QC', 'Contrôle qualité final', 'CONDITIONNEMENT'],
  CONDITIONNEMENT: ['WORK', 'QUALITE', 'FINITION_QC', 'Conditionnement', 'PRET_EXPEDITION'],
  ATTENTE_RAMASSAGE: ['CUSTODY', 'COURIER', 'RECEPTION', 'Ramassage', 'EN_ROUTE_LABO'],
  EN_ROUTE_LABO: ['CUSTODY', 'COURIER', 'RECEPTION', 'Transport vers le laboratoire', 'A_CONFIRMER'],
  PRET_EXPEDITION: ['CUSTODY', 'COURIER', 'LIVRAISON', 'Prêt à expédier', 'EN_ROUTE_CABINET'],
  EN_ROUTE_CABINET: ['CUSTODY', 'COURIER', 'LIVRAISON', 'Livraison', 'LIVRE'],
  LIVRE: ['CLINIC', '', 'LIVRAISON', 'Livré', 'ESSAYAGE'],
  ESSAYAGE: ['CLINIC', '', 'LIVRAISON', 'Essayage', 'CLOTURE'],
  RETOUR_DEMANDE: ['CLINIC', 'RECEPTION', 'CONTROLE_ENTREE', 'Retour demandé', 'A_CONFIRMER'],
  CLOTURE: ['DONE', '', 'CLOTURE', 'Clôturé', null],
};
const caseOrder = (overrides = {}) => {
  const status = overrides.status || 'ANALYSE_DEMANDE';
  const [kind, role, stage, label, next] = caseSteps[status];
  const inspection = ['A_CONFIRMER', 'CONTROLE_DOSSIER'].includes(status) ? overrides.impression_type === 'NUMERIQUE' ? 'DIGITAL' : 'PHYSICAL' : status === 'CONTROLE_MODELE' ? 'MODEL' : status === 'CONTROLE_QUALITE' ? 'QUALITY' : null;
  return { id, patient_ref: 'PAT-TEST', dentist_name: 'Dentiste test', laboratory_id: 'labo1', laboratory_name: 'Laboratoire test', partner_clinic: 1, status, status_label: label, accepted: true, total_price: '1200.00', production_attempt: 1, intake_revision: 1, intake_version: 2, impression_type: 'PHYSIQUE', delivery_service: 'STANDARD', updated_at: '2026-11-04T12:00:00Z', clinical_items: [{ tooth_number: 11, function: 'Couronne', form: 'Anatomique', material: 'Zircone', shade: 'A1' }], workflow_steps: [{ key: status, label }, ...(next ? [{ key: next, label: caseSteps[next]?.[3] || next }] : [])], next_status: next,
    stages: [{ key: stage, label: stage === 'COMMANDE' ? 'Commande' : stage === 'FABRICATION' ? 'Fabrication' : 'Parcours clinique', state: 'current' }],
    rework_restart_options: ['SALLE_CAO', 'PREPARATION_CNC', 'FINITION', 'COULEE_PLATRE', 'SCAN_LABO'].map(key => ({ key, label: caseSteps[key]?.[3] || key })),
    ...overrides, current_step: { key: status, kind, owner_roles: role ? [role] : [], stage, label, next_key: next, next_label: caseSteps[next]?.[3] || next, inspection_stages: inspection ? [inspection] : [], planning_options: { CFAO: { next_key: 'SALLE_CAO', next_label: 'Conception CAO' }, IMPRESSION_3D: { next_key: 'SALLE_CAO', next_label: 'Conception CAO' }, CONVENTIONNEL: { next_key: 'MODELE_TRAVAIL', next_label: 'Modèle de travail' } }, confirm_field: status === 'ANALYSE_DEMANDE' ? 'analysis_validated' : 'reception_validated', ...overrides.current_step } };
};
async function session(page, role = 'Laboratoire', workstation_role = 'MANAGER') {
  await page.addInitScript(({ role, workstation_role }) => {
    sessionStorage.setItem('demo_user', JSON.stringify({ name: 'Compte de test', role, workstation_role }));
    sessionStorage.setItem('demo_token', 'fixture-token'); sessionStorage.setItem('tenant_id', 'labo1');
  }, { role, workstation_role });
}
async function openClinical(page) {
  const dialog = page.getByRole('dialog', { name: /Dossier clinique/ });
  if (!await dialog.isVisible()) await page.getByRole('button', { name: /Ouvrir le dossier / }).click();
  return dialog;
}
async function openDossier(page) {
  const dialog = await openClinical(page); const summary = dialog.locator('summary').filter({ hasText: /^Dossier$/ });
  if (!await summary.evaluate(element => element.parentElement.open)) await summary.click();
  return dialog;
}
async function openProblems(page) {
  const dialog = await openClinical(page); const summary = dialog.locator('summary').filter({ hasText: /^Signaler un problème$/ });
  if (!await summary.evaluate(element => element.parentElement.open)) await summary.click();
  return dialog;
}
async function mocks(page, handler) {
  const errors = []; page.on('pageerror', e => errors.push(e.message));
  await page.route(/http:\/\/[^/]*localhost:8000\//, async route => {
    const req = route.request(); const url = new URL(req.url());
    if (req.method() === 'OPTIONS') return route.fulfill({ status: 204, headers: { 'Access-Control-Allow-Origin': '*', 'Access-Control-Allow-Headers': '*' } });
    const reply = await handler?.(url.pathname, req, url);
    const data = reply ?? (url.pathname === '/platform/pricing/' ? { materials: { Zircone: '1200.00', 'E-Max': '1500.00' }, express_rate: '0.30' }
      : url.pathname === '/platform/laboratories/' ? [{ id: 1, identifier: 'labo1', name: 'Laboratoire test' }]
      : url.pathname === '/platform/dentist/clinics/' ? [{ id: 1, name: 'Cabinet test', pickup_address: '10 rue test' }]
      : url.pathname.endsWith('/evidence/') ? { design_reviews: [], reworks: [], inspections: [], events: [] }
      : []);
    await route.fulfill({ json: data, headers: { 'Access-Control-Allow-Origin': '*' } });
  });
  return errors;
}

for (const width of [1440, 390]) {
  test(`work queue is the landing page and opens one focused action per row at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 844 });
    await session(page, 'Laboratoire', 'RECEPTION');
    const errors = await mocks(page, path => {
      if (path === '/api/work-queue/') return { results: [queueRow()], next: null };
      if (path === `/api/prescriptions/${id}/`) return caseOrder({ patient_ref: 'PAT-QUEUE', status: 'CONTROLE_DOSSIER' });
    });
    await page.goto('/static/');
    await expect(page.getByRole('heading', { name: 'À faire', exact: true })).toBeVisible();
    const row = page.getByRole('article', { name: 'Dossier PAT-QUEUE' });
    await expect(row.getByRole('button')).toHaveCount(1);
    await expect(row).toContainText('Express J+2');
    await expect(row).toContainText('À risque');
    await expect(page.getByLabel('Filtrer par poste')).toHaveCount(0);
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBe(width);
    const button = row.getByRole('button'); await button.click();
    const dialog = page.getByRole('dialog', { name: 'Dossier clinique — PAT-QUEUE' });
    await expect(dialog).toBeVisible();
    await expect(dialog.getByRole('region', { name: 'Votre action' })).toContainText('Inspection');
    await expect(dialog.getByRole('tab')).toHaveCount(0);
    await page.keyboard.press('Escape');
    await expect(dialog).toHaveCount(0); await expect(button).toBeFocused();
    expect(errors).toEqual([]);
  });
}

test('queue search and manager role filter use the server; empty results are explained', async ({ page }) => {
  await session(page);
  const requests = [];
  await mocks(page, (path, req, url) => {
    if (path === '/api/work-queue/') { requests.push(Object.fromEntries(url.searchParams)); return { results: [], next: null }; }
  });
  await page.goto('/static/');
  await expect(page.getByText('Rien à faire pour votre poste pour le moment.')).toBeVisible();
  await page.getByLabel('Filtrer par poste').selectOption('FAO');
  await page.getByLabel('Rechercher dans ma file').fill('PAT-SEARCH');
  await expect.poll(() => requests.at(-1)?.search).toBe('PAT-SEARCH');
  expect(requests.at(-1).role).toBe('FAO');
  await page.evaluate(() => window.dispatchEvent(new Event('focus')));
  await expect.poll(() => requests.filter(value => value.search === 'PAT-SEARCH').length).toBeGreaterThan(1);
});

test('dentist task shortcuts open the actual fitting control without submitting it', async ({ page }) => {
  await session(page, 'Cabinet Dentaire'); let writes = 0;
  const order = caseOrder({ status: 'LIVRE', current_step: { kind: 'CLINIC', label: 'Livré' } });
  await mocks(page, (path, req) => {
    if (req.method() !== 'GET') writes++;
    if (path === '/platform/dentist/orders/') return [order];
  });
  await page.goto('/static/');
  const row = page.getByRole('article', { name: 'Action pour PAT-TEST' });
  await expect(row.getByRole('button')).toHaveCount(1);
  await row.getByRole('button', { name: 'Valider l’essayage clinique' }).click();
  const action = page.getByRole('dialog').getByRole('button', { name: 'Valider l’essayage clinique' });
  await expect(action).toBeVisible(); await expect(action).toBeFocused();
  expect(writes).toBe(0);
});

test('accounting still lands on billing and can open its quote queue', async ({ page }) => {
  await session(page, 'Laboratoire', 'COMPTABILITE'); await mocks(page);
  await page.goto('/static/');
  await expect(page.getByRole('heading', { name: 'Facturation', exact: true }).first()).toBeVisible();
  await page.getByRole('button', { name: 'À faire', exact: true }).click();
  await expect(page.getByLabel('Rechercher dans ma file')).toBeVisible();
});

test('digital prescription resumes an upload failure without creating a second case', async ({ page }) => {
  await session(page, 'Cabinet Dentaire'); let creations = 0; let uploads = 0; let submission;
  const errors = await mocks(page, async (path, req) => {
    if (path === '/platform/dentist/orders/' && req.method() === 'POST') {
      creations++; submission = req.postDataJSON(); expect(req.headers()['idempotency-key']).toMatch(/^[0-9a-f-]{36}$/);
      return caseOrder({ total_price: '1560.00', delivery_pin_once: '0123' });
    }
    if (path.endsWith('/attachments/') && req.method() === 'POST') {
      uploads++; if (uploads === 1) { await req; return { detail: 'Upload accepted by fixture' }; }
      return { id: 'attachment', kind: 'STL' };
    }
  });
  // Fail the first file request at the transport layer after the case is created.
  let uploadRequests = 0;
  await page.route('**/platform/dentist/orders/labo1/*/attachments/', async route => {
    if (++uploadRequests === 1) await route.abort('failed'); else await route.fallback();
  });
  await page.goto('/static/');
  await page.getByLabel('Laboratoire destinataire').selectOption('labo1');
  await page.getByLabel('Cabinet et adresse de collecte').selectOption('1');
  await page.getByLabel('Référence patient anonyme').fill('PAT-NEW');
  await page.getByRole('button', { name: 'Dent 11', exact: true }).click();
  await page.getByLabel('Fonction', { exact: true }).selectOption('Couronne'); await page.getByLabel('Forme', { exact: true }).selectOption('Anatomique');
  await page.getByLabel('Teinte', { exact: true }).selectOption('A1');
  await page.getByLabel('Matériau', { exact: true }).selectOption('Zircone');
  await page.getByLabel('Empreinte', { exact: true }).selectOption('NUMERIQUE');
  await page.getByLabel('Service de livraison').selectOption('EXPRESS');
  await page.getByLabel('Je confirme la désinfection').check();
  await page.getByLabel('Fichier STL réel').setInputFiles({ name: 'scan.stl', mimeType: 'model/stl', buffer: Buffer.from('solid test\nendsolid test') });
  await page.getByRole('button', { name: 'Envoyer la prescription' }).click();
  await expect(page.getByText('Le dossier est créé.')).toBeVisible();
  await page.getByRole('button', { name: 'Réessayer le téléversement STL' }).click();
  await expect(page.getByText('Prescription enregistrée')).toBeVisible(); await expect(page.getByText('0123')).toBeVisible();
  expect(creations).toBe(1); expect(uploadRequests).toBe(2); expect(submission.clinical_items[0].function).toBe('Couronne');
  expect(submission.delivery_service).toBe('EXPRESS'); expect(submission.partner_clinic).toBe(1); expect(submission).not.toHaveProperty('total_price'); expect(errors).toEqual([]);
  await page.screenshot({ path: 'test-results/prescription.png', fullPage: true });
});

test('paginated laboratory cases advance with only authorized fields', async ({ page }) => {
  await session(page, 'Laboratoire', 'RECEPTION'); let patch;
  const errors = await mocks(page, (path, req, url) => {
    if (path === '/api/prescriptions/' && req.method() === 'GET') return url.searchParams.get('page') === '1'
      ? { count: 2, next: 'http://labo1.localhost:8000/api/prescriptions/?page=2', results: [caseOrder()] }
      : { count: 2, next: null, results: [caseOrder({ id: 'd3f16d2a-4910-47cb-920d-8c1011539c02', patient_ref: 'PAT-PAGE2' })] };
    if (path.endsWith('/command/')) { const command=req.postDataJSON(); expect(command.action).toBe('advance'); patch=command.data; return { case:caseOrder(), result:{} }; }
  });
  await page.goto('/static/'); await page.getByRole('button', { name: 'Commandes', exact: true }).first().click();
  await expect(page.getByText('PAT-PAGE2', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Ouvrir le dossier PAT-TEST' }).click();
  await page.getByRole('button', { name: 'Analyse validée → Ramassage' }).click();
  expect(patch).not.toHaveProperty('status'); expect(patch.analysis_validated).toBe(true);
  expect(patch).not.toHaveProperty('is_paused'); expect(patch).not.toHaveProperty('quality_validated'); expect(errors).toEqual([]);
});

test('courier submits QR custody and actual entered PIN through commands', async ({ page }) => {
  await session(page, 'Coursier'); let order = caseOrder({ status: 'PRET_EXPEDITION' }); const commands = [];
  await mocks(page, (path, req) => {
    if (path === '/api/prescriptions/') return { count: 1, results: [order], next: null };
    if (path.endsWith('/command/')) { const payload = req.postDataJSON(); commands.push(payload); order = { ...order, status: payload.action === 'checkout' ? 'EN_ROUTE_CABINET' : 'LIVRE' }; return { case: order, result: {} }; }
  });
  await page.goto('/static/'); await page.getByRole('button', { name: 'Sortir du laboratoire', exact: true }).click(); await page.getByLabel('Contenu du QR signé').fill('signed-token');
  await page.getByRole('dialog').getByRole('button', { name: 'Sortir du laboratoire', exact: true }).click();
  await page.getByRole('button', { name: 'Confirmer la livraison', exact: true }).click(); await page.getByLabel('PIN réel de livraison').fill('0789'); await page.getByRole('dialog').getByRole('button', { name: 'Confirmer la livraison', exact: true }).click();
  await expect.poll(() => commands.length).toBe(2);
  expect(commands).toEqual([{ action: 'checkout', data: { qr_token: 'signed-token' } }, { action: 'confirm-delivery', data: { pin: '0789' } }]);
});

test('clinical inspection records explicit checks through the evidence command', async ({ page }) => {
  await session(page); const commands = []; const order = caseOrder({ status: 'CONTROLE_DOSSIER' });
  await mocks(page, (path, req) => {
    if (path === '/api/prescriptions/') return { results: [order], next: null };
    if (path.endsWith('/command/')) { commands.push(req.postDataJSON()); return { case: order, result: {} }; }
  });
  await page.goto('/static/'); await page.getByRole('button', { name: 'Commandes', exact: true }).first().click(); await page.getByRole('button', { name: 'Ouvrir le dossier PAT-TEST' }).click();
  await openClinical(page);
  for (const name of ['Absence de déformation','Absence de bulles','Limites lisibles','Occlusion','Hygiène']) await page.getByLabel(name + ' conforme', { exact: true }).check();
  await page.getByRole('button', { name: /Valider le contrôle/ }).click();
  await expect.poll(() => commands.length).toBe(1); expect(commands[0].action).toBe('inspection'); expect(commands[0].data.stage).toBe('PHYSICAL'); expect(Object.values(commands[0].data.checks)).toEqual([true,true,true,true,true,false]);
  expect(commands[0].data.advance).toBe(true);
});

test('courier displays the server workflow label rather than a browser status dictionary', async ({ page }) => {
  await session(page, 'Coursier');
  const order = { id, patient_ref: 'PAT-TEST', status: 'ATTENTE_RAMASSAGE', status_label: 'Collecte prévue selon le serveur' };
  await mocks(page, path => path === '/api/prescriptions/' ? { results: [order], next: null } : undefined);
  await page.goto('/static/');
  await expect(page.getByText('Collecte prévue selon le serveur', { exact: true })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Confirmer la collecte', exact: true })).toBeVisible();
});

test('acceptance is one idempotent command and sends no PATCH', async ({ page }) => {
  await session(page, 'Laboratoire', 'RECEPTION'); const calls = []; const patches = [];
  const order = caseOrder({ status: 'DEMANDE_RECUE', accepted: false });
  await mocks(page, (path, req) => {
    if (req.method() === 'PATCH') patches.push(path);
    if (path === '/api/prescriptions/') return { results: [order], next: null };
    if (path.endsWith('/command/')) { calls.push(req); return { case: caseOrder(), result: { status: 'ANALYSE_DEMANDE' } }; }
  });
  await page.goto('/static/'); await page.getByRole('button', { name: 'Commandes', exact: true }).first().click();
  const dialog = await openClinical(page);
  await dialog.getByRole('button', { name: 'Accepter et analyser', exact: true }).click();
  await expect.poll(() => calls.length).toBe(1);
  expect(calls[0].postDataJSON()).toEqual({ action: 'accept', data: {} });
  expect(calls[0].headers()['idempotency-key']).toMatch(/^[0-9a-f-]{36}$/);
  expect(patches).toEqual([]);
  await expect(dialog.getByRole('button', { name: /Analyse validée/ })).toBeVisible();
});

for (const status of ['ANALYSE_DEMANDE', 'A_CONFIRMER']) {
  test(`${status} confirms explicitly in one click without a separate checkbox`, async ({ page }) => {
    await session(page, 'Laboratoire', 'RECEPTION'); const calls = [];
    const order = caseOrder({ status });
    await mocks(page, (path, req) => path === '/api/prescriptions/' ? { results: [order], next: null } : path.endsWith('/command/') ? (calls.push(req.postDataJSON()), { case: order, result: {} }) : undefined);
    await page.goto('/static/'); await page.getByRole('button', { name: 'Commandes', exact: true }).first().click();
    const dialog = await openClinical(page);
    await expect(dialog.getByRole('checkbox')).toHaveCount(0);
    expect(calls).toEqual([]);
    await dialog.locator('[data-primary-action]').click();
    await expect.poll(() => calls.length).toBe(1);
    expect(calls[0]).toEqual({ action: 'advance', data: { [status === 'ANALYSE_DEMANDE' ? 'analysis_validated' : 'reception_validated']: true } });
  });
}

test('Tout conforme is local, leaves the photo gap unchanged and allows unticking', async ({ page }) => {
  await session(page); const calls = []; const order = caseOrder({ status: 'CONTROLE_MODELE' });
  await mocks(page, (path, req) => path === '/api/prescriptions/' ? { results: [order], next: null } : path.endsWith('/command/') ? (calls.push(req.postDataJSON()), { case: order, result: {} }) : undefined);
  await page.goto('/static/'); await page.getByRole('button', { name: 'Commandes', exact: true }).first().click();
  const dialog = await openClinical(page);
  for (const box of await dialog.getByRole('checkbox').all()) await expect(box).not.toBeChecked();
  await dialog.getByRole('button', { name: 'Tout conforme', exact: true }).click();
  expect(calls).toEqual([]);
  await expect(dialog.getByLabel('Modèle conforme', { exact: true })).toBeChecked();
  await expect(dialog.getByLabel('Scan conforme', { exact: true })).toBeChecked();
  await expect(dialog.getByLabel('Écart nécessitant une photo')).not.toBeChecked();
  await expect(dialog.getByRole('button', { name: 'Valider le contrôle → Planification', exact: true })).toBeVisible();
  await dialog.getByLabel('Scan conforme', { exact: true }).uncheck();
  await expect(dialog.getByRole('button', { name: 'Enregistrer la non-conformité', exact: true })).toBeVisible();
  await dialog.getByLabel('Écart nécessitant une photo').check();
  await dialog.getByRole('button', { name: 'Tout conforme', exact: true }).click();
  await expect(dialog.getByLabel('Écart nécessitant une photo')).toBeChecked();
  expect(calls).toEqual([]);
});

test('passing inspection submits every explicit criterion and advance in the same command', async ({ page }) => {
  await session(page); const calls = []; const order = caseOrder({ status: 'CONTROLE_MODELE' });
  await mocks(page, (path, req) => path === '/api/prescriptions/' ? { results: [order], next: null } : path.endsWith('/command/') ? (calls.push(req), { case: caseOrder({ status: 'PLANIFICATION' }), result: { advanced: true } }) : undefined);
  await page.goto('/static/'); await page.getByRole('button', { name: 'Commandes', exact: true }).first().click();
  const dialog = await openClinical(page);
  await dialog.getByRole('button', { name: 'Tout conforme', exact: true }).click();
  await dialog.getByRole('button', { name: 'Valider le contrôle → Planification', exact: true }).click();
  await expect.poll(() => calls.length).toBe(1);
  expect(calls[0].postDataJSON()).toEqual({ action: 'inspection', data: { stage: 'MODEL', checks: { model: true, scan: true, gap: false }, photo: null, notes: '', advance: true } });
  expect(calls[0].headers()['idempotency-key']).toMatch(/^[0-9a-f-]{36}$/);
  await expect(dialog.getByLabel('Méthode de fabrication')).toBeVisible();
});

test('reception keeps its explicit photographed non-conformity path', async ({ page }) => {
  await session(page); const calls = []; const order = caseOrder({ status: 'A_CONFIRMER' });
  await mocks(page, (path, req) => {
    if (path === '/api/prescriptions/') return { results: [order], next: null };
    if (path.endsWith('/attachments/')) return [{ id: 'proof', kind: 'PHOTO', original_name: 'preuve.png' }];
    if (path.endsWith('/command/')) { calls.push(req.postDataJSON()); return { case: caseOrder({ status: 'RETOUR_DEMANDE' }), result: {} }; }
  });
  await page.goto('/static/'); await page.getByRole('button', { name: 'Commandes', exact: true }).first().click();
  const dialog = await openClinical(page);
  await dialog.locator('summary').filter({ hasText: 'Contrôler les éléments reçus' }).click();
  await dialog.getByLabel('Notes et motif de l’action', { exact: true }).fill('Empreinte à reprendre');
  await dialog.getByLabel('Photo de preuve (obligatoire en cas d’échec ou d’écart)').selectOption('proof');
  await dialog.getByRole('button', { name: 'Enregistrer la non-conformité' }).click();
  await expect.poll(() => calls.length).toBe(1);
  expect(calls[0].data).toMatchObject({ stage: 'PHYSICAL', photo: 'proof', notes: 'Empreinte à reprendre' });
  expect(calls[0].data).not.toHaveProperty('advance');
  await expect(dialog.getByRole('region', { name: 'Votre action' })).toContainText('En attente du dentiste');
});

for (const stage of ['CONTROLE_MODELE', 'CONTROLE_QUALITE']) {
  test(`${stage} failed evidence makes documented rework the primary next action`, async ({ page }) => {
    await session(page); const order = caseOrder({ status: stage });
    await mocks(page, path => path === '/api/prescriptions/' ? { results: [order], next: null } : path.endsWith('/evidence/') ? { inspections: [{ id: 1, stage: stage === 'CONTROLE_MODELE' ? 'MODEL' : 'QUALITY', passed: false, intake_revision: 1, production_attempt: 1, created_at: '2026-11-24T12:00:00Z' }] } : undefined);
    await page.goto('/static/'); await page.getByRole('button', { name: 'Commandes', exact: true }).first().click();
    const dialog = await openClinical(page);
    await dialog.getByRole('button', { name: 'Documenter la reprise', exact: true }).click();
    await expect(dialog.locator('details').filter({ has: page.locator('summary', { hasText: 'Signaler un problème' }) }).first()).toHaveAttribute('open', '');
    await expect(dialog.getByLabel('Origine', { exact: true })).toBeFocused();
    await expect(dialog.getByRole('button', { name: 'Enregistrer la reprise documentée' })).toBeDisabled();
  });
}

test.describe('planning from another browser timezone', () => {
test.use({ timezoneId: 'America/Los_Angeles' });
test('planning uses backend timezone and route destinations without saving a selection', async ({ page }) => {
  await session(page); const calls = [];
  const order = caseOrder({ status: 'PLANIFICATION', deadline_at: '2026-11-24T22:30:00Z', current_step: { planning_options: { CFAO: { next_key: 'SALLE_CAO', next_label: 'Destination du serveur' }, CONVENTIONNEL: { next_key: 'MODELE_TRAVAIL', next_label: 'Modèle de travail' } } } });
  await mocks(page, (path, req) => {
    if (path === '/api/prescriptions/') return { results: [order], next: null };
    if (path === '/api/planning/settings/') return { timezone: { zone: 'Africa/Casablanca', until: '2027-01-01T00:00:00Z', transitions: [{ at: '2026-01-01T00:00:00Z', offset: 120 }] } };
    if (path.endsWith('/command/')) { calls.push(req.postDataJSON()); return { case: order, result: {} }; }
  });
  await page.goto('/static/'); await page.getByRole('button', { name: 'Commandes', exact: true }).first().click();
  const dialog = await openClinical(page);
  await expect(dialog.getByLabel('Livraison prévue', { exact: true })).toHaveValue('2026-11-25');
  await expect(dialog.getByText('Échéance calculée : 25 novembre 2026')).toBeVisible();
  await dialog.getByLabel('Méthode de fabrication').selectOption('CFAO');
  await expect(dialog.getByRole('button', { name: 'Planifier → Destination du serveur' })).toBeVisible();
  await dialog.getByLabel('Méthode de fabrication').selectOption('CONVENTIONNEL');
  expect(calls).toEqual([]);
  await dialog.getByRole('button', { name: 'Planifier → Modèle de travail' }).click();
  await expect.poll(() => calls.length).toBe(1);
  expect(calls[0].data).toEqual({ production_method: 'CONVENTIONNEL', thermal_treatment: 'AUCUN', delivery_date: '2026-11-25' });
});
});

test('planning requires a manual date without a deadline and waits for a missing J+1 quote', async ({ page }) => {
  await session(page); let order = caseOrder({ status: 'PLANIFICATION' });
  await mocks(page, path => path === '/api/prescriptions/' ? { results: [order], next: null } : undefined);
  await page.goto('/static/'); await page.getByRole('button', { name: 'Commandes', exact: true }).first().click();
  let dialog = await openClinical(page);
  await expect(dialog.getByText('Échéance en cours de calcul')).toBeVisible();
  await dialog.getByLabel('Méthode de fabrication').selectOption('CFAO');
  await expect(dialog.locator('[data-primary-action]')).toBeDisabled();
  await dialog.getByLabel('Livraison prévue', { exact: true }).fill('2026-12-01');
  await expect(dialog.locator('[data-primary-action]')).toBeEnabled();
  order = caseOrder({ status: 'PLANIFICATION', total_price: null, delivery_service: 'NEXT_DAY' });
  await page.reload(); await page.getByRole('button', { name: 'Commandes', exact: true }).first().click(); dialog = await openClinical(page);
  await expect(dialog.getByRole('region', { name: 'Votre action' })).toContainText('Devis J+1 requis par la comptabilité');
  await expect(dialog.locator('[data-primary-action]')).toHaveCount(0);
});

for (const role of ['MANAGER', 'FAO']) {
  test(`${role} keeps the planning primary path and restricts forced advancement`, async ({ page }) => {
    await session(page, 'Laboratoire', role); const calls = []; const order = caseOrder({ status: 'FINITION' });
    await mocks(page, (path, req) => {
      if (path === '/api/prescriptions/') return { results: [order], next: null };
      if (path === '/api/planning/tasks/') return { results: [{ ...planningTask(), workflow_step: 'FINITION', source_status: 'FINITION' }], next: null };
      if (path.endsWith('/command/')) { calls.push(req.postDataJSON()); return { case: order, result: {} }; }
    });
    await page.goto('/static/'); await page.getByRole('button', { name: 'Commandes', exact: true }).first().click();
    const dialog = await openClinical(page);
    await expect(dialog.locator('[data-primary-action]:visible')).toHaveText('Démarrer');
    await expect(dialog.getByRole('button', { name: 'Forcer le passage à l’étape suivante' })).toBeHidden();
    await openProblems(page);
    const force = dialog.getByRole('button', { name: 'Forcer le passage à l’étape suivante' });
    if (role === 'MANAGER') {
      await expect(force).toBeDisabled();
      await dialog.getByLabel('Motif du problème', { exact: true }).fill('Correction supervisée documentée');
      await force.click(); await expect.poll(() => calls.length).toBe(1);
      expect(calls[0]).toEqual({ action: 'advance', data: { notes: 'Correction supervisée documentée' } });
    } else await expect(force).toHaveCount(0);
  });
}

test('monthly closing and credit use accounting endpoints', async ({ page }) => {
  await session(page); const calls = [];
  const period = { id: 'period-1', month: '2026-10-01', clinic: 1, closed_at: null };
  await mocks(page, (path, req) => {
    if (req.method() === 'POST') { calls.push([path, req.postDataJSON()]); return {}; }
    if (path === '/api/billing/periods/') return { results: [period], next: null };
    if (path === '/api/billing/statement-lines/') return { results: [{ id: 'line-1', period: period.id, prescription: id, base_amount: '1200', express_surcharge: '360', contested: false, excluded: false, snapshot: { patient_ref: 'PAT-TEST' } }], next: null };
    if (path === '/api/billing/invoices/') return { results: [{ id: 'invoice-1', number: 'INV-TEST', clinic_name: 'Cabinet test', total_amount: '1560', lines: [{ case_id: id, patient_ref: 'PAT-TEST', total_amount: '1560' }] }], next: null };
  });
  await page.goto('/static/'); await page.getByRole('button', { name: 'Facturation', exact: true }).first().click();
  await page.getByLabel('Cabinet et mois de livraison').selectOption(period.id); await page.getByRole('button', { name: 'Vérifier la clôture' }).click();
  await page.getByRole('button', { name: 'Confirmer la clôture et émettre la facture' }).click();
  await expect.poll(() => calls.length).toBe(1); expect(calls[0][0]).toBe('/api/billing/periods/period-1/close/');
  await page.getByText('Émettre un avoir sur une ligne', { exact: true }).click();
  await page.getByLabel('Dossier facturé').selectOption(id); await page.getByLabel('Montant de l’avoir (MAD)').fill('100.00'); await page.getByLabel('Motif', { exact: true }).fill('Ajustement');
  await page.getByRole('button', { name: 'Émettre l’avoir', exact: true }).click();
  await expect.poll(() => calls.length).toBe(2); expect(calls[1]).toEqual(['/api/billing/invoices/invoice-1/credit/', { prescription: id, amount: '100.00', reason: 'Ajustement' }]);
  await page.screenshot({ path: 'test-results/finance.png', fullPage: true });
});

test('stock consumption keeps case, lot and signed quantity', async ({ page }) => {
  await session(page); let payload;
  await mocks(page, (path, req) => {
    if (path === '/api/prescriptions/') return { results: [caseOrder()], next: null };
    if (path === '/api/inventory/') return [{ id: 1, material_name: 'Zircone', quantity: '10', unit: 'DISQUE' }];
    if (path === '/api/production-lots/') return { results: [{ id: 'lot-1', code: 'LOT-TEST', prescriptions: [id] }], next: null };
    if (path === '/api/inventory-transactions/' && req.method() === 'POST') { payload = req.postDataJSON(); return payload; }
  });
  await page.goto('/static/'); await page.getByRole('button', { name: 'Stocks et lots', exact: true }).click();
  await page.getByLabel('Mouvement', { exact: true }).selectOption('USAGE'); await page.getByLabel('Consommable', { exact: true }).selectOption('1');
  await page.getByLabel('Quantité positive').fill('0.5'); await page.getByLabel('Dossier de production').selectOption(id); await page.getByLabel('Lot de production', { exact: true }).selectOption('lot-1'); await page.getByLabel('Motif et traçabilité').fill('Usinage');
  await page.getByRole('button', { name: 'Enregistrer le mouvement' }).click();
  await expect.poll(() => payload).toBeTruthy(); expect(payload.quantity_changed).toBe('-0.5'); expect(payload.prescription).toBe(id); expect(payload.production_lot).toBe('lot-1'); expect(payload.idempotency_key).toMatch(/^[0-9a-f-]{36}$/);
});

test('expired sessions return to password login and clear tenant context', async ({ page }) => {
  await session(page); await mocks(page);
  await page.goto('/static/'); await page.evaluate(() => window.dispatchEvent(new Event('cabinet-session-expired')));
  await expect(page.getByRole('heading', { name: 'Votre espace Gestion Labo' })).toBeVisible();
  expect(await page.evaluate(() => sessionStorage.getItem('tenant_id'))).toBeNull();
  expect(await page.evaluate(() => sessionStorage.getItem('demo_token'))).toBeNull();
});

test('dentist approves a pending design and reports a linked zero-loss remake', async ({ page }) => {
  await session(page, 'Cabinet Dentaire'); let order = caseOrder({ status: 'VALIDATION_CAO', production_method: 'CFAO' }); const commands = [];
  const review = { id: 'review-1', attachment_id: 'design-1', version: 1, status: 'PENDING' };
  const errors = await mocks(page, (path, req) => {
    if (path === '/platform/dentist/orders/') return [order];
    if (path.endsWith('/evidence/')) return { design_reviews: [review], reworks: [], notifications: [] };
    if (path.endsWith('/command/')) { commands.push(req.postDataJSON()); order = { ...order, status: 'LIVRE', status_label: 'Livré' }; review.status = 'APPROVED'; return { case: order, result: {} }; }
  });
  await page.goto('/static/'); await page.getByRole('button', { name: 'Mes commandes (1)' }).click(); await openClinical(page);
  await page.getByRole('button', { name: 'Approuver', exact: true }).click();
  await openDossier(page);
  await expect(page.getByText('Version 1 · Approuvé')).toBeVisible();
  expect(commands[0]).toEqual({ action: 'design-decision', data: { review: 'review-1', decision: 'APPROVED', notes: '' } });
  await openProblems(page);
  await page.getByLabel('Étape de reprise').selectOption('SALLE_CAO'); await page.getByLabel('Cause', { exact: true }).fill('Ajustage'); await page.getByLabel('Action corrective').fill('Reconcevoir');
  await page.getByRole('button', { name: 'Enregistrer la reprise documentée' }).click();
  await expect.poll(() => commands.length).toBe(2); expect(commands[1].action).toBe('rework'); expect(commands[1].data.losses).toEqual([]); expect(errors).toEqual([]);
});

test('pending invoice PDF is explained without downloading JSON as a PDF', async ({ page }) => {
  await session(page); let downloads = 0; page.on('download', () => downloads++);
  await mocks(page, path => path === '/api/billing/invoices/' ? { results: [{ id: 'invoice-1', number: 'INV-PENDING', total_amount: '1200', lines: [] }], next: null } : undefined);
  await page.route('**/api/billing/invoices/invoice-1/pdf/', route => route.fulfill({ status: 202, json: { status: 'PDF_PENDING' }, headers: { 'Access-Control-Allow-Origin': '*' } }));
  await page.goto('/static/'); await page.getByRole('button', { name: 'Facturation', exact: true }).first().click(); await page.getByRole('button', { name: 'Télécharger le PDF' }).click();
  await expect(page.getByRole('alert')).toContainText('Document en préparation'); expect(downloads).toBe(0);
});

test('manual J+1 surcharge is sent as an accounting command', async ({ page }) => {
  await session(page, 'Laboratoire', 'COMPTABILITE'); const order = caseOrder({ status: 'PLANIFICATION', delivery_service: 'NEXT_DAY', total_price: null }); let command;
  await mocks(page, (path, req) => {
    if (path === '/api/prescriptions/') return { results: [order], next: null };
    if (path.endsWith('/command/')) { command = req.postDataJSON(); return { case: order, result: { total_price: '1500' } }; }
  });
  await page.goto('/static/'); await page.getByRole('button', { name: 'Commandes', exact: true }).first().click(); await page.getByRole('button', { name: 'Ouvrir le dossier PAT-TEST' }).click(); await openDossier(page);
  await page.getByLabel('Supplément urgence (MAD)').fill('300.00'); await page.getByRole('button', { name: 'Confirmer le devis laboratoire' }).click();
  await expect.poll(() => command).toBeTruthy(); expect(command).toEqual({ action: 'quote', data: { surcharge: '300.00', notes: '' } });
  await expect(page.getByRole('button', { name: 'Enregistrer les informations' })).toBeDisabled();
  await expect(page.getByLabel('Méthode de fabrication', { exact: true })).toHaveCount(0);
});

test('measured rework references original consumption rather than a stock deduction', async ({ page }) => {
  await session(page, 'Laboratoire', 'QUALITE'); const order = caseOrder({ status: 'CONTROLE_QUALITE', production_method: 'CFAO' }); let command;
  await mocks(page, (path, req) => {
    if (path === '/api/prescriptions/') return { results: [order], next: null };
    if (path === '/api/inventory-transactions/') return { results: [{ id: 'usage-1', transaction_type: 'USAGE', production_attempt: 1, quantity_changed: '-2.000000', material_name_snapshot: 'Zircone', unit_snapshot: 'DISQUE' }], next: null };
    if (path.endsWith('/command/')) { command = req.postDataJSON(); return { case: order, result: {} }; }
  });
  await page.goto('/static/'); await page.getByRole('button', { name: 'Commandes', exact: true }).first().click(); await page.getByRole('button', { name: 'Ouvrir le dossier PAT-TEST' }).click(); await openClinical(page);
  await openProblems(page);
  await page.getByLabel('Étape de reprise').selectOption('FINITION'); await page.getByLabel('Cause', { exact: true }).fill('Contact'); await page.getByLabel('Action corrective').fill('Corriger'); await page.getByLabel('Perte sur Zircone').fill('0.25'); await page.getByRole('button', { name: 'Enregistrer la reprise documentée' }).click();
  await expect.poll(() => command).toBeTruthy(); expect(command.action).toBe('rework'); expect(command.data.losses).toEqual([{ usage_id: 'usage-1', quantity: '0.25' }]);
});

test('laboratory navigation has no overview screen and lands on the work queue', async ({ page }) => {
  await session(page); await mocks(page);
  await page.goto('/static/');
  const nav = page.getByRole('navigation', { name: 'Navigation du laboratoire' });
  await expect(nav.getByRole('button', { name: 'Vue d’ensemble', exact: true })).toHaveCount(0);
  await expect(nav.getByRole('button', { name: 'À faire', exact: true })).toHaveAttribute('aria-current', 'page');
  await expect(page.getByLabel('Rechercher dans ma file')).toBeVisible();
  await expect(page.locator('.dental-dashboard, .featured-treatment, .smile-model')).toHaveCount(0);
});

test('alert popup opens the landing page with the alerts panel focused', async ({ page }) => {
  await session(page);
  await mocks(page, path => path === '/api/alerts/' ? [{ id: 'stock-1', type: 'stock', reference: 'STK-1', message: 'Zircone sous le seuil', section: 'stock', resource_id: 1, name: 'Zircone', overdue: false }] : undefined);
  await page.goto('/static/');
  await page.getByRole('button', { name: 'Stocks et lots', exact: true }).click();
  await page.getByRole('complementary', { name: 'Notification des alertes' }).getByRole('button', { name: /alerte au laboratoire/ }).click();
  const panel = page.getByRole('region', { name: 'Toutes les alertes' });
  await expect(panel).toBeVisible(); await expect(panel).toBeFocused();
  await expect(panel).toContainText('Zircone sous le seuil');
  await expect(page.getByLabel('Rechercher dans ma file')).toBeVisible();
});

test('dentist prescription selects teeth on the chart by click and keyboard', async ({ page }, testInfo) => {
  await session(page, 'Cabinet Dentaire'); let submission;
  await mocks(page, (path, req) => {
    if (path === '/platform/dentist/capacity-preview/') return { feasible: null, message: '' };
    if (path === '/platform/dentist/orders/' && req.method() === 'POST') { submission = req.postDataJSON(); return caseOrder({ total_price: '2700.00' }); }
  });
  await page.goto('/static/');
  await expect(page.getByRole('button', { name: 'Vue clinique', exact: true })).toHaveCount(0);
  await expect(page.getByLabel('Dent FDI')).toHaveCount(0);
  const submit = page.getByRole('button', { name: 'Envoyer la prescription', exact: true });
  await expect(page.getByText('Sélectionnez au moins une dent sur le schéma.')).toBeVisible();
  await page.getByLabel('Laboratoire destinataire').selectOption('labo1');
  await page.getByLabel('Cabinet et adresse de collecte').selectOption('1');
  await expect(submit).toBeDisabled();
  const tooth21 = page.getByRole('button', { name: 'Dent 21', exact: true }); const tooth11 = page.getByRole('button', { name: 'Dent 11', exact: true });
  await tooth21.click();
  await tooth11.focus(); await page.keyboard.press('Enter');
  await expect(tooth11).toHaveAttribute('aria-pressed', 'true'); await expect(tooth21).toHaveAttribute('aria-pressed', 'true');
  await expect(page.getByText('2 dents sélectionnées')).toBeVisible();
  const groups = page.locator('fieldset legend'); await expect(groups).toHaveText(['Dent 11', 'Dent 21']);
  await page.getByRole('button', { name: 'Dent 36', exact: true }).focus(); await page.keyboard.press('Space');
  await expect(groups).toHaveText(['Dent 11', 'Dent 21', 'Dent 36']);
  await page.getByRole('button', { name: 'Dent 36', exact: true }).click();
  await expect(groups).toHaveText(['Dent 11', 'Dent 21']);
  const first = page.getByRole('group', { name: 'Dent 11' }); const second = page.getByRole('group', { name: 'Dent 21' });
  await first.getByLabel('Fonction', { exact: true }).selectOption('Couronne'); await first.getByLabel('Forme', { exact: true }).selectOption('Anatomique');
  await first.getByLabel('Teinte', { exact: true }).selectOption('A2'); await first.getByLabel('Matériau', { exact: true }).selectOption('E-Max');
  await expect(second.getByLabel('Fonction', { exact: true })).toHaveValue('');
  await first.getByRole('button', { name: 'Appliquer à toutes les dents', exact: true }).click();
  await expect(second.getByLabel('Fonction', { exact: true })).toHaveValue('Couronne');
  await expect(second.getByLabel('Matériau', { exact: true })).toHaveValue('E-Max');
  await expect(second.getByRole('button', { name: 'Appliquer à toutes les dents' })).toHaveCount(0);
  await page.getByLabel('Référence patient anonyme').fill('PAT-TEETH');
  await page.getByLabel('Je confirme la désinfection').check();
  await page.setViewportSize({ width: 390, height: 844 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy();
  for (const control of [page.locator('.tooth-picker'), second.getByRole('button', { name: 'Retirer cette dent' }), submit])
    expect(await control.evaluate(element => element.getBoundingClientRect().right)).toBeLessThanOrEqual(390);
  expect(await page.locator('.tooth-chart').evaluate(element => element.scrollWidth > element.clientWidth)).toBeTruthy();
  await page.screenshot({ path: testInfo.outputPath('tooth-picker-390.png'), fullPage: true });
  await submit.click();
  await expect(page.getByText('Prescription enregistrée', { exact: true })).toBeVisible();
  expect(submission.clinical_items.map(item => item.tooth_number)).toEqual([11, 21]);
  expect(submission.clinical_items[1]).toEqual({ tooth_number: 21, function: 'Couronne', form: 'Anatomique', shade: 'A2', material: 'E-Max' });
});

test('dentist orders show stage progress and the expected delivery date', async ({ page }) => {
  await session(page, 'Cabinet Dentaire');
  const order = caseOrder({ status: 'SALLE_CAO', delivery_date: '2026-11-30', stages: [
    { key: 'COMMANDE', label: 'Commande', state: 'done' }, { key: 'CONCEPTION', label: 'Conception', state: 'current' }, { key: 'LIVRAISON', label: 'Livraison', state: 'todo' }] });
  const pending = caseOrder({ id: 'case-2', patient_ref: 'PAT-NODATE', stages: [] });
  await mocks(page, path => path === '/platform/dentist/orders/' ? [order, pending] : undefined);
  await page.goto('/static/');
  await expect(page.getByRole('button', { name: 'Vue clinique', exact: true })).toHaveCount(0);
  const strip = page.getByRole('list', { name: 'Étapes du dossier PAT-TEST' });
  await expect(strip.getByRole('listitem')).toHaveCount(3);
  await expect(strip.locator('[aria-current="step"]')).toHaveText('Conception');
  await expect(strip.getByRole('listitem').first()).toContainText('(terminée)');
  await expect(page.getByText('Livraison prévue : 30 novembre 2026')).toBeVisible();
  await expect(page.getByText('Date à confirmer par le laboratoire')).toBeVisible();
});

test('laboratory identity, matching favicon and resource tabs with two-decimal quantities', async ({ page }) => {
  await session(page);
  await mocks(page, path => path === '/api/inventory/' ? [{ id: 1, material_name: 'Zircone', quantity: '12.345678', unit: 'DISQUE', alert_threshold: '2.000000', unit_cost: '350.000000' }] : path === '/api/employee-profiles/' ? [{ id: 1, user: 1, role: 'CAO', contract_type: 'CDI', hire_date: '2026-01-01', is_available: true }] : undefined);
  await page.goto('/static/');
  await expect(page).toHaveTitle('Gestion Labo');
  await expect(page.getByRole('heading', { name: 'À faire', exact: true })).toBeVisible();
  await expect(page.getByLabel('Rechercher une rubrique')).toHaveCount(0);
  const icon = await page.locator('link[rel="icon"]').getAttribute('href');
  const logo = await page.getByRole('img', { name: 'Gestion Labo', exact: true }).getAttribute('src');
  expect(icon).toBe(logo);
  expect((await page.request.get(icon)).headers()['content-type']).toContain('image/svg+xml');
  await page.getByRole('button', { name: 'Stocks et lots', exact: true }).click();
  await expect(page.getByRole('tab', { name: 'Stock', exact: true })).toHaveAttribute('aria-selected', 'true');
  await expect(page.getByText('12,35 DISQUE', { exact: true })).toBeVisible();
  const quantity = page.getByLabel('Quantité positive');
  await expect(quantity).toHaveAttribute('step','0.01');
  await quantity.fill('1.23'); await quantity.press('4'); await expect(quantity).toHaveValue('1.23');
  await page.getByRole('tab', { name: 'Personnel', exact: true }).click();
  await expect(page.getByRole('cell', { name: 'CAO', exact: true })).toBeVisible();
  await page.getByRole('tab', { name: 'Matériaux', exact: true }).click();
  await expect(page.getByRole('cell', { name: '12,35', exact: true })).toBeVisible();
  await page.getByRole('button', { name: '+ Ajouter un consommable', exact: true }).click();
  await expect(page.getByLabel('Quantité initiale', { exact: false })).toHaveAttribute('step','0.01');
  await page.getByLabel('Quantité initiale', { exact: false }).fill('3.45');
  await page.getByLabel('Quantité initiale', { exact: false }).press('6');
  await expect(page.getByLabel('Quantité initiale', { exact: false })).toHaveValue('3.45');
});

const planningTask=()=>({id:'a94eb25f-4910-47cb-920d-8c1011539c01',prescription:id,workflow_step:'SALLE_CAO',title:'Conception CAO',patient_ref:'PAT-TEST',assigned_employee:1,employee_name:'Technicien CAO',required_role:'CAO',status:'READY',planned_start:'2026-11-09T07:00:00Z',planned_end:'2026-11-09T08:00:00Z',deadline:'2026-11-13T17:00:00Z',estimated_duration_minutes:60,production_attempt:1,intake_revision:1,sequence:10,generation:1,dependencies:[],locked:false,can_operate:true,external:false,source_status:'SALLE_CAO',assignment_explanation:{score:0.8,components:{qualification:1,workload:0.5}}});

test('quality reason and optional detail retain a rejected draft without selecting inspection checks', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await session(page);
  const order = caseOrder({ status: 'CONTROLE_QUALITE', status_label: 'Contrôle qualité final' });
  const commands = [];
  await mocks(page, path => path === '/api/prescriptions/' ? { results: [order], next: null } : undefined);
  await page.route('**/api/prescriptions/*/command/', async route => {
    const command = route.request().postDataJSON(); commands.push(command);
    const passed = ['margins', 'contacts', 'shade', 'occlusion', 'cosmetic', 'glazing', 'polishing'].every(key => command.data.checks[key]);
    await route.fulfill({ status: passed ? 200 : 400, json: passed ? { case: order, result: {} } : { detail: 'A failed inspection or gap requires photographic evidence.' }, headers: { 'Access-Control-Allow-Origin': '*' } });
  });
  await page.goto('/static/');
  await page.getByRole('button', { name: 'Ouvrir la navigation', exact: true }).click();
  await page.getByRole('button', { name: 'Commandes', exact: true }).first().click();
  await page.getByRole('button', { name: 'Ouvrir le dossier PAT-TEST' }).click();
  const dialog = await openClinical(page);
  const reason = dialog.getByRole('combobox', { name: 'Notes et motif de l’action — motif prédéfini' });
  await reason.selectOption('conform');
  await dialog.getByLabel('Notes et motif de l’action', { exact: true }).fill('Vérification au poste qualité.');
  expect(commands).toHaveLength(0);
  await expect(dialog.getByRole('checkbox').first()).not.toBeChecked();
  await dialog.getByRole('button', { name: 'Enregistrer la non-conformité' }).click();
  await expect(page.getByRole('alert')).toContainText('photo');
  await expect(reason).toHaveValue('conform');
  await expect(dialog.getByLabel('Notes et motif de l’action', { exact: true })).toHaveValue('Vérification au poste qualité.');
  for (const label of ['Marges', 'Contacts', 'Teinte', 'Occlusion', 'Esthétique', 'Glaçage', 'Polissage']) await dialog.getByLabel(`${label} conforme`, { exact: true }).check();
  await dialog.getByRole('button', { name: /Valider le contrôle/ }).click();
  await expect.poll(() => commands.length).toBe(2);
  expect(commands[1].data.notes).toBe('Contrôle qualité : critères contrôlés et conformes.\nVérification au poste qualité.');
  await expect(reason).toHaveValue('');
  await expect(dialog.getByLabel('Notes et motif de l’action', { exact: true })).toHaveValue('');
  await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
});

test('cycle reason enables an explicit confirmation and free text remains available', async ({ page }) => {
  await session(page);
  const calls = []; let phase = 'CYCLE';
  await planningMocks(page, (path, req, url, task) => {
    Object.assign(task, { workflow_step: 'USINAGE_CNC', source_status: 'USINAGE_CNC', status: 'IN_PROGRESS', resource_phase: phase, setup_minutes: 10, unload_minutes: 10, title: 'Usinage CNC' });
    if (path === '/api/prescriptions/') return { results: [caseOrder({ status: 'USINAGE_CNC', status_label: 'Usinage CNC' })], next: null };
    if (path.endsWith('/command/') && req.method() === 'POST') { calls.push(req.postDataJSON()); phase = 'AWAITING_UNLOAD'; return { case: caseOrder({ status: 'USINAGE_CNC' }), result: {} }; }
  });
  await page.goto('/static/');
  await page.getByRole('button', { name: 'Commandes', exact: true }).first().click();
  await page.getByRole('button', { name: 'Ouvrir le dossier PAT-TEST' }).click();
  const dialog = page.getByRole('dialog', { name: /Dossier clinique/ });
  const confirm = dialog.getByRole('button', { name: 'Confirmer la fin réelle du cycle' });
  await expect(confirm).toBeDisabled();
  const reason = dialog.getByRole('combobox', { name: 'Commentaire de progression / motif du blocage — motif prédéfini' });
  await reason.selectOption('cycle-finished');
  await expect(confirm).toBeEnabled();
  expect(calls).toHaveLength(0);
  await confirm.click();
  await expect.poll(() => calls.length).toBe(1);
  expect(calls[0]).toMatchObject({ action: 'planning-cycle-finished', data: { notes: 'Cycle terminé, pièce encore dans l’équipement.', task: planningTask().id } });
  await expect(dialog.getByRole('button', { name: 'Commencer le déchargement' })).toBeVisible();
  await expect(reason).toHaveValue('');
  await dialog.getByLabel('Commentaire de progression / motif du blocage', { exact: true }).fill('Situation exceptionnelle à expliquer.');
  await openProblems(page);
  await dialog.getByRole('button', { name: 'Bloquer la tâche' }).click();
  await expect.poll(() => calls.length).toBe(2);
  expect(calls[1]).toMatchObject({ action: 'planning-block', data: { notes: 'Situation exceptionnelle à expliquer.' } });
});

async function planningMocks(page,handler){
  const task=planningTask();
  await mocks(page,async(path,req,url)=>{
    const override=await handler?.(path,req,url,task);if(override!==undefined)return override;
    if(path==='/api/prescriptions/')return {results:[caseOrder({status:'SALLE_CAO',status_label:'Conception CAO'})],next:null};
    if(path==='/api/employee-profiles/')return [{id:1,user:1,name:'Technicien CAO',role:'CAO',is_available:true}];
    if(path==='/api/planning/tasks/'||path==='/api/planning/calendar/')return {count:1,results:[task],next:null};
    if(path==='/api/planning/workload/')return {count:1,results:[{employee:1,name:'Technicien CAO',role:'CAO',available:true,available_minutes:540,planned_minutes:60,utilization:11.11}],risks:[]};
    if(path==='/api/planning/settings/')return {timezone:{zone:'Africa/Casablanca',until:'2027-01-01T00:00:00Z',transitions:[{at:'2026-10-01T00:00:00Z',offset:60}]},working_days:[0,1,2,3,4],open_time:'08:00',close_time:'18:00',break_start:'12:00',break_end:'13:00',horizon_days:28,weights:{qualification:30,availability:25,workload:20,urgency:15,continuity:10},step_rules:{},defaults:{SALLE_CAO:{title:'Conception CAO',role:'CAO',duration:60,machine_type:'',qualifications:[]}}};
  });
}

for (const [status, expected, overrides] of [
  ['DEMANDE_RECUE', 'Accepter et analyser', { accepted: false }],
  ['ANALYSE_DEMANDE', 'Analyse validée → Ramassage', {}],
  ['PLANIFICATION', 'Planifier', {}],
  ['CONTROLE_MODELE', 'Enregistrer la non-conformité', {}],
  ['SALLE_CAO', 'Soumettre au dentiste et suspendre le délai', { design_validation_requested: true }],
  ['FINITION', 'Démarrer', {}],
  ['A_REFAIRE', 'Démarrer', {}],
]) {
  test(`workspace exposes one primary action for ${status} and keeps exceptions collapsed`, async ({ page }) => {
    await session(page);
    const order = caseOrder({ status, ...overrides });
    const task = { ...planningTask(), workflow_step: status, source_status: status };
    await mocks(page, path => path === '/api/prescriptions/' ? { results: [order], next: null } : path === '/api/planning/tasks/' ? { results: [task], next: null } : undefined);
    await page.goto('/static/'); await page.getByRole('button', { name: 'Commandes', exact: true }).first().click();
    await page.getByRole('button', { name: 'Ouvrir le dossier PAT-TEST' }).click();
    const dialog = page.getByRole('dialog');
    await expect(dialog.locator('[data-primary-action]:visible')).toHaveCount(1);
    await expect(dialog.locator('[data-primary-action]:visible')).toHaveText(expected);
    await expect(dialog.getByRole('tab')).toHaveCount(0);
    await expect(dialog.locator('[draggable="true"]')).toHaveCount(0);
    await expect(dialog.getByLabel('Cause', { exact: true })).not.toBeVisible();
    await expect(dialog.getByRole('heading', { name: 'Documents privés' })).not.toBeVisible();
    await openProblems(page); await expect(dialog.getByLabel('Cause', { exact: true })).toBeVisible();
  });
}
for (const [phase, expected] of [['SETUP', 'Chargement terminé : lancer le cycle'], ['CYCLE', 'Confirmer la fin réelle du cycle'], ['AWAITING_UNLOAD', 'Commencer le déchargement'], ['UNLOADING', 'Confirmer le déchargement et terminer']]) {
  test(`equipment ${phase} has one explicit primary action`, async ({ page }) => {
    await session(page);
    await planningMocks(page, (path, req, url, task) => {
      Object.assign(task, { workflow_step: 'USINAGE_CNC', source_status: 'USINAGE_CNC', status: 'IN_PROGRESS', resource_phase: phase, setup_minutes: 10, unload_minutes: 10 });
      if (path === '/api/prescriptions/') return { results: [caseOrder({ status: 'USINAGE_CNC' })], next: null };
    });
    await page.goto('/static/'); await page.getByRole('button', { name: 'Commandes', exact: true }).first().click(); await page.getByRole('button', { name: 'Ouvrir le dossier PAT-TEST' }).click();
    await expect(page.getByRole('dialog').locator('[data-primary-action]:visible')).toHaveCount(1);
    await expect(page.getByRole('dialog').locator('[data-primary-action]:visible')).toHaveText(expected);
  });
}
for (const [status, message] of [['VALIDATION_CAO', 'En attente du dentiste'], ['EN_ROUTE_LABO', 'En attente du coursier'], ['CLOTURE', 'Dossier clôturé']]) {
  test(`workspace explains ${status} without offering a lab transition`, async ({ page }) => {
    await session(page);
    await mocks(page, path => path === '/api/prescriptions/' ? { results: [caseOrder({ status })], next: null } : undefined);
    await page.goto('/static/'); await page.getByRole('button', { name: 'Commandes', exact: true }).first().click(); await page.getByRole('button', { name: 'Ouvrir le dossier PAT-TEST' }).click();
    const action = page.getByRole('region', { name: 'Votre action' });
    await expect(action).toContainText(message); await expect(action.locator('[data-primary-action]:visible')).toHaveCount(0);
  });
}
test('workspace shows all teeth and a read-only current stage at 390px', async ({ page }, info) => {
  await page.setViewportSize({ width: 390, height: 844 }); await session(page);
  const order = caseOrder({ clinical_items: [{ tooth_number: 11, function: 'Couronne', form: 'Anatomique', material: 'Zircone', shade: 'A1' }, { tooth_number: 21, function: 'Bridge', form: 'Autre forme', material: 'E-Max', shade: 'B2' }] });
  await mocks(page, path => path === '/api/prescriptions/' ? { results: [order], next: null } : undefined);
  await page.goto('/static/'); await page.getByRole('button', { name: 'Ouvrir la navigation', exact: true }).click(); await page.getByRole('button', { name: 'Commandes', exact: true }).first().click();
  await page.getByRole('button', { name: 'Ouvrir le dossier PAT-TEST' }).click();
  const dialog = page.getByRole('dialog'); const header = dialog.getByRole('region', { name: 'Résumé clinique' });
  await expect(header).toContainText('Dent 11'); await expect(header).toContainText('Dent 21'); await expect(header).toContainText('E-Max'); await expect(header).toContainText('B2');
  await expect(dialog.getByRole('navigation', { name: 'Étapes du dossier' }).locator('[aria-current="step"]')).toHaveCount(1);
  await expect.poll(() => dialog.evaluate(element => element.scrollWidth <= element.clientWidth)).toBe(true);
  await page.screenshot({ path: info.outputPath('workspace-header-390.png'), fullPage: true });
});
test('dossier history preserves user notes and empty notes do not become errors', async ({ page }) => {
  await session(page); const order = caseOrder({ status: 'CLOTURE' });
  await mocks(page, path => path === '/api/prescriptions/' ? { results: [order], next: null } : path.endsWith('/evidence/') ? { design_reviews: [], inspections: [{ id: 1, stage: 'QUALITY', created_at: '2026-11-24T10:00:00Z', checks: { margins: true }, notes: '' }], events: [{ id: 'event', created_at: '2026-11-24T11:00:00Z', notes: 'Custom note 123' }], reworks: [] } : undefined);
  await page.goto('/static/'); await page.getByRole('button', { name: 'Commandes', exact: true }).first().click(); await page.getByRole('button', { name: 'Ouvrir le dossier PAT-TEST' }).click();
  const dialog = await openDossier(page); await dialog.locator('summary').filter({ hasText: /^Historique et preuves$/ }).click();
  await expect(dialog).toContainText('Custom note 123'); await expect(dialog).toContainText('Marges : oui');
  await expect(dialog).not.toContainText('Action impossible');
});
test('future work and another assignee explain the blocker without a start button', async ({ page }) => {
  await session(page, 'Laboratoire', 'FAO'); let mine = false;
  const order = caseOrder({ status: 'FINITION' });
  await mocks(page, path => path === '/api/prescriptions/' ? { results: [order], next: null } : path === '/api/planning/tasks/' ? { results: [{ ...planningTask(), workflow_step: 'FINITION', source_status: 'FINITION', can_operate: mine, can_start_now: false, employee_name: mine ? 'Moi' : 'Autre technicien', planned_start: '2099-01-01T10:00:00Z' }], next: null } : undefined);
  await page.goto('/static/'); await page.getByRole('button', { name: 'Commandes', exact: true }).first().click(); await page.getByRole('button', { name: 'Ouvrir le dossier PAT-TEST' }).click();
  const action = page.getByRole('region', { name: 'Votre action' });
  await expect(action).toContainText('Tâche affectée à Autre technicien'); await expect(action.locator('[data-primary-action]')).toHaveCount(0);
  mine = true; await page.getByRole('button', { name: 'Actualiser le dossier', exact: true }).click();
  await expect(action).toContainText('Prévu le 01/01/2099'); await expect(action.locator('[data-primary-action]')).toHaveCount(0);
});
test('dentist design corrections use one explicit decision and never load lab planning', async ({ page }) => {
  await session(page, 'Cabinet Dentaire'); const commands = []; const planningReads = [];
  const order = caseOrder({ status: 'VALIDATION_CAO' });
  await mocks(page, (path, req) => {
    if (path.startsWith('/api/planning/')) planningReads.push(path);
    if (path === '/platform/dentist/orders/') return [order];
    if (path.endsWith('/evidence/')) return { design_reviews: [{ id: 'review-1', version: 1, status: 'PENDING', attachment_id: 'design-1' }], inspections: [], reworks: [] };
    if (path.endsWith('/command/')) { commands.push(req.postDataJSON()); return { case: order, result: {} }; }
  });
  await page.goto('/static/'); await page.getByRole('article', { name: 'Action pour PAT-TEST' }).getByRole('button').click();
  const dialog = page.getByRole('dialog'); await expect(dialog.locator('[data-primary-action]:visible')).toHaveCount(1);
  await dialog.getByLabel('Décision du design').selectOption('CHANGES_REQUESTED');
  const submit = dialog.getByRole('button', { name: 'Demander des corrections', exact: true }); await expect(submit).toBeDisabled();
  await dialog.getByRole('combobox', { name: 'Notes et motif de l’action — motif prédéfini' }).selectOption('changes');
  expect(commands).toHaveLength(0); await submit.click(); await expect.poll(() => commands.length).toBe(1);
  expect(commands[0]).toEqual({ action: 'design-decision', data: { review: 'review-1', decision: 'CHANGES_REQUESTED', notes: 'Corrections du design nécessaires avant approbation.' } });
  expect(planningReads).toEqual([]); await openDossier(page); await expect(dialog.getByRole('heading', { name: 'Informations du dossier' })).toHaveCount(0);
});
test('dentist delivery PIN disappears after confirmation and fitting remains explicit', async ({ page }) => {
  await session(page, 'Cabinet Dentaire'); const commands = []; let order = caseOrder({ status: 'EN_ROUTE_CABINET' });
  await mocks(page, (path, req) => {
    if (path === '/platform/dentist/orders/') return [order];
    if (path.endsWith('/command/')) { expect(req.headers()['idempotency-key']).toMatch(/^[0-9a-f-]{36}$/); commands.push(req.postDataJSON()); order = caseOrder({ status: 'LIVRE' }); return { case: order, result: {} }; }
  });
  await page.goto('/static/'); await page.getByRole('article', { name: 'Action pour PAT-TEST' }).getByRole('button').click();
  const dialog = page.getByRole('dialog'); await dialog.getByLabel('PIN de livraison', { exact: true }).fill('0789'); await dialog.getByRole('button', { name: 'Valider le PIN', exact: true }).click();
  await expect(dialog.getByLabel('PIN de livraison', { exact: true })).toHaveCount(0);
  await expect(dialog.getByRole('button', { name: 'Valider l’essayage clinique', exact: true })).toBeVisible();
  expect(commands).toEqual([{ action: 'confirm-delivery', data: { pin: '0789' } }]);
});
test('a successful command followed by a refresh failure cannot be submitted again', async ({ page }) => {
  await session(page); let committed = false; let writes = 0;
  const order = caseOrder({ status: 'SALLE_CAO' });
  await planningMocks(page, path => {
    if (path.endsWith('/command/')) { committed = true; writes++; return { case: order, result: {} }; }
  });
  await page.route('**/evidence/', async route => { if (committed) await route.abort('failed'); else await route.fallback(); });
  await page.goto('/static/'); await page.getByRole('button', { name: 'Commandes', exact: true }).first().click(); await page.getByRole('button', { name: 'Ouvrir le dossier PAT-TEST' }).click();
  await page.getByRole('button', { name: 'Démarrer', exact: true }).click();
  await expect(page.getByRole('alert')).toContainText('Action enregistrée');
  await expect(page.getByRole('region', { name: 'Votre action' })).toContainText('Actualisez');
  await expect(page.getByRole('region', { name: 'Votre action' }).locator('[data-primary-action]')).toHaveCount(0);
  expect(writes).toBe(1);
});
test('planning calendar, Gantt and workload display backend tasks and filters',async({page},info)=>{
  await session(page);const queries=[];
  await planningMocks(page,(path,req,url)=>{if(path==='/api/planning/tasks/'||path==='/api/planning/calendar/')queries.push(Object.fromEntries(url.searchParams));});
  await page.goto('/static/');await page.getByRole('button',{name:'Planning',exact:true}).click();
  await page.getByLabel('Date du planning').fill('2026-11-09');
  await expect(page.getByTitle('PAT-TEST · Conception CAO · Technicien CAO',{exact:true})).toBeVisible();
  await page.getByLabel('Employé',{exact:true}).selectOption('1');
  await expect.poll(()=>queries.some(q=>q.employee==='1')).toBe(true);
  await expect(page.locator('.planning-time-block small')).toContainText('08:00');
  await page.screenshot({path:info.outputPath('planning-calendar-desktop.png'),fullPage:true});
  await page.getByRole('button',{name:'Gantt',exact:true}).click();await expect(page.locator('.planning-gantt-bar')).toBeVisible();
  await page.getByRole('button',{name:'Charge',exact:true}).click();await expect(page.getByRole('cell',{name:'11.11 %',exact:true})).toBeVisible();
  await page.setViewportSize({width:390,height:844});
  await expect(page.getByRole('heading',{name:'Planning de fabrication'})).toBeVisible();
  await expect.poll(()=>page.locator('.clinical-sidebar').evaluate(el=>el.getBoundingClientRect().right)).toBeLessThanOrEqual(0);
  await page.locator('.planning-workload-table').scrollIntoViewIfNeeded();
  await expect.poll(()=>page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBe(true);
  await page.screenshot({path:info.outputPath('planning-workload-mobile.png'),fullPage:true});
});
test('planning task panel opens the same case workspace and restores focus', async ({ page }) => {
  await session(page); await planningMocks(page);
  await page.goto('/static/'); await page.getByRole('button', { name: 'Planning', exact: true }).click();
  await page.getByLabel('Date du planning').fill('2026-11-09');
  await page.getByTitle('PAT-TEST · Conception CAO · Technicien CAO', { exact: true }).click();
  const drawer = page.getByRole('dialog', { name: 'Tâche PAT-TEST' });
  const opener = drawer.getByRole('button', { name: 'Ouvrir le dossier PAT-TEST' });
  await opener.click(); const workspace = page.getByRole('dialog', { name: 'Dossier clinique — PAT-TEST' });
  await expect(workspace.getByRole('region', { name: 'Votre action' })).toBeVisible();
  await expect(workspace.locator('[data-primary-action]:visible')).toHaveCount(1);
  await page.keyboard.press('Escape'); await expect(workspace).toHaveCount(0); await expect(opener).toBeFocused();
  await expect(drawer).toBeVisible();
});
test('supervised planning assignment carries UUID and reports an API conflict',async({page})=>{
  await session(page);let payload;let key;
  await planningMocks(page);
  await page.route('**/api/planning/tasks/*/assign/',async route=>{payload=route.request().postDataJSON();key=route.request().headers()['idempotency-key'];await route.fulfill({status:400,json:{detail:'Conflit de réservation : employé déjà occupé.'},headers:{'Access-Control-Allow-Origin':'*'}});});
  await page.goto('/static/');await page.getByRole('button',{name:'Planning',exact:true}).click();await page.getByLabel('Date du planning').fill('2026-11-09');
  await page.getByTitle('PAT-TEST · Conception CAO · Technicien CAO',{exact:true}).click();
  await page.getByRole('combobox',{name:'Motif de supervision — motif prédéfini'}).selectOption('priority');
  await page.getByLabel('Motif de supervision',{exact:true}).fill('Cabinet disponible cet après-midi.');
  await page.getByRole('button',{name:'Affecter et verrouiller',exact:true}).click();
  await expect(page.getByRole('alert')).toContainText('Conflit de réservation');
  expect(payload.employee).toBe(1);expect(payload.start).toBe('2026-11-09T07:00:00.000Z');expect(key).toMatch(/^[0-9a-f-]{36}$/);
  expect(payload.notes).toBe('Réaffectation pour respecter la priorité de livraison.\nCabinet disponible cet après-midi.');
  await expect(page.getByLabel('Motif de supervision',{exact:true})).toHaveValue('Cabinet disponible cet après-midi.');
});
test('manufacturing task start and completion use existing case-command endpoint',async({page})=>{
  await session(page);const calls=[];
  await planningMocks(page,(path,req,url,task)=>{
    if(path.endsWith('/command/')&&req.method()==='POST'){
      const payload=req.postDataJSON();calls.push(payload);
      task.status=payload.action==='planning-start'?'IN_PROGRESS':'COMPLETED';
      return {case:caseOrder({status:'SALLE_CAO'}),result:{task_id:task.id,status:task.status}};
    }
  });
  await page.goto('/static/');await page.getByRole('button',{name:'Commandes',exact:true}).first().click();await page.getByRole('button',{name:'Ouvrir le dossier PAT-TEST'}).click();
  await page.getByRole('button',{name:'Démarrer',exact:true}).click();await page.getByRole('button',{name:'Terminer l’étape',exact:true}).click();
  await expect.poll(()=>calls.length).toBe(2);expect(calls.map(c=>c.action)).toEqual(['planning-start','planning-complete']);expect(calls[0].data.task).toBe(planningTask().id);
});

for (const width of [1440, 390]) {
  test(`clinical checkpoint opens in a dialog with visible French feedback at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 740 });
    await session(page);
    const commands = [];
    await mocks(page, path => path === '/api/prescriptions/' ? { results: [caseOrder({ status: 'CONTROLE_DOSSIER' })], next: null } : undefined);
    await page.route('**/api/prescriptions/*/command/', async route => {
      const command = route.request().postDataJSON(); commands.push(command);
      await route.fulfill({ status: command.data.checks.hygiene ? 200 : 400,
        json: command.data.checks.hygiene ? { case: caseOrder({ status: 'CONTROLE_DOSSIER' }), result: {} } : { detail: 'A failed inspection or gap requires photographic evidence.' },
        headers: { 'Access-Control-Allow-Origin': '*' } });
    });
    await page.goto('/static/');
    if (width < 650) await page.getByRole('button', { name: 'Ouvrir la navigation', exact: true }).click();
    await page.getByRole('button', { name: 'Commandes', exact: true }).first().click();
    await page.getByRole('button', { name: 'Ouvrir le dossier PAT-TEST' }).click();
    const dialog = page.getByRole('dialog', { name: 'Dossier clinique — PAT-TEST' });
    await expect(dialog).toBeVisible();
    await expect(dialog.getByRole('region', { name: 'Votre action' })).toContainText('Inspection');
    await expect(dialog.getByRole('tab')).toHaveCount(0);
    for (const label of ['Absence de déformation', 'Absence de bulles', 'Limites lisibles', 'Occlusion'])
      await dialog.getByLabel(label + ' conforme', { exact: true }).check();
    await dialog.getByRole('button', { name: 'Enregistrer la non-conformité' }).click();
    const error = page.getByRole('alert');
    await expect(error).toContainText('photo de preuve');
    const bounds = await error.boundingBox();
    expect(bounds.y).toBeLessThan(100);
    expect(await error.evaluate(element => {
      const rect = element.getBoundingClientRect();
      return element.contains(document.elementFromPoint(rect.x + 10, rect.y + 10));
    })).toBe(true);
    await dialog.getByLabel('Hygiène conforme', { exact: true }).check();
    await dialog.getByRole('button', { name: /Valider le contrôle/ }).click();
    await expect(page.getByRole('alert')).toHaveCount(0);
    await expect(page.locator('.app-notification').getByRole('status')).toContainText('Action enregistrée.');
    expect(commands[1].data.checks.hygiene).toBe(true);
    expect(commands[1].data.stage).toBe('PHYSICAL');
    await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await page.screenshot({ path: `test-results/clinical-dialog-${width}.png`, fullPage: true });
    await page.keyboard.press('Escape');
    await expect(dialog).toHaveCount(0);
    await page.getByRole('button', { name: 'Ouvrir le dossier PAT-TEST' }).click();
    await expect(dialog).toBeVisible();
    await page.keyboard.press('Escape');
    await expect(page.getByRole('button', { name: 'Ouvrir le dossier PAT-TEST' })).toBeFocused();
  });
}

test('courier scans each custody step explicitly and hides successful QR and PIN controls', async ({ page }) => {
  await session(page, 'Coursier');
  const courierOrder = status => ({ id, patient_ref: 'PAT-TEST', status, status_label: caseSteps[status][3] });
  let order = courierOrder('ATTENTE_RAMASSAGE'); const commands = [];
  await mocks(page, path => path === '/api/prescriptions/' ? { results: [order], next: null } : undefined);
  await page.route('**/api/prescriptions/*/command/', async route => {
    const command = route.request().postDataJSON(); commands.push(command);
    const valid = command.action === 'confirm-delivery' ? command.data.pin === '0789' : command.data.qr_token === 'signed-token';
    if (valid) order = courierOrder({ pickup: 'EN_ROUTE_LABO', 'lab-deposit': 'A_CONFIRMER', 'confirm-delivery': 'LIVRE' }[command.action]);
    await route.fulfill({ status: valid ? 200 : 400, json: valid ? { case: order, result: {} }
      : { detail: command.action === 'confirm-delivery' ? 'Invalid delivery PIN.' : 'Invalid or expired QR code.' },
    headers: { 'Access-Control-Allow-Origin': '*' } });
  });
  await page.goto('/static/');
  await expect(page.getByLabel('Contenu du QR signé du dossier')).toHaveCount(0);
  await page.getByRole('button', { name: 'Confirmer la collecte', exact: true }).click();
  await page.getByLabel('Contenu du QR signé du dossier').fill('bad-token');
  await page.getByRole('dialog').getByRole('button', { name: 'Confirmer la collecte', exact: true }).click();
  await expect(page.getByRole('alert')).toContainText('Code QR invalide ou expiré');
  await expect(page.getByRole('dialog')).toBeVisible();
  await page.getByLabel('Contenu du QR signé du dossier').fill('signed-token');
  await page.getByRole('dialog').getByRole('button', { name: 'Confirmer la collecte', exact: true }).click();
  await expect(page.getByRole('dialog')).toHaveCount(0);
  await expect(page.getByLabel('Contenu du QR signé du dossier')).toHaveCount(0);
  await expect(page.getByRole('button', { name: 'Confirmer le dépôt au labo' })).toHaveCount(0);
  expect(commands.filter(command => command.action === 'lab-deposit')).toHaveLength(0);
  await page.getByRole('button', { name: 'Scanner à l’arrivée au laboratoire' }).click();
  await expect(page.getByLabel('Contenu du QR signé du dossier')).toHaveValue('');
  await page.getByLabel('Contenu du QR signé du dossier').fill('signed-token');
  await page.getByRole('button', { name: 'Valider le QR d’arrivée' }).click();
  await expect(page.getByRole('dialog')).toHaveCount(0);
  expect(commands.filter(command => command.action === 'lab-deposit')).toHaveLength(1);
  // Separate delivery-stage fixture; pickup never silently grants delivery.
  order = courierOrder('EN_ROUTE_CABINET');
  await page.getByRole('button', { name: 'Actualiser les commandes' }).click();
  await page.getByRole('button', { name: 'Confirmer la livraison', exact: true }).click();
  await page.getByLabel('PIN réel de livraison').fill('0000');
  await page.getByRole('dialog').getByRole('button', { name: 'Confirmer la livraison', exact: true }).click();
  await expect(page.getByRole('alert')).toContainText('PIN');
  await page.getByLabel('PIN réel de livraison').fill('0789');
  await page.getByRole('dialog').getByRole('button', { name: 'Confirmer la livraison', exact: true }).click();
  await expect(page.getByRole('dialog')).toHaveCount(0);
  await expect(page.getByLabel('PIN réel de livraison')).toHaveCount(0);
  await expect(page.getByText('Livré', { exact: true })).toBeVisible();
});


async function completeCapacityForm(page) {
  await page.getByRole('button', { name: 'Dent 11', exact: true }).click();
  await page.getByLabel('Laboratoire destinataire').selectOption('labo1');
  await page.getByLabel('Cabinet et adresse de collecte').selectOption('1');
  await page.getByLabel('Référence patient anonyme').fill('CAPACITY-TEST');
  await page.getByLabel('Fonction', { exact: true }).selectOption('Couronne');
  await page.getByLabel('Forme', { exact: true }).selectOption('Anatomique');
  await page.getByLabel('Teinte', { exact: true }).selectOption('A1');
  await page.getByLabel('Matériau', { exact: true }).selectOption('Zircone');
  await page.getByLabel('Je confirme la désinfection').check();
}

const capacityWarning = { requested_deadline: '2026-11-27T10:00:00+01:00', feasible: false,
  earliest_feasible_date: '2026-11-30', reason_code: 'CAPACITY', provisional: true };

test('advisory capacity at 390px permits explicit submission without saving a route', async ({ page }, testInfo) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await session(page, 'Cabinet Dentaire');
  let submission; let previews = 0;
  const errors = await mocks(page, (path, req) => {
    if (path === '/platform/dentist/capacity-preview/') { previews++; return capacityWarning; }
    if (path === '/platform/dentist/orders/' && req.method() === 'POST') {
      submission = req.postDataJSON(); return caseOrder({ total_price: '1200.00' });
    }
  });
  await page.goto('/static/'); await completeCapacityForm(page);
  const notice = page.getByRole('status', { name: 'Capacité indicative' });
  await expect(notice).toContainText('30 novembre 2026');
  await expect(notice).toContainText('Date provisoire');
  await expect(page.getByText('Action enregistrée.', { exact: true })).toHaveCount(0);
  await expect(page.getByRole('button', { name: 'Envoyer la prescription', exact: true })).toBeEnabled();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy();
  await page.screenshot({ path: testInfo.outputPath('capacity-390.png'), fullPage: true });
  await notice.getByRole('button', { name: 'Envoyer quand même' }).click();
  await expect(page.getByText('Prescription enregistrée', { exact: true })).toBeVisible();
  expect(submission.delivery_service).toBe('STANDARD'); expect(submission).not.toHaveProperty('production_method');
  expect(previews).toBeGreaterThan(0); expect(errors).toEqual([]);
});

test('capacity slower-service choice changes J+1 to J+2 then J+4 and re-previews', async ({ page }) => {
  await session(page, 'Cabinet Dentaire'); const calls = [];
  await mocks(page, (path, req) => {
    if (path === '/platform/dentist/capacity-preview/') { calls.push(req.postDataJSON()); return capacityWarning; }
  });
  await page.goto('/static/'); await page.getByRole('button', { name: 'Dent 11', exact: true }).click();
  await page.getByLabel('Laboratoire destinataire').selectOption('labo1');
  await page.getByLabel('Service de livraison').selectOption('NEXT_DAY');
  await expect(page.getByRole('button', { name: 'Choisir un délai plus long' })).toBeVisible();
  await page.getByRole('button', { name: 'Choisir un délai plus long' }).click();
  await expect(page.getByLabel('Service de livraison')).toHaveValue('EXPRESS');
  await expect.poll(() => calls.at(-1)?.delivery_service).toBe('EXPRESS');
  await page.getByRole('button', { name: 'Choisir un délai plus long' }).click();
  await expect(page.getByLabel('Service de livraison')).toHaveValue('STANDARD');
  await expect.poll(() => calls.at(-1)?.delivery_service).toBe('STANDARD');
  await expect(page.getByRole('button', { name: 'Choisir un délai plus long' })).toHaveCount(0);
  expect(calls.some(body => body.delivery_service === 'NEXT_DAY')).toBeTruthy();
  expect(calls.every(body => body.clinical_item_count === 1)).toBeTruthy();
});

for (const unavailable of ['unknown', 'offline']) {
  test(`capacity preview ${unavailable} never blocks a complete prescription`, async ({ page }) => {
    await session(page, 'Cabinet Dentaire'); let submission;
    await mocks(page, (path, req) => {
      if (path === '/platform/dentist/capacity-preview/') return { feasible: null, message: '' };
      if (path === '/platform/dentist/orders/' && req.method() === 'POST') {
        submission = req.postDataJSON(); return caseOrder({ total_price: '1200.00' });
      }
    });
    if (unavailable === 'offline') await page.route('**/platform/dentist/capacity-preview/', route => route.abort('failed'));
    await page.goto('/static/'); await completeCapacityForm(page);
    // Wait until the advisory request has actually completed or failed.
    await expect.poll(async () => page.evaluate(() => performance.getEntriesByType('resource').some(item => item.name.includes('capacity-preview')))).toBeTruthy();
    await expect(page.getByRole('status', { name: 'Capacité indicative' })).toHaveCount(0);
    await expect(page.getByText('Action enregistrée.', { exact: true })).toHaveCount(0);
    await page.getByRole('button', { name: 'Envoyer la prescription', exact: true }).click();
    await expect(page.getByText('Prescription enregistrée', { exact: true })).toBeVisible();
    expect(submission.patient_ref).toBe('CAPACITY-TEST');
  });
}


async function paymentMocks(page) {
  let paid = false; let reversed = false; const requests = []; const receipts = new Map();
  const invoice = () => ({ id: 'payment-invoice', period: 'payment-period', clinic: 1, number: 'FAC-PAY', clinic_name: 'Cabinet test',
    issued_at: '2026-10-01T10:00:00Z', total_amount: '1000.00', base_amount: '1000.00', express_surcharge: '0.00', lines: [],
    paid_amount: paid && !reversed ? '400.00' : '0.00', balance: paid && !reversed ? '600.00' : '1000.00',
    payment_status: paid && !reversed ? 'PARTIELLE' : 'IMPAYEE', due_date: '2026-11-30', terms_days: 60, days_overdue: 0 });
  const payment = () => ({ id: 'payment-1', clinic: 1, method: 'CHEQUE', amount: '400.00', received_on: '2026-11-25',
    reference: 'CH-UI', bank: 'Banque test', due_on: null, allocations: [{ invoice: 'payment-invoice', amount: '400.00' }],
    reversal: reversed ? { reason: 'IMPAYE' } : null });
  function record(req) {
    const key = req.headers()['idempotency-key']; requests.push({ key, body: req.postDataJSON() });
    if (!receipts.has(key)) { receipts.set(key, true); paid = true; }
    return payment();
  }
  await mocks(page, (path, req) => {
    if (path === '/api/partner-clinics/') return [{ id: 1, name: 'Cabinet test', payment_terms_days: 60 }];
    if (path === '/api/billing/invoices/') return { results: [invoice()], next: null };
    if (path === '/api/billing/payments/') return req.method() === 'POST' ? record(req) : { results: paid ? [payment()] : [], next: null };
    if (path === '/api/billing/payments/payment-1/reverse/') { reversed = true; return { id: 1, reason: req.postDataJSON().reason }; }
    if (path === '/api/billing/receivables/') return [{ clinic: 1, terms_days: 60, total_due: invoice().balance, not_due: invoice().balance, buckets: { '0_30': '0', '31_60': '0', '61_90': '0', '90_plus': '0' }, overpaid_amount: '0', oldest_overdue_days: 0 }];
  });
  return { requests, receipts, record };
}
async function openPaymentDialog(page) {
  await page.goto('/static/');
  await page.locator('button.sidebar-link[aria-label="Facturation"]').click();
  await page.getByRole('button', { name: 'Enregistrer un encaissement', exact: true }).click();
  const dialog = page.getByRole('dialog', { name: 'Enregistrer un encaissement', exact: true });
  await dialog.getByLabel('Cabinet payeur').selectOption('1');
  await dialog.getByLabel('Montant encaissé (MAD)', { exact: true }).fill('400');
  await dialog.getByLabel('Référence du paiement', { exact: true }).fill('CH-UI');
  await dialog.getByLabel('Banque', { exact: true }).fill('Banque test');
  return dialog;
}

test('finance records a partial cheque then an immutable unpaid reversal at 390px', async ({ page }, testInfo) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await session(page); const fixture = await paymentMocks(page);
  await page.goto('/static/');
  await page.getByRole('button', { name: 'Ouvrir la navigation', exact: true }).click();
  await page.locator('button.sidebar-link[aria-label="Facturation"]').click();
  await page.getByRole('button', { name: 'Enregistrer un encaissement', exact: true }).click();
  const dialog = page.getByRole('dialog', { name: 'Enregistrer un encaissement', exact: true });
  await dialog.getByLabel('Cabinet payeur').selectOption('1');
  await dialog.getByLabel('Montant encaissé (MAD)', { exact: true }).fill('400');
  await dialog.getByLabel('Référence du paiement', { exact: true }).fill('CH-UI');
  await dialog.getByLabel('Banque', { exact: true }).fill('Banque test');
  await expect(dialog.getByLabel('Affectation à FAC-PAY (MAD)')).toHaveValue('400.00');
  await expect(dialog).toContainText('60 jours');
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy();
  await page.screenshot({ path: testInfo.outputPath('payment-dialog-390.png'), fullPage: true });
  await dialog.getByRole('button', { name: 'Enregistrer le paiement', exact: true }).focus(); await page.keyboard.press('Enter');
  await expect(dialog).toHaveCount(0);
  await expect(page.getByText('Partiellement payée', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Marquer comme impayé / Annuler la saisie', exact: true }).click();
  const reverse = page.getByRole('dialog', { name: 'Annuler ou signaler un impayé', exact: true });
  await expect(reverse).toContainText('conserve la preuve');
  await reverse.getByLabel('Motif de l’annulation').selectOption('IMPAYE');
  await reverse.getByRole('button', { name: 'Confirmer l’annulation du paiement', exact: true }).click();
  await expect(reverse).toHaveCount(0);
  await expect(page.getByText('Impayée', { exact: true })).toBeVisible();
  await expect(page.getByText('Signalé impayé · preuve conservée', { exact: true })).toBeVisible();
  expect(fixture.requests).toHaveLength(1); expect(fixture.receipts.size).toBe(1);
  expect(fixture.requests[0].body.allocations).toEqual([{ invoice: 'payment-invoice', amount: '400.00' }]);
  expect(fixture.requests[0].key).toMatch(/^[0-9a-f-]{36}$/);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy();
});

test('payment transport retry retains one dialog key and does not duplicate a committed record', async ({ page }) => {
  await session(page); const fixture = await paymentMocks(page); let first = true;
  await page.route('**/api/billing/payments/', async route => {
    if (route.request().method() === 'POST' && first) { first = false; fixture.record(route.request()); await route.abort('failed'); }
    else await route.fallback();
  });
  const dialog = await openPaymentDialog(page);
  await dialog.getByRole('button', { name: 'Enregistrer le paiement', exact: true }).click();
  await expect(page.getByRole('alert')).toContainText('Connexion');
  await dialog.getByRole('button', { name: 'Enregistrer le paiement', exact: true }).click();
  await expect(dialog).toHaveCount(0);
  expect(fixture.requests).toHaveLength(2); expect(fixture.requests[0].key).toBe(fixture.requests[1].key); expect(fixture.receipts.size).toBe(1);
});

test('successful payment plus refresh failure offers only a read retry', async ({ page }) => {
  await session(page); const fixture = await paymentMocks(page); let failRefresh = true;
  await page.route('**/api/billing/invoices/**', async route => {
    if (fixture.requests.length && failRefresh && route.request().method() === 'GET') { failRefresh = false; await route.abort('failed'); }
    else await route.fallback();
  });
  const dialog = await openPaymentDialog(page);
  await dialog.getByRole('button', { name: 'Enregistrer le paiement', exact: true }).click();
  await expect(dialog.getByRole('button', { name: 'Actualiser les soldes et fermer', exact: true })).toBeVisible();
  await expect(dialog.getByRole('button', { name: 'Enregistrer le paiement', exact: true })).toHaveCount(0);
  await dialog.getByRole('button', { name: 'Actualiser les soldes et fermer', exact: true }).click();
  await expect(dialog).toHaveCount(0); expect(fixture.requests).toHaveLength(1);
});


test('dentist reads only the selected owned invoice balance beside the existing PDF', async ({ page }) => {
  await session(page, 'Cabinet Dentaire'); const reads = [];
  await mocks(page, path => {
    if (path === '/platform/dentist/orders/') return [caseOrder({ patient_ref: 'DENT-PAY', laboratory_id: 'labo1', laboratory_name: 'Laboratoire test', status: 'LIVRE', invoiced_at: '2026-11-01T12:00:00Z' })];
    if (path.endsWith('/invoice-balance/')) { reads.push(path); return { balance: '600.00', payment_status: 'PARTIELLE', due_date: '2027-01-01', terms_days: 60, days_overdue: 0 }; }
  });
  await page.goto('/static/'); await page.getByRole('button', { name: /Mes commandes/ }).click();
  const dialog = await openDossier(page);
  await expect(dialog.getByRole('button', { name: 'Facture PDF', exact: true })).toBeVisible();
  await dialog.getByRole('button', { name: 'Consulter le solde', exact: true }).click();
  await expect(dialog.getByText('Partiellement payée', { exact: true })).toBeVisible();
  await expect(dialog).toContainText('600,00 MAD');
  expect(reads).toEqual([`/platform/dentist/orders/labo1/${id}/invoice-balance/`]);
});

const dashboardFixture = (operations = true) => ({
  as_of: '2026-11-25T12:00:00Z', timezone: 'Africa/Casablanca', currency: 'MAD',
  finance: { month: '2026-11-01', billed_this_month: '1000.00', last_closed_month: '2026-10-01', invoiced_last_closed_month: '2500.00', total_receivables: '600.00', over_60_days: '100.00', overpaid_amount: '20.00', open_disputes: 2, analytics: { last_refreshed_at: null, stale: true, refresh_failed: false } },
  ...(operations ? { operations: { active_cases: 3, stages: [{ key: 'COMMANDE', label: 'Commande', count: 2 }, { key: 'CONCEPTION', label: 'Planification et conception', count: 1 }], late: [{ id, patient_ref: 'PAT-DASH', stage_label: 'Commande', deadline_at: '2026-11-24T17:00:00Z', projected_end: '2026-11-25T12:00:00Z' }], at_risk: [], deliveries_due_today: 1, deliveries_due_this_week: 2, paused_or_blocked_cases: 1, rework_30_days: { reworks: 1, delivered: 2, rate_percent: 50 } } } : {}),
});
for (const width of [1440, 390]) {
  test(`manager dashboard reuses server figures and opens the real case workspace at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 844 }); await session(page);
    const errors = await mocks(page, path => {
      if (path === '/api/dashboard/summary/') return dashboardFixture();
      if (path === `/api/prescriptions/${id}/`) return caseOrder({ patient_ref: 'PAT-DASH' });
    });
    await page.goto('/static/');
    await expect(page.getByRole('heading', { name: 'À faire', exact: true })).toBeVisible();
    if (width === 390) await page.getByRole('button', { name: 'Ouvrir la navigation', exact: true }).click();
    await page.getByRole('button', { name: 'Tableau de bord', exact: true }).click();
    const dashboard = page.getByRole('region', { name: 'Indicateurs du laboratoire' });
    await expect(dashboard.getByText('Dossiers actifs', { exact: true })).toBeVisible();
    await expect(dashboard.getByText('Dossiers actifs', { exact: true }).locator('..')).toContainText('3');
    await expect(dashboard.getByText('Créances à encaisser', { exact: true }).locator('..')).toContainText('600,00');
    await expect(dashboard.getByText(/Le catalogue de facturation est ancien/)).toBeVisible();
    const open = dashboard.getByRole('button', { name: 'Ouvrir le dossier PAT-DASH', exact: true });
    await open.focus(); await page.keyboard.press('Enter');
    await expect(page.getByRole('dialog', { name: /Dossier clinique/ })).toBeVisible();
    await page.keyboard.press('Escape'); await expect(open).toBeFocused();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy();
    expect(errors).toEqual([]);
  });
}
test('accounting dashboard shows only its finance subset and can refresh it', async ({ page }) => {
  await session(page, 'Laboratoire', 'COMPTABILITE');
  let reads = 0;
  await mocks(page, path => { if (path === '/api/dashboard/summary/') { reads += 1; return dashboardFixture(false); } });
  await page.goto('/static/'); await page.getByRole('button', { name: 'Tableau de bord', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Finances', exact: true })).toBeVisible();
  await expect(page.getByText('Dossiers actifs', { exact: true })).toHaveCount(0);
  const beforeRefresh = reads;
  await page.getByRole('button', { name: 'Actualiser le tableau de bord', exact: true }).click();
  await expect(page.getByText('Tableau de bord actualisé.', { exact: true })).toBeVisible(); expect(reads).toBe(beforeRefresh + 1);
});
test('technical workstation has no management dashboard navigation', async ({ page }) => {
  await session(page, 'Laboratoire', 'CAO'); await mocks(page); await page.goto('/static/');
  await expect(page.getByRole('button', { name: 'Tableau de bord', exact: true })).toHaveCount(0);
});


const identityFixture = () => ({ id: 1, legal_name: 'Laboratoire Test Atlas', address: 'Adresse fictive',
  city: 'Ville Test', phone: '0000000000', email: 'demo@example.invalid', ice: '000000000000000',
  identifiant_fiscal: '', registre_commerce: '', patente: '', updated_at: null, updated_by: '' });

for (const width of [1440, 390]) {
  test('manager identity form validates, saves and stays usable by keyboard at ' + width + 'px', async ({ page }) => {
    await page.setViewportSize({ width, height: 844 }); await session(page);
    let profile = identityFixture(); const writes = []; let reads = 0;
    const errors = await mocks(page, (path, req) => {
      if (path === '/api/laboratory-profile/') {
        if (req.method() === 'PUT') { const data = req.postDataJSON(); writes.push(data); profile = { ...profile, ...data, updated_at: '2026-11-25T12:00:00Z', updated_by: 'platform:1:Compte de test' }; }
        else reads += 1;
        return profile;
      }
    });
    await page.goto('/static/');
    if (width === 390) await page.getByRole('button', { name: 'Ouvrir la navigation', exact: true }).click();
    await page.getByRole('button', { name: 'Configuration', exact: true }).click();
    const summary = page.locator('summary').filter({ hasText: /^Identité du laboratoire$/ });
    await expect(summary).toBeVisible(); expect(reads).toBe(0);
    await summary.focus(); await page.keyboard.press('Enter');
    const form = page.getByRole('form', { name: 'Identité du laboratoire' });
    await expect(form.getByLabel('Dénomination légale', { exact: true })).toHaveValue('Laboratoire Test Atlas');
    await form.getByLabel('Dénomination légale', { exact: true }).fill('Laboratoire Fictif V1');
    await form.getByLabel('ICE (15 chiffres)', { exact: true }).fill('12');
    await form.getByRole('button', { name: 'Enregistrer l’identité', exact: true }).click();
    const toast = page.getByRole('button', { name: 'Fermer la notification', exact: true }).locator('..');
    await expect(toast.getByRole('alert')).toContainText('15 chiffres');
    expect((await toast.boundingBox()).y).toBeLessThan(80);
    expect(writes).toHaveLength(0); await expect(form.getByLabel('ICE (15 chiffres)', { exact: true })).toBeFocused();
    await form.getByLabel('ICE (15 chiffres)', { exact: true }).fill('000000000000000');
    await form.getByRole('button', { name: 'Enregistrer l’identité', exact: true }).click();
    await expect(toast.getByRole('status')).toHaveText('Identité du laboratoire enregistrée.');
    expect(writes).toHaveLength(1); expect(writes[0].ice).toBe('000000000000000');
    await summary.click(); await summary.focus(); await page.keyboard.press('Enter');
    await expect(form.getByLabel('Dénomination légale', { exact: true })).toHaveValue('Laboratoire Fictif V1');
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBe(width);
    expect(errors).toEqual([]);
  });
}

test('identity server errors remain French and preserve the draft', async ({ page }) => {
  await session(page); await mocks(page);
  await page.route('**/api/laboratory-profile/', async route => {
    const method = route.request().method();
    const headers = { 'Access-Control-Allow-Origin': '*', 'Access-Control-Allow-Headers': '*' };
    if (method === 'OPTIONS') return route.fulfill({ status: 204, headers });
    return route.fulfill({ status: method === 'PUT' ? 400 : 200, headers,
      json: method === 'PUT' ? { ice: ['ICE must contain exactly 15 digits.'] } : identityFixture() });
  });
  await page.goto('/static/'); await page.getByRole('button', { name: 'Configuration', exact: true }).click();
  await page.locator('summary').filter({ hasText: /^Identité du laboratoire$/ }).click();
  const form = page.getByRole('form', { name: 'Identité du laboratoire' });
  await form.getByLabel('Dénomination légale', { exact: true }).fill('Brouillon conservé');
  await form.getByRole('button', { name: 'Enregistrer l’identité', exact: true }).click();
  const toast = page.getByRole('button', { name: 'Fermer la notification', exact: true }).locator('..');
  await expect(toast.getByRole('alert')).toContainText('L’ICE doit contenir exactement 15 chiffres');
  await expect(form.getByLabel('Dénomination légale', { exact: true })).toHaveValue('Brouillon conservé');
});

test('accounting can read identity but has no save action', async ({ page }) => {
  await session(page, 'Laboratoire', 'COMPTABILITE'); const methods = [];
  await mocks(page, (path, req) => { if (path === '/api/laboratory-profile/') { methods.push(req.method()); return identityFixture(); } });
  await page.goto('/static/'); await page.getByRole('button', { name: 'Configuration', exact: true }).click();
  await page.locator('summary').filter({ hasText: /^Identité du laboratoire$/ }).click();
  const form = page.getByRole('form', { name: 'Identité du laboratoire' });
  await expect(form.getByLabel('Dénomination légale', { exact: true })).toHaveValue('Laboratoire Test Atlas');
  await expect(form.getByLabel('Dénomination légale', { exact: true })).toHaveAttribute('readonly', '');
  await expect(form.getByRole('button', { name: /Enregistrer/ })).toHaveCount(0);
  expect(methods).toEqual(['GET']);
});

test('technical workstation does not render or fetch laboratory identity', async ({ page }) => {
  await session(page, 'Laboratoire', 'FAO'); let reads = 0;
  await mocks(page, path => { if (path === '/api/laboratory-profile/') { reads += 1; return identityFixture(); } });
  await page.goto('/static/'); await page.getByRole('button', { name: 'Configuration', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Configuration', exact: true }).last()).toBeVisible();
  await expect(page.locator('summary').filter({ hasText: /^Identité du laboratoire$/ })).toHaveCount(0);
  expect(reads).toBe(0);
});


test('French dossier file chooser works with Enter and resets after upload at 390px', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await session(page); const uploads = []; const order = caseOrder({ status: 'CONTROLE_MODELE' });
  await mocks(page, (path, req) => {
    if (path === '/api/prescriptions/') return { results: [order], next: null };
    if (path.endsWith('/attachments/')) {
      if (req.method() === 'POST') { uploads.push(req.postDataBuffer()); return { id: 1, kind: 'STL', original_name: 'preuve-v1.stl' }; }
      return [];
    }
  });
  await page.goto('/static/');
  await page.getByRole('button', { name: 'Ouvrir la navigation', exact: true }).click();
  await page.getByRole('button', { name: 'Commandes', exact: true }).first().click();
  const dossier = await openDossier(page);
  await dossier.getByLabel('Type', { exact: true }).selectOption('STL');
  await expect(dossier.getByText('Aucun fichier s\u00e9lectionn\u00e9', { exact: true })).toBeVisible();
  const chooser = dossier.getByRole('button', { name: 'Choisir un fichier', exact: true });
  await chooser.focus();
  await expect(chooser).toBeFocused();
  const selected = page.waitForEvent('filechooser'); await chooser.press('Enter');
  await (await selected).setFiles({ name: 'preuve-v1.stl', mimeType: 'model/stl', buffer: Buffer.from('solid v1\nendsolid v1\n') });
  await expect(dossier.getByText('preuve-v1.stl', { exact: true })).toBeVisible();
  await dossier.getByRole('button', { name: 'T\u00e9l\u00e9verser', exact: true }).click();
  await expect.poll(() => uploads.length).toBe(1);
  expect(uploads[0].toString()).toContain('preuve-v1.stl');
  await expect(dossier.getByText('Aucun fichier s\u00e9lectionn\u00e9', { exact: true })).toBeVisible();
  await expect(dossier.getByRole('button', { name: 'T\u00e9l\u00e9verser', exact: true })).toBeDisabled();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
});

test('French dentist STL chooser keeps the required native file input and keyboard activation', async ({ page }) => {
  await session(page, 'Cabinet Dentaire'); await mocks(page);
  await page.goto('/static/'); await page.getByLabel('Empreinte', { exact: true }).selectOption('NUMERIQUE');
  const input = page.getByLabel('Fichier STL r\u00e9el \u00b7 25 Mo maximum', { exact: true });
  await expect(input).toHaveAttribute('required', '');
  const chooser = page.getByRole('button', { name: 'Choisir un fichier', exact: true });
  await chooser.focus(); const selected = page.waitForEvent('filechooser'); await chooser.press('Space');
  await (await selected).setFiles({ name: 'scan-v1.stl', mimeType: 'model/stl', buffer: Buffer.from('solid v1\nendsolid v1\n') });
  await expect(page.getByText('scan-v1.stl', { exact: true })).toBeVisible();
  expect(await input.evaluate(element => [element.files.length, element.files[0].name])).toEqual([1, 'scan-v1.stl']);
});

test('finance preserves cents in large statement totals and the remaining credit ceiling', async ({ page }) => {
  await session(page); const period = { id: 'exact-period', month: '2026-10-01', clinic: 1, closed_at: null };
  await mocks(page, path => {
    if (path === '/api/billing/periods/') return [period];
    if (path === '/api/billing/statement-lines/') return [{ id: 'exact-line', period: period.id, prescription: id,
      base_amount: '90071992547409.91', express_surcharge: '0.10', contested: false, excluded: false }];
    if (path === '/api/billing/invoices/') return [{ id: 'exact-invoice', number: 'FAC-EXACT', clinic: 1,
      clinic_name: 'Cabinet test', total_amount: '90071992547409.91',
      lines: [{ case_id: id, patient_ref: 'PAT-EXACT', total_amount: '90071992547409.91' }] }];
    if (path === '/api/billing/credit-notes/') return [{ id: 'exact-credit', invoice: 'exact-invoice',
      prescription: id, amount: '0.10', reason: 'Ajustement fictif' }];
  });
  await page.goto('/static/'); await page.locator('button.sidebar-link[aria-label="Facturation"]').click();
  await page.getByLabel('Cabinet et mois de livraison').selectOption(period.id);
  await expect(page.getByText(/1 dossier\(s\) inclus/)).toContainText('90\u202f071\u202f992\u202f547\u202f410,01');
  await page.getByText('\u00c9mettre un avoir sur une ligne', { exact: true }).click();
  await page.getByLabel('Dossier factur\u00e9').selectOption(id);
  await expect(page.getByText(/Montant restant ajustable/)).toContainText('90\u202f071\u202f992\u202f547\u202f409,81');
  await expect(page.getByLabel('Montant de l\u2019avoir (MAD)')).toHaveAttribute('max', '90071992547409.81');
});


// ---------------- Step 8.8: presentation readiness ----------------
const labMonth = () => { const p = new Intl.DateTimeFormat('en-CA', { timeZone: 'Africa/Casablanca', year: 'numeric', month: '2-digit' }).formatToParts(new Date()); return `${p.find(x => x.type === 'year').value}-${p.find(x => x.type === 'month').value}`; };

test('8.8 Facturation lists delivered orders with work, amount, status and total, and opens the case', async ({ page }) => {
  await session(page, 'Laboratoire', 'COMPTABILITE'); const month = labMonth();
  const line = (lineId, ref, base, express, extra = {}) => ({ id: lineId, period: 'p1', prescription: id, base_amount: base, express_surcharge: express, contested: false, excluded: false, dispute_reason: '',
    snapshot: { case_id: id, patient_ref: ref, delivery_service: express === '0.00' ? 'STANDARD' : 'EXPRESS', delivered_at: `${month}-20T10:00:00Z`, items: [{ tooth_number: 11, function: 'Couronne', form: 'Anatomique', material: 'E-Max', shade: 'A1' }] }, ...extra });
  await mocks(page, path => {
    if (path === '/api/billing/periods/') return [{ id: 'p1', clinic: 1, month: `${month}-01`, closed_at: null }];
    if (path === '/api/billing/statement-lines/') return [line('l1', 'REF-LIVRE', '1500.00', '0.00'), line('l2', 'REF-EXCLU', '300.00', '0.00', { excluded: true })];
    if (path === '/api/partner-clinics/') return [{ id: 1, name: 'Cabinet Atlas' }];
    if (path === `/api/prescriptions/${id}/`) return caseOrder({ status: 'CLOTURE' });
  });
  await page.goto('/static/');
  const table = page.getByRole('table', { name: 'Commandes livrées du mois' });
  await expect(table).toContainText('REF-LIVRE'); await expect(table).toContainText('Cabinet Atlas');
  await expect(table).toContainText('Dent 11 · Couronne · E-Max · A1'); await expect(table).toContainText('Dans le relevé');
  await expect(table).toContainText('Exclue');
  await expect(table.locator('tfoot')).toContainText('1 500,00');
  await expect(page.getByText('Aucune facture pour le moment', { exact: false })).toBeVisible();
  // The current month's statement is preselected and lines stay compact until "Ajuster".
  await expect(page.getByRole('button', { name: 'Ajuster', exact: true }).first()).toBeVisible();
  await expect(page.getByLabel('Contestée')).toHaveCount(0);
  await page.getByRole('button', { name: 'Ajuster', exact: true }).first().click();
  await expect(page.getByLabel('Contestée')).toBeVisible();
  await table.getByRole('button', { name: 'REF-LIVRE' }).click();
  await expect(page.getByRole('dialog', { name: /Dossier clinique/ })).toBeVisible();
});

test('8.8 passing inspection hides the proof photo; a failed criterion shows it again', async ({ page }) => {
  await session(page); const order = caseOrder({ status: 'CONTROLE_MODELE' });
  await mocks(page, path => path === '/api/prescriptions/' ? { results: [order], next: null } : undefined);
  await page.goto('/static/'); await page.getByRole('button', { name: 'Commandes', exact: true }).first().click();
  const dialog = await openClinical(page);
  const photo = dialog.getByLabel('Photo de preuve (obligatoire en cas d’échec ou d’écart)');
  await dialog.getByRole('button', { name: 'Tout conforme', exact: true }).click();
  await expect(photo).toHaveCount(0);
  await expect(dialog.getByRole('region', { name: 'Votre action' }).getByText('Note libre (facultative)')).toBeVisible();
  await dialog.getByLabel('Scan conforme', { exact: true }).uncheck();
  await expect(photo).toBeVisible();
  await dialog.getByLabel('Scan conforme', { exact: true }).check(); await dialog.getByLabel('Écart nécessitant une photo').check();
  await expect(photo).toBeVisible();
});

test('8.8 CAO uploads the design inside the action and submits the auto-selected version', async ({ page }) => {
  await session(page); const order = caseOrder({ status: 'SALLE_CAO', design_validation_requested: true }); const commands = []; let uploaded = false;
  await mocks(page, (path, req) => {
    if (path === '/api/prescriptions/') return { results: [order], next: null };
    if (path.endsWith('/attachments/') && req.method() === 'POST') { uploaded = true; return { id: 'design-9', kind: 'DESIGN', name: 'design.stl' }; }
    if (path.endsWith('/attachments/')) return uploaded ? [{ id: 'design-9', kind: 'DESIGN', original_name: 'design.stl', created_at: '2026-11-26T10:00:00Z' }] : [];
    if (path.endsWith('/command/')) { commands.push(req.postDataJSON()); return { case: order, result: {} }; }
  });
  await page.goto('/static/'); await page.getByRole('button', { name: 'Commandes', exact: true }).first().click();
  const dialog = await openClinical(page);
  const submit = dialog.getByRole('button', { name: 'Soumettre au dentiste et suspendre le délai' });
  await expect(submit).toBeDisabled();
  await dialog.getByLabel('Fichier de design · 25 Mo maximum').setInputFiles({ name: 'design.stl', mimeType: 'model/stl', buffer: Buffer.from('solid d\nendsolid d') });
  await dialog.getByRole('button', { name: 'Téléverser le design', exact: true }).click();
  await expect(dialog.getByLabel('Version de design téléversée')).toHaveValue('design-9');
  await submit.click();
  await expect.poll(() => commands.length).toBe(1);
  expect(commands[0]).toEqual({ action: 'design-request', data: { attachment: 'design-9', notes: '' } });
});

test('8.8 lot is created from the case with this case preselected', async ({ page }) => {
  await session(page); let posted = null;
  const order = caseOrder({ status: 'PREPARATION_CNC', current_step: { kind: 'WORK', next_requires_lot: true } });
  await mocks(page, (path, req) => {
    if (path === '/api/prescriptions/') return { results: [order], next: null };
    if (path === '/api/planning/tasks/') return { results: [{ ...planningTask(), workflow_step: 'PREPARATION_CNC', source_status: 'PREPARATION_CNC', status: 'READY', planned_start: '2020-01-01T08:00:00Z', planned_end: '2020-01-01T09:00:00Z' }], next: null };
    if (path === '/api/production-lots/' && req.method() === 'POST') { posted = req.postDataJSON(); return { id: 'lot-1', code: posted.code, prescriptions: [id] }; }
    if (path === '/api/production-lots/') return posted ? [{ id: 'lot-1', code: posted.code, prescriptions: [id] }] : [];
    if (path === '/api/machines/') return [{ id: 3, name: 'Virtual mill' }];
  });
  await page.goto('/static/'); await page.getByRole('button', { name: 'Commandes', exact: true }).first().click();
  const dialog = await openClinical(page);
  const panel = dialog.getByRole('region', { name: 'Lot de production' });
  await expect(panel.getByLabel('Code du lot')).toHaveValue('LOT-PAT-TEST');
  await panel.getByLabel('Machine du lot').selectOption('3');
  await panel.getByRole('button', { name: 'Créer et lier le lot' }).click();
  await expect.poll(() => posted).toEqual({ code: 'LOT-PAT-TEST', machine: 3, inventory_item: null, prescriptions: [id] });
  await expect(dialog.getByText('Lot lié : LOT-PAT-TEST')).toBeVisible();
  await expect(dialog.getByText(/Pourquoi cette affectation \?/)).toBeVisible();
});

test('8.8 courier reads the signed QR from an imported label image', async ({ page }) => {
  await session(page, 'Coursier'); const commands = [];
  const order = caseOrder({ status: 'ATTENTE_RAMASSAGE' });
  await mocks(page, (path, req) => {
    if (path === '/api/prescriptions/') return { count: 1, results: [order], next: null };
    if (path.endsWith('/command/')) { commands.push(req.postDataJSON()); return { case: { ...order, status: 'EN_ROUTE_LABO' }, result: {} }; }
  });
  await page.goto('/static/'); await page.getByRole('button', { name: 'Confirmer la collecte', exact: true }).click();
  const dialog = page.getByRole('dialog');
  await dialog.getByLabel('Importer l’image du QR (photo ou étiquette)').setInputFiles('tests/fixtures/qr-fixture.png');
  await expect(dialog.getByLabel('Contenu du QR signé du dossier')).toHaveValue('.FIXTURE-SIGNED-QR-CONTENT');
  expect(commands).toEqual([]);
  await dialog.getByRole('button', { name: 'Confirmer la collecte', exact: true }).click();
  await expect.poll(() => commands).toEqual([{ action: 'pickup', data: { qr_token: '.FIXTURE-SIGNED-QR-CONTENT' } }]);
});

test('8.8 dentist sees a plain status without lab risk or workshop jargon', async ({ page }) => {
  await session(page, 'Cabinet Dentaire');
  const order = caseOrder({ status: 'PREPARATION_CNC', delivery_date: '2026-11-30', stages: [{ key: 'FABRICATION', label: 'Fabrication', state: 'current' }], current_step: { kind: 'WORK', instruction: 'Préparer la FAO, le placement dans le brut.' } });
  await mocks(page, path => path === '/platform/dentist/orders/' ? [order] : undefined);
  await page.goto('/static/'); await page.getByRole('button', { name: 'Ouvrir le dossier PAT-TEST' }).click();
  const dialog = page.getByRole('dialog', { name: /Dossier clinique/ });
  await expect(dialog).toContainText('Votre dossier est à l’étape « Fabrication » au laboratoire. Livraison prévue : 30 novembre 2026.');
  await expect(dialog).not.toContainText('Risque'); await expect(dialog).not.toContainText('placement dans le brut');
});

test('8.8 technical diagnostics moved under Configuration and show only pending items by default', async ({ page }) => {
  await session(page);
  await mocks(page, path => path === '/api/operations/outbox/' ? [{ id: 'e1', event_type: 'CATALOG', processed_at: '2026-11-26T10:00:00Z', attempts: 1 }, { id: 'e2', event_type: 'CATALOG', processed_at: null, failed_at: '2026-11-26T10:00:00Z', attempts: 3, last_error: 'boom' }] : undefined);
  await page.goto('/static/');
  await expect(page.getByRole('navigation', { name: 'Navigation du laboratoire' }).getByRole('button', { name: 'Opérations' })).toHaveCount(0);
  await page.getByRole('button', { name: 'Configuration', exact: true }).click();
  await page.getByText('Diagnostic technique', { exact: true }).click();
  await expect(page.getByText(/3 essai\(s\)/)).toBeVisible(); await expect(page.getByText(/1 essai\(s\)/)).toHaveCount(0);
  await page.getByLabel(/Afficher tout l’historique/).check();
  await expect(page.getByText(/1 essai\(s\)/)).toBeVisible();
});

test('8.8 an inventory stock alert opens Stocks et lots on that consumable, not an empty page', async ({ page }) => {
  await session(page);
  await mocks(page, path => {
    if (path === '/api/alerts/') return [{ id: 'stock-7', type: 'stock', reference: 'INV-7', message: 'Le stock de matière « E-Max CAD bloc A2 » est au seuil d’alerte ou en dessous : 4 UNITES restant(s), seuil 5 UNITES.', section: 'inventory', resource_id: 7, name: 'E-Max CAD bloc A2', overdue: true, due_date: null }];
    if (path === '/api/inventory/') return [{ id: 6, material_name: 'Zircone', quantity: '6.000000', unit: 'DISQUE', alert_threshold: '3.000000', unit_cost: '850', is_low_stock: false }, { id: 7, material_name: 'E-Max CAD bloc A2', quantity: '4.000000', unit: 'UNITES', alert_threshold: '5.000000', unit_cost: '210', is_low_stock: true }];
  });
  await page.goto('/static/');
  const alert = page.getByRole('region', { name: 'Toutes les alertes' }).getByRole('button', { name: /E-Max CAD bloc A2/ });
  await expect(alert).not.toContainText('Échéance dépassée');
  await expect(alert).toContainText('Stocks et lots / Stock / E-Max CAD bloc A2');
  await alert.click();
  await expect(page.getByRole('heading', { name: 'Stocks et lots de production' })).toBeVisible();
  await expect(page.locator('#inventory-item-7')).toHaveClass(/ring-2/);
  await expect(page.getByLabel('Consommable', { exact: true })).toHaveValue('7');
});
