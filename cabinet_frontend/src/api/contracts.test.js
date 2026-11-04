import test from 'node:test';
import assert from 'node:assert/strict';
import { acceptsQuantity, allRows, completed, money, quantityInput, quantityText, retryableRequest, rowsOf } from './contracts.js';

test('loads every page while preserving endpoint, query and abort signal', async () => {
  const calls = []; const signal = new AbortController().signal;
  const client = { get: async (path, config) => {
    calls.push([path, config]);
    return { data: config.params.page === 1 ? { results: [{ id: 1 }], next: 'https://untrusted.example/api/other/?page=2' } : { results: [{ id: 2 }], next: null } };
  } };
  assert.deepEqual(await allRows(client, 'prescriptions/', { include_completed: true }, signal), [{ id: 1 }, { id: 2 }]);
  assert.equal(calls[1][0], 'prescriptions/');
  assert.deepEqual(calls[1][1], { params: { include_completed: true, page: 2 }, signal });
});

test('supports dentist array responses and rejects malformed/repeating pagination', async () => {
  assert.deepEqual(await allRows({ get: async () => ({ data: [{ id: 'dentist-case' }] }) }, 'orders/'), [{ id: 'dentist-case' }]);
  assert.throws(() => rowsOf({ detail: 'No permission' }), /inattendue/);
  await assert.rejects(() => allRows({ get: async () => ({ data: { results: [], next: '?page=1' } }) }, 'orders/'), /Pagination/);
});

test('same submission reuses its key after uncertain transport/server failure', async () => {
  const request = retryableRequest(); const keys = []; let fail = true;
  const client = { post: async (_, payload, config) => { keys.push(config.headers['Idempotency-Key']); if (fail) throw new Error('Connection lost'); return { data: payload }; } };
  const payload = { clinical_items: [{ tooth_number: 11 }], laboratory_id: 'labo1' };
  await assert.rejects(() => request(client, 'orders/', payload));
  fail = false; await request(client, 'orders/', payload);
  assert.equal(keys[0], keys[1]);
  await request(client, 'orders/', payload);
  assert.notEqual(keys[1], keys[2]);
});

test('changed submission and a rejected PIN receive new keys', async () => {
  const request = retryableRequest(); const keys = [];
  const client = { post: async (_, payload, config) => { keys.push(config.headers['Idempotency-Key']); throw Object.assign(new Error('Wrong PIN'), { response: { status: 400 } }); } };
  await assert.rejects(() => request(client, 'command/', { action: 'confirm-delivery', data: { pin: '0000' } }));
  await assert.rejects(() => request(client, 'command/', { action: 'confirm-delivery', data: { pin: '0000' } }));
  assert.notEqual(keys[0], keys[1]);
  const uncertain = retryableRequest(); const uncertainKeys = [];
  const server = { post: async (_, payload, config) => { uncertainKeys.push(config.headers['Idempotency-Key']); throw new Error('Offline'); } };
  await assert.rejects(() => uncertain(server, 'orders/', { laboratory_id: 'labo1' }));
  await assert.rejects(() => uncertain(server, 'orders/', { laboratory_id: 'labo2' }));
  assert.notEqual(uncertainKeys[0], uncertainKeys[1]);
});

test('manual quotes are never displayed as zero and fitting/closed are completed', () => {
  assert.match(money(null), /Devis/); assert.match(money('1200.00'), /1.*200/);
  assert.equal(completed('ESSAYAGE'), true); assert.equal(completed('CLOTURE'), true);
  assert.equal(completed('EN_ROUTE_CABINET'), false);
});

test('quantities display and accept at most two decimal places', () => {
  assert.equal(quantityText('12.000000'), '12');
  assert.equal(quantityText('12.345678'), '12,35');
  assert.equal(quantityText('-0.250000'), '-0,25');
  assert.equal(quantityInput('12.345678'), '12.35');
  assert.equal(quantityInput('12.30'), '12.30');
  assert.equal(acceptsQuantity('12.34'), true);
  assert.equal(acceptsQuantity('12,34'), true);
  assert.equal(acceptsQuantity('12.345'), false);
  assert.equal(acceptsQuantity('1e-6'), false);
  assert.equal(acceptsQuantity('-1'), false);
});
