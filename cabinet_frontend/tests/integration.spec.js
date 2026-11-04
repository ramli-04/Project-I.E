import { test, expect } from '@playwright/test';

const id = 'd3f16d2a-4910-47cb-920d-8c1011539c01';
const caseOrder = (overrides = {}) => ({ id, patient_ref: 'PAT-TEST', dentist_name: 'Dentiste test', laboratory_id: 'labo1', laboratory_name: 'Laboratoire test', partner_clinic: 1, status: 'ANALYSE_DEMANDE', status_label: 'Analyse de la demande', accepted: true, total_price: '1200.00', production_attempt: 1, intake_version: 2, impression_type: 'PHYSIQUE', delivery_service: 'STANDARD', updated_at: '2026-11-04T12:00:00Z', clinical_items: [{ tooth_number: 11, function: 'Couronne', form: 'Anatomique', material: 'Zircone', shade: 'A1' }], workflow_steps: [{ key: 'ANALYSE_DEMANDE', label: 'Analyse' }, { key: 'ATTENTE_RAMASSAGE', label: 'Ramassage' }], next_status: 'ATTENTE_RAMASSAGE', ...overrides });
async function session(page, role = 'Laboratoire', workstation_role = 'MANAGER') {
  await page.addInitScript(({ role, workstation_role }) => {
    sessionStorage.setItem('demo_user', JSON.stringify({ name: 'Compte de test', role, workstation_role }));
    sessionStorage.setItem('demo_token', 'fixture-token'); sessionStorage.setItem('tenant_id', 'labo1');
  }, { role, workstation_role });
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
  await page.getByLabel('Fonction', { exact: true }).fill('Couronne'); await page.getByLabel('Forme', { exact: true }).fill('Anatomique');
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
    if (req.method() === 'PATCH') { patch = req.postDataJSON(); return caseOrder(); }
  });
  await page.goto('/static/'); await page.getByRole('button', { name: 'Commandes', exact: true }).first().click();
  await expect(page.getByText('PAT-PAGE2', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Ouvrir le diagramme PAT-TEST' }).click();
  await page.getByLabel('Analyse de la demande validée').check();
  await page.getByRole('button', { name: 'Valider → Ramassage' }).click();
  expect(patch.status).toBe('ATTENTE_RAMASSAGE'); expect(patch.analysis_validated).toBe(true);
  expect(patch).not.toHaveProperty('is_paused'); expect(patch).not.toHaveProperty('quality_validated'); expect(errors).toEqual([]);
});

test('courier submits QR custody and actual entered PIN through commands', async ({ page }) => {
  await session(page, 'Coursier'); let order = caseOrder({ status: 'PRET_EXPEDITION' }); const commands = [];
  await mocks(page, (path, req) => {
    if (path === '/api/prescriptions/') return { count: 1, results: [order], next: null };
    if (path.endsWith('/command/')) { const payload = req.postDataJSON(); commands.push(payload); order = { ...order, status: payload.action === 'checkout' ? 'EN_ROUTE_CABINET' : 'LIVRE' }; return { case: order, result: {} }; }
  });
  await page.goto('/static/'); await page.getByLabel('Contenu du QR signé').fill('signed-token');
  await page.getByRole('button', { name: 'Sortir du laboratoire' }).click();
  await page.getByLabel('PIN réel de livraison').fill('0789'); await page.getByRole('button', { name: 'Confirmer la livraison' }).click();
  await expect.poll(() => commands.length).toBe(2);
  expect(commands).toEqual([{ action: 'checkout', data: { qr_token: 'signed-token' } }, { action: 'confirm-delivery', data: { pin: '0789' } }]);
});

test('clinical inspection records explicit checks through the evidence command', async ({ page }) => {
  await session(page); const commands = []; const order = caseOrder({ status: 'CONTROLE_DOSSIER' });
  await mocks(page, (path, req) => {
    if (path === '/api/prescriptions/') return { results: [order], next: null };
    if (path.endsWith('/command/')) { commands.push(req.postDataJSON()); return { case: order, result: {} }; }
  });
  await page.goto('/static/'); await page.getByRole('button', { name: 'Commandes', exact: true }).first().click(); await page.getByRole('button', { name: 'Ouvrir le diagramme PAT-TEST' }).click();
  await page.getByRole('button', { name: 'Ouvrir les documents et actions' }).click();
  for (const name of ['Absence de déformation','Absence de bulles','Limites lisibles','Occlusion','Hygiène']) await page.getByLabel(name + ' conforme', { exact: true }).check();
  await page.getByRole('button', { name: 'Enregistrer le contrôle' }).click();
  await expect.poll(() => commands.length).toBe(1); expect(commands[0].action).toBe('inspection'); expect(commands[0].data.stage).toBe('PHYSICAL'); expect(Object.values(commands[0].data.checks)).toEqual([true,true,true,true,true,false]);
});

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
  await page.goto('/static/'); await page.getByRole('button', { name: 'Mes commandes (1)' }).click(); await page.getByRole('button', { name: 'Ouvrir les documents et actions' }).click();
  await page.getByRole('button', { name: 'Approuver', exact: true }).click();
  await expect(page.getByText('Version 1 · APPROVED')).toBeVisible();
  expect(commands[0]).toEqual({ action: 'design-decision', data: { review: 'review-1', decision: 'APPROVED', notes: '' } });
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
  await page.goto('/static/'); await page.getByRole('button', { name: 'Commandes', exact: true }).first().click(); await page.getByRole('button', { name: 'Ouvrir le diagramme PAT-TEST' }).click(); await page.getByRole('button', { name: 'Ouvrir les documents et actions' }).click();
  await page.getByLabel('Supplément urgence (MAD)').fill('300.00'); await page.getByRole('button', { name: 'Confirmer le devis laboratoire' }).click();
  await expect.poll(() => command).toBeTruthy(); expect(command).toEqual({ action: 'quote', data: { surcharge: '300.00', notes: '' } });
  await expect(page.getByRole('button', { name: 'Enregistrer les informations' })).toBeDisabled();
});

test('measured rework references original consumption rather than a stock deduction', async ({ page }) => {
  await session(page, 'Laboratoire', 'QUALITE'); const order = caseOrder({ status: 'CONTROLE_QUALITE', production_method: 'CFAO' }); let command;
  await mocks(page, (path, req) => {
    if (path === '/api/prescriptions/') return { results: [order], next: null };
    if (path === '/api/inventory-transactions/') return { results: [{ id: 'usage-1', transaction_type: 'USAGE', production_attempt: 1, quantity_changed: '-2.000000', material_name_snapshot: 'Zircone', unit_snapshot: 'DISQUE' }], next: null };
    if (path.endsWith('/command/')) { command = req.postDataJSON(); return { case: order, result: {} }; }
  });
  await page.goto('/static/'); await page.getByRole('button', { name: 'Commandes', exact: true }).first().click(); await page.getByRole('button', { name: 'Ouvrir le diagramme PAT-TEST' }).click(); await page.getByRole('button', { name: 'Ouvrir les documents et actions' }).click();
  await page.getByLabel('Étape de reprise').selectOption('FINITION'); await page.getByLabel('Cause', { exact: true }).fill('Contact'); await page.getByLabel('Action corrective').fill('Corriger'); await page.getByLabel('Perte sur Zircone').fill('0.25'); await page.getByRole('button', { name: 'Enregistrer la reprise documentée' }).click();
  await expect.poll(() => command).toBeTruthy(); expect(command.action).toBe('rework'); expect(command.data.losses).toEqual([{ usage_id: 'usage-1', quantity: '0.25' }]);
});

test('clinical dashboard supports tooth selection, filters and mobile navigation', async ({ page }) => {
  await session(page); const order = caseOrder();
  await mocks(page, path => path === '/api/prescriptions/' ? { results: [order], next: null } : undefined);
  await page.goto('/static/');
  await page.getByRole('button', { name: 'Dent 11', exact: true }).click();
  await expect(page.locator('.featured-treatment')).toContainText('PAT-TEST');
  await expect(page.getByRole('button', { name: 'Dent 11', exact: true })).toHaveAttribute('aria-pressed','true');
  await page.getByRole('button', { name: 'Prioritaires', exact: true }).click();
  await expect(page.getByText('Aucun dossier dans cette sélection.')).toBeVisible();
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await page.setViewportSize({ width: 390, height: 844 });
  await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth)).toBe(390);
  await expect.poll(() => page.locator('.odontogram-card').evaluate(e => e.getBoundingClientRect().right)).toBeLessThanOrEqual(390);
  await page.getByRole('button', { name: 'Ouvrir la navigation', exact: true }).click();
  await page.getByRole('button', { name: 'Stocks et lots', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Stocks et lots de production' })).toBeVisible();
});

test('laboratory identity, matching favicon and resource tabs with two-decimal quantities', async ({ page }) => {
  await session(page);
  await mocks(page, path => path === '/api/inventory/' ? [{ id: 1, material_name: 'Zircone', quantity: '12.345678', unit: 'DISQUE', alert_threshold: '2.000000', unit_cost: '350.000000' }] : path === '/api/employee-profiles/' ? [{ id: 1, user: 1, role: 'CAO', contract_type: 'CDI', hire_date: '2026-01-01', is_available: true }] : undefined);
  await page.goto('/static/');
  await expect(page).toHaveTitle('Gestion Labo');
  await expect(page.getByRole('heading', { name: 'Laboratoire de prothèses dentaires', exact: true })).toBeVisible();
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
