export const upperTeeth = [18,17,16,15,14,13,12,11,21,22,23,24,25,26,27,28];
export const lowerTeeth = [48,47,46,45,44,43,42,41,31,32,33,34,35,36,37,38];
export const chartOrder = [...upperTeeth, ...lowerTeeth];

export const emptyToothItem = tooth => ({ tooth_number: tooth, function: '', form: '', shade: '', material: '' });

export function sortByChart(items) {
  return [...items].sort((a, b) => chartOrder.indexOf(Number(a.tooth_number)) - chartOrder.indexOf(Number(b.tooth_number)));
}

export function toggleTooth(items, tooth) {
  const number = Number(tooth);
  if (!chartOrder.includes(number)) return items;
  if (items.some(item => Number(item.tooth_number) === number)) return items.filter(item => Number(item.tooth_number) !== number);
  return sortByChart([...items, emptyToothItem(number)]);
}

export function applyFirstToAll(items) {
  if (items.length < 2) return items;
  const { function: fn, form, shade, material } = items[0];
  return items.map((item, index) => index === 0 ? item : { ...item, function: fn, form, shade, material });
}
