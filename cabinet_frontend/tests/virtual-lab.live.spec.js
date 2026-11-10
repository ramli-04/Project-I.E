import { randomUUID } from 'node:crypto';
import { test, expect } from '@playwright/test';

// Real HTTP only: no route interception, fixtures replacing responses, or preview adapter.
const backend = 'http://127.0.0.1:18000';
const password = 'Demo-Lab-2026!';
const tenantHost = 'simlab.localhost';

test.beforeAll(async ({ request }) => {
  const response = await request.get(backend + '/platform/environment/');
  expect(response.status()).toBe(200);
  expect((await response.json()).mode).toBe('SIMULATION');
});

test('browser preflight allows the required idempotency header', async ({ request }) => {
  const response = await request.fetch(backend + '/api/prescriptions/', {
    method: 'OPTIONS', headers: {
      Host: tenantHost, Origin: 'http://localhost:18080',
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
  expect((await response).status()).toBe(200);
  await expect(page.locator('#login-name')).toHaveCount(0);
}

async function authenticate(request, name, role) {
  const response = await request.post(backend + '/platform/login/', {
    data: { name, password, role, ...(role === 'LAB' ? { laboratory: 'simlab' } : {}) },
  });
  expect(response.status(), 'real API login').toBe(200);
  return (await response.json()).token;
}

test('manager loads real cases and planning/workload/resource screens', async ({ page }, info) => {
  const problems = observe(page);
  await login(page);
  await page.getByRole('button', { name: 'Commandes', exact: true }).first().click();
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

async function preparePlanningCase(request) {
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
      disinfected: true, impression_type: 'NUMERIQUE', partner_clinic: clinic.id, delivery_service: 'NEXT_DAY',
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
  };
  expect((await request.patch(url, { headers, data: { accepted: true } })).status()).toBe(200);
  await command('quote', { surcharge: '100.00', notes: 'Synthetic browser test manual J+1 quote' });
  await command('advance');
  await command('advance', { analysis_validated: true });
  await command('advance', { reception_validated: true });
  const upload = await request.post(url + 'attachments/', { headers, multipart: {
    kind: 'STL', file: { name: 'browser-test.stl', mimeType: 'model/stl',
      buffer: Buffer.from('solid demo\nfacet normal 0 0 1\nouter loop\nvertex 0 0 0\nvertex 1 0 0\nvertex 0 1 0\nendloop\nendfacet\nendsolid demo') },
  } });
  expect(upload.status()).toBe(201);
  await command('inspection', { stage: 'DIGITAL', checks: { margins: true, occlusion: true, space: true, scan_quality: true } });
  await command('advance');
  return { reference, order, url, headers, command };
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
  const { reference, order, url, headers, command } = await preparePlanningCase(request);
  // Valid two-request workaround isolates later controls from the route-selection regression above.
  const route = await request.patch(url, { headers, data: {
    production_method: 'IMPRESSION_3D', delivery_date: new Date(Date.now() + 86400000).toISOString().slice(0, 10),
  } });
  expect(route.status()).toBe(200);
  await command('advance');
  const tasksUrl = `${backend}/api/planning/tasks/?prescription=${order.id}`;
  let task;
  await expect.poll(async () => {
    const rows = await (await request.get(tasksUrl, { headers })).json();
    task = rows.results.find(row => row.workflow_step === 'SALLE_CAO');
    return task?.status;
  }, { timeout: 45000 }).toBe('READY');
  const taskState = async () => (await (await request.get(`${backend}/api/planning/tasks/${task.id}/`, { headers })).json()).status;
  const problems = observe(page);
  await login(page);
  await page.getByRole('button', { name: 'Commandes', exact: true }).first().click();
  await page.getByLabel('Rechercher dans la gestion des commandes').fill(reference);
  await page.getByRole('button', { name: `Ouvrir le diagramme ${reference}` }).click();
  const current = page.locator('.planning-step').filter({ has: page.locator('strong', { hasText: 'Conception numérique / CAO' }) });
  await current.getByRole('button', { name: 'Démarrer', exact: true }).click();
  await expect.poll(taskState).toBe('IN_PROGRESS');
  await page.getByLabel('Commentaire de progression / motif du blocage').fill('Synthetic operator pause for browser verification');
  await current.getByRole('button', { name: 'Mettre en pause', exact: true }).click();
  await expect.poll(taskState).toBe('PAUSED');
  await current.getByRole('button', { name: 'Reprendre', exact: true }).click();
  await expect.poll(taskState).toBe('IN_PROGRESS');
  await current.getByRole('button', { name: 'Terminer l’étape', exact: true }).click();
  await expect.poll(taskState).toBe('COMPLETED');
  await expect.poll(async () => (await (await request.get(url, { headers })).json()).status).toBe('PREPARATION_3D');
  await page.screenshot({ path: info.outputPath('real-workflow.png'), fullPage: true });
  expect(problems).toEqual([]);
});

test('dentist sees owned demo cases through the real portal', async ({ page }, info) => {
  const problems = observe(page);
  await login(page, 'Demo Dentist', 'DENTIST');
  await page.getByRole('button', { name: /Mes commandes/ }).click();
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
