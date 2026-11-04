import React, { useState, useEffect, useRef, useCallback } from "react";
import api from "./api/client";
import platform from "./api/platform";
import DemoLogin from "./DemoLogin";
import AdminPortal from "./AdminPortal";
import SupportButton from "./SupportButton";
import LabBusinessConfiguration from "./LabBusinessConfiguration";
import LabAdminLayout from "./LabAdminLayout";
import { LabOverview, OrderManagement } from "./LabWorkspace";
import { AlertPopup } from './LabAlerts';
import { useLabAlerts } from './useLabAlerts';
import { useTenant } from "./contexts/useTenant";
import { 
  User, FileText, Package,
  ShieldCheck, LogOut,
  Settings, LayoutDashboard, ChevronDown
} from "lucide-react";
import DentistPortal from './DentistPortal';
import CourierPortal from './CourierPortal';
import FinanceDashboard from './FinanceDashboard';
import InventoryWorkspace from './InventoryWorkspace';
import OperationsDashboard from './OperationsDashboard';
import { allRows, errorText, workstation } from './api/contracts';
import { Feedback, Button } from './IntegrationUI';
import SidebarLogo from './SidebarLogo';
import { previewMode } from './api/preview';

export default function App() {
  return <>{previewMode && <div role="status" className="fixed bottom-2 left-1/2 z-50 w-max max-w-[95vw] -translate-x-1/2 rounded-xl border border-amber-400/40 bg-white px-4 py-2 text-center text-xs text-amber-800">Aperçu sans base de données · données fictives · lecture seule</div>}<Application /></>;
}

function Application() {
  const [user, setUser] = useState(() => {
    try { return JSON.parse(sessionStorage.getItem('demo_user') || 'null'); } catch { return null; }
  });
  const [orders, setOrders] = useState([]);
  const [orderError, setOrderError] = useState('');
  const [loadingOrders, setLoadingOrders] = useState(false);
  const loadSequence = useRef(0);
  const [labSection, setLabSection] = useState('main');
  const [labTab, setLabTab] = useState('dashboard');
  const [alertFocus, setAlertFocus] = useState(0);
  const [configTarget, setConfigTarget] = useState(null);
  const { tenant, clearTenant } = useTenant();
  const alertState = useLabAlerts(user?.role === 'Laboratoire' ? tenant?.id : null);
  
  const fetchOrders = useCallback(async () => {
    if (!user || user.role === 'Administrateur') return;
    const sequence = ++loadSequence.current;
    setLoadingOrders(true); setOrderError('');
    try {
      const rows = user.role === 'Cabinet Dentaire'
        ? await allRows(platform, 'dentist/orders/')
        : await allRows(api, 'prescriptions/', { include_completed: true });
      if (sequence === loadSequence.current) setOrders(rows);
    } catch (error) {
      if (sequence === loadSequence.current) setOrderError(errorText(error));
    } finally { if (sequence === loadSequence.current) setLoadingOrders(false); }
  }, [user]);
  useEffect(() => {
    if (user) void fetchOrders();
    return () => { loadSequence.current += 1; };
  }, [user, fetchOrders]);
  useEffect(() => {
    const expired = () => {
      loadSequence.current += 1;
      sessionStorage.removeItem('demo_token'); sessionStorage.removeItem('demo_user');
      setUser(null); setOrders([]); setOrderError(''); setLabSection('main');
      setLabTab('dashboard'); setConfigTarget(null); clearTenant();
    };
    window.addEventListener('cabinet-session-expired', expired);
    return () => window.removeEventListener('cabinet-session-expired', expired);
  }, [clearTenant]);
  const orderFeedback = <div className="orders-toolbar"><Feedback error={orderError} />
    {loadingOrders && <p role="status" className="text-sm text-slate-500">Chargement des commandes…</p>}
    <Button disabled={loadingOrders} onClick={fetchOrders}>Actualiser les commandes</Button>
  </div>;
  if (!user) return <DemoLogin setUser={setUser} />;

  if (user.role === 'Laboratoire') return <LabAdminLayout
    section={labSection}
    laboratoryName={tenant?.name || tenant?.id}
    onNavigate={section => { if (section === 'configuration') setConfigTarget(null); setLabSection(section); }}
    accountMenu={<><SupportButton /><AccountMenu user={user} tenant={tenant} onLogout={() => {
      const token = sessionStorage.getItem('demo_token');
      if (token) platform.post('logout/', {}, { headers: { Authorization: `Bearer ${token}` } }).catch(() => {});
      sessionStorage.removeItem('demo_token');
      sessionStorage.removeItem('demo_user');
      setUser(null); setOrders([]); setLabSection('main'); setLabTab('dashboard'); setConfigTarget(null); clearTenant();
    }} /></>}
  >
    {orderFeedback}
    <LabPortal key={tenant?.id} section={labSection} activeTab={labTab} setActiveTab={setLabTab} configTarget={configTarget} alertState={alertState} alertFocus={alertFocus} onAlertSelect={alert => {
      setConfigTarget({ section: alert.section, id: alert.resource_id, request: Date.now() });
      setLabSection('configuration');
    }} orders={orders} refresh={fetchOrders} />
    <AlertPopup alerts={alertState.alerts} onOpen={() => { setLabSection('main'); setLabTab('dashboard'); setAlertFocus(value => value + 1); }} />
  </LabAdminLayout>;

  return (
    <div className="portal-shell flex h-screen bg-[#f6f7f9] text-slate-900 font-sans overflow-hidden">
      {/* Sidebar */}
      <div className="portal-sidebar hidden w-64 shrink-0 bg-white border-r border-slate-200/80 p-6 md:flex md:flex-col">
        <div className="flex items-center gap-3 mb-10">
          <SidebarLogo />
        </div>
        
        {user.role === 'Laboratoire' && <nav aria-label="Navigation du laboratoire" className="space-y-2">
          {[
            ['main', 'Menu principal', LayoutDashboard],
            ['orders', 'Commandes', Package],
            ['billing', 'Facturation', FileText],
            ['configuration', 'Configuration', Settings],
          ].map(([key, label, Icon]) => <button key={key} onClick={() => { if (key === 'configuration') setConfigTarget(null); setLabSection(key); }} aria-current={labSection === key ? 'page' : undefined} className={`flex w-full items-center gap-3 rounded-xl px-4 py-3 text-sm font-medium transition-colors ${labSection === key ? 'border border-sky-400/20 bg-teal-600/15 text-teal-700' : 'border border-transparent text-slate-500 hover:bg-white hover:text-slate-900'}`}><Icon className="h-5 w-5" />{label}</button>)}
        </nav>}
        {user.role === 'Administrateur' && <nav aria-label="Navigation administration"><div className="flex items-center gap-3 rounded-xl border border-sky-400/20 bg-teal-600/15 px-4 py-3 text-sm font-medium text-teal-700"><LayoutDashboard className="h-5 w-5" />Administration</div></nav>}
      </div>

      {/* Main Content */}
      <div className="min-w-0 flex-1 overflow-y-auto">
        <header className="h-16 border-b border-slate-200/80 bg-white flex items-center justify-between gap-4 px-8 backdrop-blur-md sticky top-0 z-20">
          <div className="flex items-center gap-2 text-sm text-slate-500">
            <ShieldCheck className="w-4 h-4 text-emerald-700" />
            Système synchronisé
          </div>
          <div className="flex items-center gap-3">
          {['Laboratoire', 'Cabinet Dentaire'].includes(user.role) && <SupportButton />}
          <AccountMenu user={user} tenant={tenant} onLogout={() => {
            const token = sessionStorage.getItem('demo_token');
            if (token) platform.post('logout/', {}, { headers: { Authorization: `Bearer ${token}` } }).catch(() => {});
            sessionStorage.removeItem('demo_token');
            sessionStorage.removeItem('demo_user');
            setUser(null);
            setOrders([]);
            setLabSection('main');
            setLabTab('dashboard');
            setConfigTarget(null);
            clearTenant();
          }} />
          </div>
        </header>
        
        <main className="p-4 sm:p-8 max-w-7xl mx-auto">{user.role !== 'Administrateur' && orderFeedback}
          {user.role === "Administrateur" && <AdminPortal />}
          {user.role === "Cabinet Dentaire" && <DentistPortal user={user} orders={orders} refresh={fetchOrders} />}
          {user.role === "Laboratoire" && <LabPortal section={labSection} activeTab={labTab} setActiveTab={setLabTab} configTarget={configTarget} alertState={alertState} alertFocus={alertFocus} onAlertSelect={alert => {
            setConfigTarget({ section: alert.section, id: alert.resource_id, request: Date.now() });
            setLabSection('configuration');
          }} orders={orders} refresh={fetchOrders} />}
          {user.role === "Coursier" && <CourierPortal orders={orders} refresh={fetchOrders} />}
        </main>
        {user.role === 'Laboratoire' && <AlertPopup alerts={alertState.alerts} onOpen={() => {
          setLabSection('main'); setLabTab('dashboard'); setAlertFocus(value => value + 1);
        }} />}
      </div>
    </div>
  );
}

// ---------------- VIEWS ----------------

function AccountMenu({ user, tenant, onLogout }) {
  const [open, setOpen] = useState(false);
  const container = useRef(null);
  const trigger = useRef(null);

  useEffect(() => {
    if (!open) return;
    const dismissOutside = event => {
      if (!container.current?.contains(event.target)) setOpen(false);
    };
    const dismissEscape = event => {
      if (event.key === 'Escape') {
        setOpen(false);
        trigger.current?.focus();
      }
    };
    document.addEventListener('pointerdown', dismissOutside);
    document.addEventListener('focusin', dismissOutside);
    document.addEventListener('keydown', dismissEscape);
    return () => {
      document.removeEventListener('pointerdown', dismissOutside);
      document.removeEventListener('focusin', dismissOutside);
      document.removeEventListener('keydown', dismissEscape);
    };
  }, [open]);

  return <div ref={container} className="relative">
    <button ref={trigger} onClick={() => setOpen(value => !value)} aria-expanded={open} aria-controls="account-panel" aria-label="Mon compte" className="flex items-center gap-2 rounded-xl border border-slate-200/80 bg-white px-3 py-2 text-sm text-slate-800 transition-colors hover:bg-slate-100 focus-visible:outline-2 focus-visible:outline-sky-400">
      <User className="h-4 w-4 text-teal-700" /><span>Mon compte</span><ChevronDown className={`h-4 w-4 transition-transform ${open ? 'rotate-180' : ''}`} />
    </button>
    {open && <section id="account-panel" aria-label="Informations du compte" className="absolute right-0 top-full mt-3 w-72 max-w-[calc(100vw-2rem)] overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-2xl">
      <div className="space-y-4 p-5">
        <div><p className="text-xs text-slate-500">Connecté en tant que</p><p className="mt-1 break-words font-semibold text-slate-900">{user.name}</p><p className="mt-1 text-xs font-medium uppercase tracking-wide text-teal-700">{user.role}</p></div>
        <div className="rounded-xl border border-slate-200/80 bg-white p-3"><p className="text-xs text-slate-500">Espace</p><p className="mt-1 break-words text-sm font-medium text-teal-700">{user.role === 'Administrateur' ? 'Administration du projet' : user.role === 'Cabinet Dentaire' ? 'Dentiste — choix du labo par commande' : tenant?.name || tenant?.id}</p>{tenant?.id && <p className="mt-1 break-words text-xs text-slate-500">Identifiant : {tenant.id}</p>}</div>
      </div>
      <div className="border-t border-slate-200/80 p-2"><button onClick={onLogout} className="flex w-full items-center gap-2 rounded-xl px-3 py-3 text-sm text-red-700 transition-colors hover:bg-red-500/10"><LogOut className="h-4 w-4" />Déconnexion</button></div>
    </section>}
  </div>;
}

function LabPortal({ section, orders, refresh, activeTab, setActiveTab, configTarget, alertState, alertFocus, onAlertSelect }) {
  const patchOrder = async (id, payload) => { await api.patch(`prescriptions/${id}/`, payload); await refresh(); };
  const role = workstation();
  if (section === 'configuration') return <LabBusinessConfiguration key={configTarget?.request || 'configuration'} target={configTarget} />;
  if (section === 'inventory') return <InventoryWorkspace orders={orders} />;
  if (section === 'operations') return role === 'MANAGER' ? <OperationsDashboard /> : <p>Accès responsable requis.</p>;
  if (section === 'orders') return <OrderManagement orders={orders} patchOrder={patchOrder} refresh={refresh} />;
  if (section === 'billing') return ['MANAGER','COMPTABILITE'].includes(role) ? <FinanceDashboard /> : <p>Accès comptabilité requis.</p>;
  return <LabOverview orders={orders} tab={activeTab} setTab={setActiveTab} alertState={alertState} alertFocus={alertFocus} onAlertSelect={onAlertSelect} />;
}
