import test from 'node:test';
import assert from 'node:assert/strict';
import { applyFirstToAll, chartOrder, toggleTooth } from './toothPickerHelpers.js';

test('chart covers the 32 FDI teeth once', () => {
  assert.equal(chartOrder.length, 32);
  assert.equal(new Set(chartOrder).size, 32);
});

test('toggling adds empty rows in chart order and removes on second toggle', () => {
  let items = toggleTooth([], 21);
  items = toggleTooth(items, 11);
  items = toggleTooth(items, 46);
  assert.deepEqual(items.map(item => item.tooth_number), [11, 21, 46]);
  assert.deepEqual(items[0], { tooth_number: 11, function: '', form: '', shade: '', material: '' });
  items = toggleTooth(items, '21');
  assert.deepEqual(items.map(item => item.tooth_number), [11, 46]);
});

test('unknown tooth numbers are ignored and existing details are kept', () => {
  const items = [{ tooth_number: 11, function: 'Couronne', form: 'Anatomique', shade: 'A2', material: 'E-Max' }];
  assert.equal(toggleTooth(items, 19), items);
  assert.equal(toggleTooth(items, 21)[0].shade, 'A2');
});

test('apply to all copies only the first row details, never the tooth', () => {
  const items = [
    { tooth_number: 11, function: 'Couronne', form: 'Anatomique', shade: 'A2', material: 'E-Max' },
    { tooth_number: 21, function: '', form: '', shade: '', material: '' },
  ];
  assert.deepEqual(applyFirstToAll(items)[1], { tooth_number: 21, function: 'Couronne', form: 'Anatomique', shade: 'A2', material: 'E-Max' });
  assert.equal(applyFirstToAll([items[0]]).length, 1);
});
