import { AxiosError } from 'axios';

export const previewMode = import.meta.env.MODE === 'demo';
const lab = { id: 1, identifier: 'labo1', name: 'Laboratoire Démonstration' };
const clinic = { id: 1, name: 'Cabinet Démonstration', pickup_address: '12 avenue Exemple, Casablanca', contact_phone: '0000000000', contact_email: '', platform_dentist: 1 };
const stages = [
  ['DEMANDE_RECUE', 'Demande reçue'], ['ANALYSE_DEMANDE', 'Analyse de la demande'], ['ATTENTE_RAMASSAGE', 'Ramassage'], ['EN_ROUTE_LABO', 'Transport vers le laboratoire'], ['A_CONFIRMER', 'Réception'], ['CONTROLE_DOSSIER', 'Contrôle du dossier'], ['COULEE_PLATRE', 'Coulée du plâtre'], ['SCAN_LABO', 'Scan laboratoire'], ['CONTROLE_MODELE', 'Contrôle modèle'], ['PLANIFICATION', 'Planification'], ['SALLE_CAO', 'Conception CAO'], ['PREPARATION_CNC', 'Préparation FAO'], ['USINAGE_CNC', 'Usinage'], ['FINITION', 'Finition'], ['CONTROLE_QUALITE', 'Contrôle qualité'], ['CONDITIONNEMENT', 'Conditionnement'], ['PRET_EXPEDITION', 'Prêt à expédier'], ['EN_ROUTE_CABINET', 'Livraison'], ['LIVRE', 'Livré'], ['ESSAYAGE', 'Essayage'], ['CLOTURE', 'Clôturé'],
];
const statuses = ['DEMANDE_RECUE','SALLE_CAO','CONTROLE_QUALITE','PRET_EXPEDITION','ATTENTE_RAMASSAGE','LIVRE'];
const orders = statuses.map((status, i) => ({
  id: `00000000-0000-4000-8000-${String(i + 1).padStart(12, '0')}`,
  patient_ref: `DEMO-${String(i + 1).padStart(3, '0')}`, dentist_name: 'Dentiste Démonstration',
  laboratory_id: 'labo1', laboratory_name: lab.name, partner_clinic: 1,
  clinic_name: clinic.name, pickup_address: clinic.pickup_address, contact_phone: clinic.contact_phone,
  accepted: i > 0, status, status_label: stages.find(s => s[0] === status)[1],
  next_status: stages[stages.findIndex(s => s[0] === status) + 1]?.[0], workflow_steps: stages.map(([key,label]) => ({ key,label })),
  tooth_number: String(11 + i), material: 'Zircone', shade: 'A2', impression_type: 'PHYSIQUE',
  clinical_items: [{ tooth_number: 11 + i, function: 'Couronne', form: 'Anatomique', shade: 'A2', material: 'Zircone' }],
  created_at: '2026-11-01T09:00:00Z', updated_at: '2026-11-04T10:00:00Z',
  delivery_date: '2026-11-06', production_method: 'CFAO', thermal_treatment: 'AUCUN',
  total_price: i === 2 ? '1560.00' : '1200.00', base_amount: '1200.00', express_surcharge: i === 2 ? '360.00' : '0.00',
  delivery_service: i === 2 ? 'EXPRESS' : 'STANDARD', is_fast_track: i === 2,
  billing_stage: 'COMMANDE', is_paused: false, pause_reason: '', current_issues: '', technical_notes: '', workstation_notes: {},
  analysis_validated: i > 0, reception_validated: i > 0, quality_validated: i > 2,
  production_attempt: 1, intake_revision: 1, intake_version: 2, workflow_history: [], deadline_suspended_seconds: 0,
}));
const inventory = [{ id: 1, material_name: 'Disque zircone', quantity: '12.000000', unit: 'DISQUE', alert_threshold: '3', unit_cost: '350', is_low_stock: false }, { id: 2, material_name: 'Plâtre dentaire', quantity: '800.000000', unit: 'GRAMMES', alert_threshold: '1000', unit_cost: '0.15', is_low_stock: true }];
const envelope = results => ({ count: results.length, next: null, previous: null, results });

export async function previewAdapter(config) {
  const path = config.url.replace(/^\/+/, '').split('?')[0];
  const platform = config.baseURL?.includes('/platform/');
  const method = (config.method || 'get').toLowerCase();
  const payload = typeof config.data === 'string' ? JSON.parse(config.data) : config.data || {};
  let data;
  if (platform && path === 'login/' && method === 'post') {
    const role = ['LAB','DENTIST','COURIER','ADMIN'].includes(payload.role) ? payload.role : 'LAB';
    data = { token: 'local-preview-only', account: { id: 1, name: payload.name || 'Démo', role, email: '', workstation_role: 'MANAGER', ...(['LAB','COURIER'].includes(role) ? { laboratory_id: 'labo1', laboratory_name: lab.name } : {}) } };
  } else if (platform && path === 'logout/' && method === 'post') data = {};
  else if (method !== 'get') {
    const response = { status: 403, statusText: 'Preview is read only', data: { detail: 'Aperçu en lecture seule : démarrez le backend pour enregistrer des modifications.' }, config, headers: {} };
    throw new AxiosError(response.data.detail, 'ERR_BAD_REQUEST', config, null, response);
  } else if (platform) {
    if (path === 'laboratories/') data = [lab];
    else if (path === 'pricing/') data = { materials: { Zircone: '1200', 'E-Max': '1500', 'Céramo-Métal': '800', '100% Métal': '500', 'Provisoire Résine': '200' }, express_rate: '0.30', next_day: 'MANUAL_QUOTE', currency: 'MAD' };
    else if (path === 'dentist/orders/') data = orders;
    else if (path === 'dentist/clinics/') data = [clinic];
    else if (path === 'overview/') data = { laboratories: [{ ...lab, order_count: orders.length, paused_count: 0, account_count: 3 }], dentist_count: 1, account_count: 3, open_tickets: 0 };
    else if (path === 'accounts/') data = [{ id: 1, name: 'Dentiste Démonstration', email: '', role: 'DENTIST', is_active: true }];
    else if (path.endsWith('/evidence/')) data = { design_reviews: [], reworks: [], notifications: [] };
    else data = [];
  } else {
    if (path === 'prescriptions/') {
      let user; try { user = JSON.parse(sessionStorage.getItem('demo_user') || '{}'); } catch { user = {}; }
      data = envelope(user.role === 'Coursier' ? orders.filter(o => ['ATTENTE_RAMASSAGE','PRET_EXPEDITION'].includes(o.status)) : orders);
    } else if (path === 'inventory/') data = inventory;
    else if (path === 'employee-profiles/') data = [{ id: 1, user: 1, name: 'Youssef — Démonstration', role: 'CAO', contract_type: 'CDI', hire_date: '2026-01-05', is_available: true }, { id: 2, user: 2, name: 'Salma — Démonstration', role: 'QUALITE', contract_type: 'CDI', hire_date: '2026-02-02', is_available: true }];
    else if (path === 'partner-clinics/') data = [clinic];
    else if (path === 'production-lots/') data = envelope([{ id: 'demo-lot', code: 'LOT-DEMO-01', prescriptions: [orders[1].id], machine: 1, inventory_item: 1 }]);
    else if (path === 'machines/') data = [{ id: 1, name: 'Usineuse Démo', machine_type: 'USINEUSE_CNC', capacity: 8, status: 'ACTIF' }];
    else if (path.endsWith('/evidence/')) data = { inspections: [], design_reviews: [], reworks: [], events: [], notifications: [] };
    else if (path.startsWith('analytics/')) data = { ...envelope([]), analytics: { stale: false, last_refreshed_at: '2026-11-04T10:00:00Z' } };
    else if (path.startsWith('billing/') || path.startsWith('operations/') || path === 'inventory-transactions/') data = envelope([]);
    else data = [];
  }
  return { status: 200, statusText: 'OK', data: structuredClone(data), config, headers: {} };
}
