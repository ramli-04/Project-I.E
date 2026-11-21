import { randomUUID } from 'node:crypto';
import { execFileSync } from 'node:child_process';
import { test, expect } from '@playwright/test';

// Real HTTP only: no route interception, fixtures replacing responses, or preview adapter.
const backend = process.env.VIRTUAL_LAB_BACKEND || 'http://127.0.0.1:18000';
const frontend = process.env.VIRTUAL_LAB_FRONTEND || 'http://localhost:18080';
const composeProject = process.env.VIRTUAL_LAB_PROJECT || 'cabinet-virtual-lab';
const password = 'Demo-Lab-2026!';
const tenantHost = 'simlab.localhost';
const apiTokens = new Map();
const browserSessions = new Map();

test.beforeAll(async ({ request }) => {
  const response = await request.get(backend + '/platform/environment/');
  expect(response.status()).toBe(200);
  expect((await response.json()).mode).toBe('SIMULATION');
});

test('browser preflight allows the required idempotency header', async ({ request }) => {
  const response = await request.fetch(backend + '/api/prescriptions/', {
    method: 'OPTIONS', headers: {
      Host: tenantHost, Origin: new URL(frontend).origin,
      'Access-Control-Request-Method': 'POST',
      'Access-Control-Request-Headers': 'authorization,content-type,idempotency-key',
    },
  });
  expect(response.status()).toBe(200);
  expect(response.headers()['access-control-allow-headers'].split(',').map(value => value.trim()))
    .toContain('idempotency-key');
});

function observe(page) {
  const problems = [];
  page.on('pageerror', error => problems.push(error.message));
  page.on('response', response => {
    if (/\/(api|platform)\//.test(response.url()) && response.status() >= 400) {
      problems.push(`${response.status()} ${new URL(response.url()).pathname}`);
    }
  });
  page.on('requestfailed', request => {
    if (/\/(api|platform)\//.test(request.url()) && !/ABORTED/.test(request.failure()?.errorText || '')) {
      problems.push(`${request.failure()?.errorText} ${new URL(request.url()).pathname}`);
    }
  });
  return problems;
}

async function login(page, name = 'Demo Manager', portal = 'LAB') {
  const key = `${portal}:${name}`;
  if (browserSessions.has(key)) {
    await page.addInitScript(({ values, origin }) => {
      if (location.origin === origin) {
        for (const [key, value] of Object.entries(values)) sessionStorage.setItem(key, value);
      }
    }, { values: browserSessions.get(key), origin: new URL(frontend).origin });
    await page.goto('/');
    await expect(page.locator('#login-name')).toHaveCount(0);
    await expect(page.getByRole('status').filter({ hasText: 'SIMULATION' })).toBeVisible();
    return;
  }
  await page.goto('/');
  await expect(page.getByRole('status').filter({ hasText: 'SIMULATION' })).toBeVisible();
  await page.locator('#login-portal').selectOption(portal);
  if (portal === 'LAB' || portal === 'COURIER') {
    await expect(page.locator('#login-laboratory')).toBeEnabled();
    await page.locator('#login-laboratory').selectOption('simlab');
  }
  await page.locator('#login-name').fill(name);
  await page.locator('#login-password').fill(password);
  const response = page.waitForResponse(r => r.url().endsWith('/platform/login/') && r.request().method() === 'POST');
  await page.getByRole('button', { name: 'Accéder à mon espace' }).click();
  const authenticated = await response;
  expect(authenticated.status()).toBe(200);
  apiTokens.set(key, (await authenticated.json()).token);
  await expect(page.locator('#login-name')).toHaveCount(0);
  browserSessions.set(key, await page.evaluate(() => Object.fromEntries(
    Array.from({ length: sessionStorage.length }, (_, i) => sessionStorage.key(i))
      .map(key => [key, sessionStorage.getItem(key)]))));
}

async function authenticate(request, name, role) {
  const key = `${role}:${name}`;
  if (apiTokens.has(key)) return apiTokens.get(key);
  const response = await request.post(backend + '/platform/login/', {
    data: { name, password, role, ...(['LAB', 'COURIER'].includes(role) ? { laboratory: 'simlab' } : {}) },
  });
  expect(response.status(), 'real API login').toBe(200);
  const token = (await response.json()).token;
  apiTokens.set(key, token);
  return token;
}

test('manager loads real cases and planning/workload/resource screens', async ({ page }, info) => {
  const problems = observe(page);
  await login(page);
  await page.getByRole('button', { name: 'Commandes', exact: true }).first().click();
  await page.getByLabel('Rechercher dans la gestion des commandes').fill('DEMO-PRINT-STANDARD');
  await expect(page.getByRole('button', { name: 'Ouvrir le diagramme DEMO-PRINT-STANDARD' })).toBeVisible();
  await page.getByRole('button', { name: 'Planning', exact: true }).click();
  await expect(page.getByLabel('Date du planning')).toBeVisible();
  await page.getByRole('button', { name: 'Charge', exact: true }).click();
  await expect(page.locator('td').filter({ hasText: 'Demo CAD A' }).first()).toBeVisible();
  await page.getByRole('button', { name: 'Paramètres et équipe', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Paramètres du moteur de planification' })).toBeVisible();
  await page.screenshot({ path: info.outputPath('real-planning.png'), fullPage: true });
  expect(problems).toEqual([]);
});

async function preparePlanningCase(request, track = 'NUMERIQUE') {
  const manager = await authenticate(request, 'Demo Manager', 'LAB');
  const dentist = await authenticate(request, 'Demo Dentist', 'DENTIST');
  const headers = { Host: tenantHost, Authorization: `Bearer ${manager}` };
  const clinics = await request.get(backend + '/platform/dentist/clinics/?laboratory=simlab', {
    headers: { Authorization: `Bearer ${dentist}` },
  });
  expect(clinics.status()).toBe(200);
  const clinicData = await clinics.json();
  const clinic = (Array.isArray(clinicData) ? clinicData : clinicData.results)[0];
  const reference = 'BROWSER-' + randomUUID().slice(0, 8);
  const creation = await request.post(backend + '/platform/dentist/orders/', {
    headers: { Authorization: `Bearer ${dentist}`, 'Idempotency-Key': randomUUID() },
    data: { laboratory_id: 'simlab', patient_ref: reference, dentist_name: 'Demo Dentist',
      disinfected: true, impression_type: track, partner_clinic: clinic.id, delivery_service: 'NEXT_DAY',
      clinical_items: [{ tooth_number: 11, function: 'Browser test', form: 'Anatomique', shade: 'A2', material: 'Provisoire Résine' }] },
  });
  expect(creation.status()).toBe(201);
  const order = await creation.json();
  const url = `${backend}/api/prescriptions/${order.id}/`;
  const command = async (action, data = {}) => {
    const response = await request.post(url + 'command/', {
      headers: { ...headers, 'Idempotency-Key': randomUUID() }, data: { action, data },
    });
    expect(response.status(), `${action}: ${await response.text()}`).toBe(200);
    return response.json();
  };
  expect((await request.patch(url, { headers, data: { accepted: true } })).status()).toBe(200);
  await command('quote', { surcharge: '100.00', notes: 'Synthetic browser test manual J+1 quote' });
  await command('advance');
  await command('advance', { analysis_validated: true });
  if (track === 'PHYSIQUE') {
    const qr = syntheticQrToken(order.id);
    await command('pickup', { qr_token: qr });
    await command('lab-deposit', { qr_token: qr });
    await command('inspection', { stage: 'PHYSICAL', checks: {
      deformation: true, bubbles: true, limits: true, occlusion: true, hygiene: true,
    } });
  }
  await command('advance', { reception_validated: true });
  if (track === 'NUMERIQUE') {
    const upload = await request.post(url + 'attachments/', { headers, multipart: {
    kind: 'STL', file: { name: 'browser-test.stl', mimeType: 'model/stl',
      buffer: Buffer.from('solid demo\nfacet normal 0 0 1\nouter loop\nvertex 0 0 0\nvertex 1 0 0\nvertex 0 1 0\nendloop\nendfacet\nendsolid demo') },
    } });
    expect(upload.status()).toBe(201);
    await command('inspection', { stage: 'DIGITAL', checks: { margins: true, occlusion: true, space: true, scan_quality: true } });
  } else {
    await command('advance'); // Plaster casting.
    await command('advance'); // Laboratory scan.
    await command('advance'); // Model/scan checkpoint.
    await command('inspection', { stage: 'MODEL', checks: { model: true, scan: true } });
  }
  await command('advance');
  return { reference, order, url, headers, command, dentist };
}

function syntheticQrToken(id) {
  // Scanner input only: read the existing synthetic case's signed label through
  // the same function as the PNG endpoint. No production endpoint or DB writes.
  const source = `import os; from uuid import UUID; from django_tenants.utils import schema_context; from api.models import Prescription; from api.case_commands import qr_token; assert os.environ.get('CABINET_SIMULATION') == '1'; ctx=schema_context('simlab'); ctx.__enter__(); order=Prescription.objects.get(pk=UUID('${id}'),patient_ref__startswith='BROWSER-'); print(qr_token(order)); ctx.__exit__(None,None,None)`;
  return execFileSync('docker', ['compose', '-p', composeProject, '-f', 'compose.demo.yml', 'exec', '-T', 'backend',
    'python', 'manage.py', 'shell', '--verbosity', '0', '-c', source], {
    cwd: new URL('../..', import.meta.url), encoding: 'utf8', windowsHide: true,
  }).trim();
}

test('planning route selection and advancement work in one request', async ({ request }) => {
  const { url, headers } = await preparePlanningCase(request);
  const response = await request.post(url + 'command/', {
    headers: { ...headers, 'Idempotency-Key': randomUUID() },
    data: { action: 'advance', data: { production_method: 'IMPRESSION_3D',
      delivery_date: new Date(Date.now() + 86400000).toISOString().slice(0, 10) } },
  });
  expect(response.status(), `Route selection regression: ${await response.text()}`).toBe(200);
});

test('human starts, pauses, resumes and completes a real CAO task', async ({ page, request }, info) => {
  const manager = await authenticate(request, 'Demo Manager', 'LAB');
  const headers = { Host: tenantHost, Authorization: `Bearer ${manager}` };
  // Failed earlier runs may leave their own CAD fixture running. Finish that
  // legitimate step through its audited command; never delete/reset history or
  // move seeded/user cases. This keeps reruns independent of old test failures.
  const running = await (await request.get(`${backend}/api/planning/tasks/?status=IN_PROGRESS&page_size=200`, { headers })).json();
  for (const row of running.results.filter(row => row.workflow_step === 'SALLE_CAO'
    && row.patient_ref.startsWith('BROWSER-'))) {
    const detail = await (await request.get(`${backend}/api/prescriptions/${row.prescription}/`, { headers })).json();
    if (detail.design_validation_requested) continue;
    const completed = await request.post(`${backend}/api/prescriptions/${row.prescription}/command/`, {
      headers: { ...headers, 'Idempotency-Key': randomUUID() },
      data: { action: 'planning-complete', data: {
        task: row.id, notes: 'Finish CAD fixture left by an interrupted browser verification',
      } },
    });
    expect(completed.status(), await completed.text()).toBe(200);
  }
  // READY means business prerequisites passed, not that a future slot is due.
  // Use the next due reservation instead of jumping a newly created case ahead.
  let task, order;
  await expect.poll(async () => {
    const response = await request.get(`${backend}/api/planning/tasks/?status=READY&page_size=200`, { headers });
    expect(response.status()).toBe(200);
    const rows = await response.json();
    for (const candidate of rows.results.filter(row => row.workflow_step === 'SALLE_CAO'
      && Date.parse(row.planned_start) <= Date.now())) {
      const detail = await (await request.get(`${backend}/api/prescriptions/${candidate.prescription}/`, { headers })).json();
      if (!detail.design_validation_requested) { task = candidate; order = detail; return true; }
    }
    return false;
  }, { timeout: 45000, message: 'A due CAO reservation without an external design gate is required' }).toBe(true);
  const reference = order.patient_ref;
  const url = `${backend}/api/prescriptions/${order.id}/`;
  const taskState = async () => (await (await request.get(`${backend}/api/planning/tasks/${task.id}/`, { headers })).json()).status;
  const problems = observe(page);
  await login(page);
  await page.getByRole('button', { name: 'Commandes', exact: true }).first().click();
  await page.getByLabel('Rechercher dans la gestion des commandes').fill(reference);
  await page.getByRole('button', { name: `Ouvrir le diagramme ${reference}` }).click();
  await page.getByRole('tab', { name: 'Progression et machines' }).click();
  const current = page.locator('.planning-step').filter({ has: page.locator('strong', { hasText: 'Conception numérique / CAO' }) });
  await expect(current).toBeVisible();
  await page.getByRole('textbox', { name: 'Commentaire de progression / motif du blocage', exact: true }).fill('Supervisor starts ready CAD work; movable forecasts may be recalculated');
  await current.getByRole('button', { name: 'Démarrer maintenant et replanifier', exact: true }).click();
  await expect.poll(taskState).toBe('IN_PROGRESS');
  await page.getByRole('textbox', { name: 'Commentaire de progression / motif du blocage', exact: true }).fill('Synthetic operator pause for browser verification');
  await current.getByRole('button', { name: 'Mettre en pause', exact: true }).click();
  await expect.poll(taskState).toBe('PAUSED');
  await current.getByRole('button', { name: 'Reprendre', exact: true }).click();
  await expect.poll(taskState).toBe('IN_PROGRESS');
  await current.getByRole('button', { name: 'Terminer l’étape', exact: true }).click();
  await expect.poll(taskState).toBe('COMPLETED');
  await expect.poll(async () => (await (await request.get(url, { headers })).json()).status)
    .toBe(order.production_method === 'IMPRESSION_3D' ? 'PREPARATION_3D' : 'PREPARATION_CNC');
  await page.screenshot({ path: info.outputPath('real-workflow.png'), fullPage: true });
  expect(problems).toEqual([]);
});

async function equipmentTask(request,order,headers) {
  const response=await request.get(`${backend}/api/planning/tasks/?prescription=${order.id}&include_terminal=true`,{headers});
  expect(response.status()).toBe(200);
  return (await response.json()).results.find(row=>row.workflow_step===order.status&&!['COMPLETED','CANCELLED'].includes(row.status));
}

async function finishAttendedEquipment(request,state,headers,command) {
  let task=await equipmentTask(request,state,headers);
  if (!task||!task.resource_phase||task.resource_phase==='MANUAL') return false;
  await expect.poll(async()=>{
    task=await equipmentTask(request,state,headers);
    return Boolean(task?.assigned_employee&&task.planned_start);
  },{timeout:45000,message:'Qualified equipment reservation must be available'}).toBe(true);
  const data={task:task.id,notes:'Synthetic operator confirms physical work; no device event or clinical approval simulated'};
  if(task.resource_phase==='PLANNED')await command('planning-start',{...data,start_now:true});
  if(['PLANNED','SETUP'].includes(task.resource_phase))await command('planning-launch-cycle',data);
  if(['PLANNED','SETUP','CYCLE'].includes(task.resource_phase))await command('planning-cycle-finished',data);
  if(['PLANNED','SETUP','CYCLE','AWAITING_UNLOAD'].includes(task.resource_phase))await command('planning-begin-unload',data);
  await command('planning-complete',data);
  return true;
}

test('equipment phases release technician and require explicit unloading through real UI',async({page,request},info)=>{
  const {reference,order,url,headers,command}=await preparePlanningCase(request);
  await command('advance',{production_method:'IMPRESSION_3D',delivery_date:new Date(Date.now()+86400000).toISOString().slice(0,10)});
  const lot=await request.post(backend+'/api/production-lots/',{headers,data:{code:reference,prescriptions:[order.id]}});
  expect(lot.status()).toBe(201);
  await command('advance'); // CAD complete; still no clinical quality approval.
  await command('advance'); // Preparation complete; physical setup must now start.
  const state=await(await request.get(url,{headers})).json();
  let task;
  await expect.poll(async()=>{
    task=await equipmentTask(request,state,headers);
    return task?.resource_phase==='PLANNED'&&Boolean(task.assigned_employee);
  },{timeout:45000}).toBe(true);
  const phase=async()=>(await(await request.get(`${backend}/api/planning/tasks/${task.id}/`,{headers})).json()).resource_phase;
  const problems=observe(page);
  await login(page);
  await page.getByRole('button',{name:'Commandes',exact:true}).first().click();
  await page.getByLabel('Rechercher dans la gestion des commandes').fill(reference);
  await page.getByRole('button',{name:`Ouvrir le diagramme ${reference}`}).click();
  await page.getByRole('tab', { name: 'Progression et machines' }).click();
  const current=page.locator('.planning-step').filter({has:page.locator('strong',{hasText:task.title})});
  await expect(current).toBeVisible();
  await page.getByRole('textbox', { name: 'Commentaire de progression / motif du blocage', exact: true }).fill('Synthetic operator verifies actual machine phase for browser acceptance');
  const early=current.getByRole('button',{name:'Démarrer maintenant et replanifier',exact:true});
  if(await early.isVisible())await early.click();
  else await current.getByRole('button',{name:'Démarrer',exact:true}).click();
  await expect.poll(phase).toBe('SETUP');
  await current.getByRole('button',{name:'Chargement terminé : lancer le cycle',exact:true}).click();
  await expect.poll(phase).toBe('CYCLE');
  await expect(current.getByText('Cycle autonome · technicien libéré',{exact:true})).toBeVisible();
  await page.getByRole('combobox',{name:'Commentaire de progression / motif du blocage — motif prédéfini'}).selectOption('cycle-finished');
  await current.getByRole('button',{name:'Confirmer la fin réelle du cycle',exact:true}).click();
  await expect.poll(phase).toBe('AWAITING_UNLOAD');
  expect((await(await request.get(url,{headers})).json()).status).toBe('IMPRESSION_3D');
  await expect(current.getByText('Cycle terminé · machine occupée jusqu’au déchargement',{exact:true})).toBeVisible();
  await current.getByRole('button',{name:'Commencer le déchargement',exact:true}).click();
  await expect.poll(phase).toBe('UNLOADING');
  await current.getByRole('button',{name:'Confirmer le déchargement et terminer',exact:true}).click();
  await expect.poll(phase).toBe('FINISHED');
  const finished=await(await request.get(url,{headers})).json();
  expect(finished.status).not.toBe('IMPRESSION_3D');expect(finished.quality_validated).toBe(false);
  await page.screenshot({path:info.outputPath('real-equipment-phases.png'),fullPage:true});
  expect(problems).toEqual([]);
});

for (const [track, route] of [['PHYSIQUE', 'CFAO'], ['NUMERIQUE', 'IMPRESSION_3D']]) {
  test(`${track}: real workflow reaches delivery, fitting and monthly statement`, async ({ page, request }, info) => {
    const { reference, order, url, headers, command, dentist } = await preparePlanningCase(request, track);
    await command('advance', { production_method: route,
      delivery_date: new Date(Date.now() + 86400000).toISOString().slice(0, 10) });
    const lot = await request.post(backend + '/api/production-lots/', {
      headers, data: { code: reference, prescriptions: [order.id] },
    });
    expect(lot.status(), await lot.text()).toBe(201);
    let state = await (await request.get(url, { headers })).json();
    for (let step = 0; state.status !== 'CONTROLE_QUALITE' && step < 12; step++) {
      if(!await finishAttendedEquipment(request,state,headers,command))await command('advance');
      state = await (await request.get(url, { headers })).json();
    }
    expect(state.status).toBe('CONTROLE_QUALITE');
    await command('inspection', { stage: 'QUALITY', checks: {
      margins: true, contacts: true, shade: true, occlusion: true,
      cosmetic: true, glazing: true, polishing: true,
    } });
    await command('advance');
    const slip = await request.get(url + 'delivery-slip/', { headers });
    expect(slip.status()).toBe(200);
    expect((await slip.body()).subarray(0, 5).toString()).toBe('%PDF-');
    await command('advance');
    const courier = await authenticate(request, 'Demo Courier', 'COURIER');
    const checkout = await request.post(url + 'command/', {
      headers: { Host: tenantHost, Authorization: `Bearer ${courier}`, 'Idempotency-Key': randomUUID() },
      data: { action: 'checkout', data: { qr_token: syntheticQrToken(order.id) } },
    });
    expect(checkout.status(), await checkout.text()).toBe(200);
    for (const [action, data] of [
      ['confirm-delivery', { pin: order.delivery_pin_once }], ['fitting', { passed: true }],
    ]) {
      const response = await request.post(`${backend}/platform/dentist/orders/simlab/${order.id}/command/`, {
        headers: { Authorization: `Bearer ${dentist}`, 'Idempotency-Key': randomUUID() }, data: { action, data },
      });
      expect(response.status(), `${action}: ${await response.text()}`).toBe(200);
    }
    state = await (await request.get(url, { headers })).json();
    expect(state.status).toBe('CLOTURE');
    const statements = await request.get(backend + '/api/billing/statement-lines/?page_size=200', { headers });
    expect(statements.status()).toBe(200);
    const matching = (await statements.json()).results.filter(row => row.prescription === order.id);
    expect(matching, 'Delivered case enters the monthly statement exactly once').toHaveLength(1);
    const [line] = matching;
    const problems = observe(page);
    await login(page);
    await page.locator('button.sidebar-link[aria-label="Facturation"]').click();
    await expect(page.getByRole('heading', { name: 'Situations mensuelles et facturation' })).toBeVisible();
    await page.getByLabel('Cabinet et mois de livraison').selectOption(line.period);
    await expect(page.getByText(reference, { exact: false }).first()).toBeVisible();
    await page.screenshot({ path: info.outputPath(`${track.toLowerCase()}-monthly-statement.png`), fullPage: true });
    expect(problems).toEqual([]);
    // Current-month delivery is intentionally left open. Historical monthly
    // closing/PDF/30% pricing are covered in the isolated backend test database.
  });
}

test('dentist sees owned demo cases through the real portal', async ({ page }, info) => {
  const problems = observe(page);
  await login(page, 'Demo Dentist', 'DENTIST');
  await page.getByRole('button', { name: /Mes commandes/ }).click();
  await page.getByRole('textbox', { name: 'Rechercher mes commandes' }).fill('DEMO-CNC-APPROVAL');
  await expect(page.getByRole('heading', { name: /DEMO-CNC-APPROVAL/ })).toBeVisible();
  await page.screenshot({ path: info.outputPath('real-dentist.png'), fullPage: true });
  expect(problems).toEqual([]);
});

test('mobile login and manager navigation stay usable', async ({ page }, info) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await login(page);
  const navigation = page.getByRole('button', { name: /Ouvrir.*menu|Ouvrir.*navigation|Menu/i }).first();
  await expect(navigation).toBeVisible();
  await navigation.click();
  await expect(page.getByRole('button', { name: 'Planning', exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Planning', exact: true }).click();
  await expect(page.getByLabel('Date du planning')).toBeVisible();
  await page.screenshot({ path: info.outputPath('real-mobile.png'), fullPage: true });
});
