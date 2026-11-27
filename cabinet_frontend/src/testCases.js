// Presentation filter for automated BROWSER- test cases in the synthetic demo only.
// Hidden: those paused with the documented test note, or closed for more than a day.
// Fresh BROWSER- cases created by a running test stay visible.
export const TEST_PAUSE_NOTE = 'Données de test automatisées — hors démonstration';
export const ARCHIVE_NOTE = 'Ancien dossier de démonstration — archivé';
const DAY = 24 * 60 * 60 * 1000;
const simulationBuild = () => { try { return import.meta.env?.VITE_SIMULATION === '1'; } catch { return false; } };

export function isAutomatedTestCase(order, { now = Date.now(), simulation = simulationBuild() } = {}) {
  if (!simulation || !order) return false;
  if (order.is_paused && String(order.pause_reason || '').includes(ARCHIVE_NOTE)) return true;
  if (!String(order.patient_ref || '').startsWith('BROWSER-')) return false;
  if (order.is_paused && String(order.pause_reason || '').includes(TEST_PAUSE_NOTE)) return true;
  const updated = Date.parse(order.updated_at || '');
  return order.status === 'CLOTURE' && Number.isFinite(updated) && now - updated > DAY;
}

export function splitTestCases(rows, show, options) {
  const hidden = rows.filter(row => isAutomatedTestCase(row, options));
  return { visible: show ? rows : rows.filter(row => !hidden.includes(row)), hiddenCount: hidden.length };
}

export function readShowTestCases() {
  try { return sessionStorage.getItem('show_test_cases') === '1'; } catch { return false; }
}
export function writeShowTestCases(value) {
  try { sessionStorage.setItem('show_test_cases', value ? '1' : '0'); } catch { /* per-tab convenience only */ }
}
