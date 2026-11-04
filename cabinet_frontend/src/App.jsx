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
  User, FileText, Package, Truck,
  ShieldCheck, Clock, Zap, LogOut,
  Upload, Download, Settings, LayoutDashboard, ChevronDown
} from "lucide-react";
import shadeGuideImg from "./assets/shade-guide.png";
import logoImg from "./assets/logo.png";

export default function App() {
  const [user, setUser] = useState(() => {
    try { return JSON.parse(sessionStorage.getItem('demo_user') || 'null'); } catch { return null; }
  });
  const [orders, setOrders] = useState([]);
  const [labSection, setLabSection] = useState('main');
  const [labTab, setLabTab] = useState('dashboard');
  const [alertFocus, setAlertFocus] = useState(0);
  const [configTarget, setConfigTarget] = useState(null);
  const { tenant, clearTenant } = useTenant();
  const alertState = useLabAlerts(user?.role === 'Laboratoire' ? tenant?.id : null);
  
  const fetchOrders = useCallback(async () => {
    try {
      if (user?.role === 'Administrateur') return;
      const res = user?.role === 'Cabinet Dentaire' ? await platform.get('dentist/orders/') : await api.get("prescriptions/", { params: { include_completed: true } });
      setOrders(res.data);
    } catch (e) {
      console.error("API Error", e);
    }
  }, [user]);

  useEffect(() => {
    if (user) fetchOrders();
  }, [user, fetchOrders]);

  if (!user) return <DemoLogin setUser={setUser} courierLogin={<LoginScreen setUser={setUser} />} />;

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
    <LabPortal key={tenant?.id} section={labSection} activeTab={labTab} setActiveTab={setLabTab} configTarget={configTarget} alertState={alertState} alertFocus={alertFocus} onAlertSelect={alert => {
      setConfigTarget({ section: alert.section, id: alert.resource_id, request: Date.now() });
      setLabSection('configuration');
    }} orders={orders} refresh={fetchOrders} />
    <AlertPopup alerts={alertState.alerts} onOpen={() => { setLabSection('main'); setLabTab('dashboard'); setAlertFocus(value => value + 1); }} />
  </LabAdminLayout>;

  return (
    <div className="flex h-screen bg-[#0d0914] text-white font-sans overflow-hidden">
      {/* Sidebar */}
      <div className="w-64 shrink-0 bg-white/5 border-r border-white/10 p-6 flex flex-col">
        <div className="flex items-center gap-3 mb-10">
          <img src={logoImg} alt="Cabinet 2.0 Logo" className="h-10 w-10 drop-shadow-[0_0_15px_rgba(14,165,233,0.6)] object-contain" />
          <h1 className="text-xl font-bold text-white tracking-wide">Cabinet 2.0</h1>
        </div>
        
        {user.role === 'Laboratoire' && <nav aria-label="Navigation du laboratoire" className="space-y-2">
          {[
            ['main', 'Menu principal', LayoutDashboard],
            ['orders', 'Commandes', Package],
            ['billing', 'Facturation', FileText],
            ['configuration', 'Configuration', Settings],
          ].map(([key, label, Icon]) => <button key={key} onClick={() => { if (key === 'configuration') setConfigTarget(null); setLabSection(key); }} aria-current={labSection === key ? 'page' : undefined} className={`flex w-full items-center gap-3 rounded-xl px-4 py-3 text-sm font-medium transition-colors ${labSection === key ? 'border border-sky-400/20 bg-sky-500/15 text-sky-300' : 'border border-transparent text-slate-400 hover:bg-white/5 hover:text-white'}`}><Icon className="h-5 w-5" />{label}</button>)}
        </nav>}
        {user.role === 'Administrateur' && <nav aria-label="Navigation administration"><div className="flex items-center gap-3 rounded-xl border border-sky-400/20 bg-sky-500/15 px-4 py-3 text-sm font-medium text-sky-300"><LayoutDashboard className="h-5 w-5" />Administration</div></nav>}
      </div>

      {/* Main Content */}
      <div className="min-w-0 flex-1 overflow-y-auto">
        <header className="h-16 border-b border-white/10 bg-white/5 flex items-center justify-between gap-4 px-8 backdrop-blur-md sticky top-0 z-20">
          <div className="flex items-center gap-2 text-sm text-gray-400">
            <ShieldCheck className="w-4 h-4 text-emerald-400" />
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
        
        <main className="p-8 max-w-7xl mx-auto">
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
    <button ref={trigger} onClick={() => setOpen(value => !value)} aria-expanded={open} aria-controls="account-panel" aria-label="Mon compte" className="flex items-center gap-2 rounded-xl border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-200 transition-colors hover:bg-white/10 focus-visible:outline-2 focus-visible:outline-sky-400">
      <User className="h-4 w-4 text-sky-300" /><span>Mon compte</span><ChevronDown className={`h-4 w-4 transition-transform ${open ? 'rotate-180' : ''}`} />
    </button>
    {open && <section id="account-panel" aria-label="Informations du compte" className="absolute right-0 top-full mt-3 w-72 max-w-[calc(100vw-2rem)] overflow-hidden rounded-2xl border border-white/15 bg-[#171321] shadow-2xl">
      <div className="space-y-4 p-5">
        <div><p className="text-xs text-slate-400">Connecté en tant que</p><p className="mt-1 break-words font-semibold text-white">{user.name}</p><p className="mt-1 text-xs font-medium uppercase tracking-wide text-violet-300">{user.role}</p></div>
        <div className="rounded-xl border border-white/10 bg-white/5 p-3"><p className="text-xs text-slate-400">Espace</p><p className="mt-1 break-words text-sm font-medium text-sky-300">{user.role === 'Administrateur' ? 'Administration du projet' : user.role === 'Cabinet Dentaire' ? 'Dentiste — choix du labo par commande' : tenant?.name || tenant?.id}</p>{tenant?.id && <p className="mt-1 break-words text-xs text-slate-400">Identifiant : {tenant.id}</p>}</div>
      </div>
      <div className="border-t border-white/10 p-2"><button onClick={onLogout} className="flex w-full items-center gap-2 rounded-xl px-3 py-3 text-sm text-red-300 transition-colors hover:bg-red-500/10"><LogOut className="h-4 w-4" />Déconnexion</button></div>
    </section>}
  </div>;
}

function LoginScreen({ setUser }) {
  const [name, setName] = useState('');
  const [tenantId, setTenantId] = useState('labo1');
  const { setTenant } = useTenant();
  return <div className="min-h-screen bg-[#0d0914] flex items-center justify-center p-4 text-white">
    <form onSubmit={event => { event.preventDefault(); setTenant(tenantId, tenantId); setUser({ name, role: 'Coursier' }); }} className="w-full max-w-md rounded-3xl border border-white/10 bg-white/5 p-8 space-y-5">
      <h1 className="text-2xl font-semibold">Accès livreur</h1>
      <label className="block text-sm text-slate-300">Votre nom<input aria-label="Nom du livreur" required value={name} onChange={event => setName(event.target.value)} className="mt-2 w-full rounded-xl border border-white/15 bg-black/30 p-3" /></label>
      <label className="block text-sm text-slate-300">Identifiant du laboratoire<input aria-label="Laboratoire du livreur" required pattern="[a-z0-9][a-z0-9-]*" value={tenantId} onChange={event => setTenantId(event.target.value)} className="mt-2 w-full rounded-xl border border-white/15 bg-black/30 p-3" /></label>
      <button className="w-full rounded-xl bg-violet-600 p-3">Accéder au portail livreur</button>
    </form>
  </div>;
}

function DentistPortal({ user, orders, refresh }) {
  const [tab, setTab] = useState("new");
  
  const myOrders = orders;

  return (
    <div className="space-y-6">
      <div className="flex gap-4 border-b border-white/10 pb-4">
        <button 
          onClick={() => setTab("new")}
          className={`px-4 py-2 rounded-lg font-medium transition-colors ${tab === "new" ? "bg-white/10 text-white" : "text-gray-400 hover:text-white"}`}
        >
          Nouvelle Fiche
        </button>
        <button 
          onClick={() => setTab("list")}
          className={`px-4 py-2 rounded-lg font-medium transition-colors ${tab === "list" ? "bg-white/10 text-white" : "text-gray-400 hover:text-white"}`}
        >
          Mes Commandes ({myOrders.length})
        </button>
      </div>

      {tab === "new" ? <DentistForm user={user} onSuccess={() => { refresh(); setTab("list"); }} /> : <DentistList orders={myOrders} />}
    </div>
  );
}

const getToothWidth = (num) => {
  const d = num % 10;
  if (d >= 6) return "w-8";
  if (d >= 3) return "w-6";
  return "w-5";
};

const getTopMargin = (num) => {
  const d = num % 10;
  if (d <= 2) return "mt-4";
  if (d <= 5) return "mt-2";
  return "mt-0";
};

const getBottomMargin = (num) => {
  const d = num % 10;
  if (d <= 2) return "mb-4";
  if (d <= 5) return "mb-2";
  return "mb-0";
};

const ToothSvg = ({ isTop, isActive, className }) => (
  <svg 
    viewBox="0 0 24 24" 
    className={`${className} transition-all duration-300 ${isActive ? 'fill-sky-500 stroke-sky-300 drop-shadow-[0_0_10px_rgba(14,165,233,0.8)]' : 'fill-white/5 stroke-white/30 group-hover:stroke-sky-400 group-hover:fill-sky-900/40'}`}
    style={{ transform: isTop ? 'rotate(180deg)' : '' }}
  >
    <path 
      d="M4 6c0-2.5 2-4 4.5-4C10 2 11 3 12 4c1-1 2-2 3.5-2C18 2 20 3.5 20 6c0 3-1.5 5.5-3 7.5L16 20c-.5 1-2 1-2.5 0L12 16l-1.5 4c-.5 1-2 1-2.5 0L6 13.5C4.5 11.5 4 9 4 6z" 
      strokeWidth="1.5"
    />
  </svg>
);

function DentistForm({ user, onSuccess }) {
  const [laboratories, setLaboratories] = useState([]);
  const [laboratoryId, setLaboratoryId] = useState('');
  const [labError, setLabError] = useState('');
  useEffect(() => {
    let cancelled = false;
    platform.get('laboratories/').then(({ data }) => { if (!cancelled) setLaboratories(data); }).catch(() => { if (!cancelled) setLabError('Impossible de charger les laboratoires. Rechargez la page.'); });
    return () => { cancelled = true; };
  }, []);
  const [formData, setFormData] = useState({
    patient_ref: "", tooth_number: "", shade: "A1", material: "Zircone",
    is_fast_track: false, disinfected: false,
    impression_type: "PHYSIQUE", stl_file_name: ""
  });
  const [loading, setLoading] = useState(false);

  const prices = { 
    "Zircone": 1200, 
    "E-Max": 1500, 
    "Céramo-Métal": 800, 
    "100% Métal": 500, 
    "Provisoire Résine": 200 
  };
  const basePrice = prices[formData.material] || 0;
  const totalPrice = formData.is_fast_track ? Math.round(basePrice * 1.30) : basePrice;
  const fastTrackSurcharge = totalPrice - basePrice;

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    
    const payload = {
      patient_ref: formData.patient_ref,
      tooth_number: parseInt(formData.tooth_number, 10) || formData.tooth_number,
      shade: formData.shade,
      material: formData.material,
      impression_type: formData.impression_type,
      stl_file_name: formData.impression_type === "NUMERIQUE" ? formData.stl_file_name : "",
      is_fast_track: formData.is_fast_track,
      disinfected: formData.disinfected,
      dentist_name: user.name,
      total_price: totalPrice,
    };

    try {
      await platform.post("dentist/orders/", { ...payload, laboratory_id: laboratoryId });
      onSuccess();
    } catch (e) {
      console.error(e);
      alert("Erreur lors de la soumission");
    }
    setLoading(false);
  };

  return (
    <div className="grid grid-cols-3 gap-8">
      <div className="col-span-2 bg-white/5 border border-white/10 rounded-2xl p-6">
        <h2 className="text-xl font-semibold mb-6 flex items-center gap-2">
          <FileText className="text-violet-400" /> Prescrire
        </h2>
        <form id="dentistForm" onSubmit={handleSubmit} className="grid grid-cols-2 gap-6">
          <div><label htmlFor="dentist-laboratory" className="mb-1 block text-sm text-gray-400">Laboratoire destinataire *</label><select id="dentist-laboratory" required value={laboratoryId} onChange={event => setLaboratoryId(event.target.value)} className="w-full rounded-lg border border-white/10 bg-[#171321] p-3 text-white"><option value="">Choisir un laboratoire</option>{laboratories.map(lab => <option key={lab.identifier} value={lab.identifier}>{lab.name}</option>)}</select>{labError && <p role="alert" className="mt-1 text-xs text-red-300">{labError}</p>}</div>
          <div>
            <label className="block text-sm text-gray-400 mb-1">Réf. Patient (Anonyme)</label>
            <input type="text" required className="w-full bg-black/40 border border-white/10 rounded-lg p-3" 
              value={formData.patient_ref} onChange={e => setFormData({...formData, patient_ref: e.target.value})} placeholder="PAT-XXXX" />
          </div>
          <div className="col-span-2 bg-black/20 border border-white/5 p-6 rounded-xl mb-2 mt-2">
            <label className="block text-sm font-medium text-slate-300 mb-8 text-center uppercase tracking-widest">
              Odontogramme
            </label>
            <div className="flex flex-col gap-8 items-center overflow-x-auto pb-4">
              {/* Upper Arch */}
              <div className="flex gap-4 items-start">
                {/* Q1 */}
                <div className="flex gap-1 items-start">
                  {[18, 17, 16, 15, 14, 13, 12, 11].map((tooth) => {
                    const isActive = formData.tooth_number === tooth.toString();
                    return (
                      <button key={tooth} type="button" onClick={() => setFormData({ ...formData, tooth_number: tooth.toString() })} className={`group flex flex-col items-center gap-2 ${getTopMargin(tooth)} transition-all`}>
                        <div className="text-xs font-mono transition-colors text-slate-400 group-hover:text-sky-300">
                          {isActive ? <span className="text-white font-bold">{tooth}</span> : tooth}
                        </div>
                        <ToothSvg isTop={true} isActive={isActive} className={getToothWidth(tooth)} />
                      </button>
                    );
                  })}
                </div>
                {/* Midline */}
                <div className="w-px h-16 bg-white/10 mx-2"></div>
                {/* Q2 */}
                <div className="flex gap-1 items-start">
                  {[21, 22, 23, 24, 25, 26, 27, 28].map((tooth) => {
                    const isActive = formData.tooth_number === tooth.toString();
                    return (
                      <button key={tooth} type="button" onClick={() => setFormData({ ...formData, tooth_number: tooth.toString() })} className={`group flex flex-col items-center gap-2 ${getTopMargin(tooth)} transition-all`}>
                        <div className="text-xs font-mono transition-colors text-slate-400 group-hover:text-sky-300">
                          {isActive ? <span className="text-white font-bold">{tooth}</span> : tooth}
                        </div>
                        <ToothSvg isTop={true} isActive={isActive} className={getToothWidth(tooth)} />
                      </button>
                    );
                  })}
                </div>
              </div>

              {/* Lower Arch */}
              <div className="flex gap-4 items-end">
                {/* Q4 */}
                <div className="flex gap-1 items-end">
                  {[48, 47, 46, 45, 44, 43, 42, 41].map((tooth) => {
                    const isActive = formData.tooth_number === tooth.toString();
                    return (
                      <button key={tooth} type="button" onClick={() => setFormData({ ...formData, tooth_number: tooth.toString() })} className={`group flex flex-col items-center gap-2 ${getBottomMargin(tooth)} transition-all`}>
                        <ToothSvg isTop={false} isActive={isActive} className={getToothWidth(tooth)} />
                        <div className="text-xs font-mono transition-colors text-slate-400 group-hover:text-sky-300">
                          {isActive ? <span className="text-white font-bold">{tooth}</span> : tooth}
                        </div>
                      </button>
                    );
                  })}
                </div>
                {/* Midline */}
                <div className="w-px h-16 bg-white/10 mx-2"></div>
                {/* Q3 */}
                <div className="flex gap-1 items-end">
                  {[31, 32, 33, 34, 35, 36, 37, 38].map((tooth) => {
                    const isActive = formData.tooth_number === tooth.toString();
                    return (
                      <button key={tooth} type="button" onClick={() => setFormData({ ...formData, tooth_number: tooth.toString() })} className={`group flex flex-col items-center gap-2 ${getBottomMargin(tooth)} transition-all`}>
                        <ToothSvg isTop={false} isActive={isActive} className={getToothWidth(tooth)} />
                        <div className="text-xs font-mono transition-colors text-slate-400 group-hover:text-sky-300">
                          {isActive ? <span className="text-white font-bold">{tooth}</span> : tooth}
                        </div>
                      </button>
                    );
                  })}
                </div>
              </div>
            </div>
            <div className="mt-6 text-center">
              <span className="text-slate-400 text-sm mr-2">Dent sélectionnée :</span>
              <span className="text-sky-400 font-bold font-mono tracking-wider">{formData.tooth_number || 'Aucune'}</span>
            </div>
          </div>

          {/* ── Impression Type Toggle ── */}
          <div className="col-span-2">
            <label className="block text-sm text-gray-400 mb-2">Type d'Empreinte</label>
            <div className="grid grid-cols-2 gap-3">
              <button type="button"
                onClick={() => setFormData({...formData, impression_type: "PHYSIQUE", stl_file_name: ""})}
                className={`flex items-center justify-center gap-2 p-3 rounded-xl border text-sm font-medium transition-all ${
                  formData.impression_type === "PHYSIQUE"
                    ? "ring-2 ring-sky-500 bg-sky-900/30 border-sky-500 text-white"
                    : "bg-black/40 border-white/10 text-gray-400 hover:border-white/30"
                }`}
              >
                📦 Empreinte Physique (Collecte Coursier)
              </button>
              <button type="button"
                onClick={() => setFormData({...formData, impression_type: "NUMERIQUE"})}
                className={`flex items-center justify-center gap-2 p-3 rounded-xl border text-sm font-medium transition-all ${
                  formData.impression_type === "NUMERIQUE"
                    ? "ring-2 ring-violet-500 bg-violet-900/30 border-violet-500 text-white"
                    : "bg-black/40 border-white/10 text-gray-400 hover:border-white/30"
                }`}
              >
                💻 Empreinte Numérique (Fichier .STL)
              </button>
            </div>
          </div>

          {/* ── STL File Drop Zone (shown only when NUMERIQUE) ── */}
          {formData.impression_type === "NUMERIQUE" && (
            <div className="col-span-2">
              <div className="bg-white/5 border-2 border-dashed border-violet-500/40 rounded-xl p-6 text-center hover:border-violet-400/60 transition-colors">
                <Upload className="w-8 h-8 text-violet-400 mx-auto mb-2" />
                <p className="text-sm text-gray-300 mb-3">Glissez votre fichier .STL / .PLY ou cliquez pour sélectionner</p>
                <input
                  type="file"
                  accept=".stl,.ply"
                  onChange={(e) => {
                    const file = e.target.files[0];
                    if (file) setFormData({...formData, stl_file_name: file.name});
                  }}
                  className="hidden"
                  id="stl-upload"
                />
                <label htmlFor="stl-upload" className="cursor-pointer inline-flex items-center gap-2 bg-violet-600 hover:bg-violet-500 text-white text-sm font-medium px-4 py-2 rounded-lg transition-colors">
                  <Upload className="w-4 h-4" /> Parcourir
                </label>
                {formData.stl_file_name && (
                  <div className="mt-3 inline-flex items-center gap-2 bg-violet-500/20 border border-violet-500/30 text-violet-300 text-xs font-mono px-3 py-1.5 rounded-lg">
                    📄 {formData.stl_file_name}
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Clinical Lightbox */}
          <div className="col-span-2 bg-white/5 border border-white/10 rounded-xl p-4 mb-4">
            <img src={shadeGuideImg} alt="Guide de Teintes VITA" className="w-full object-contain rounded-lg bg-white p-2" />
            <p className="text-xs text-slate-400 mt-2 text-center">Guide VITA Classical - Référence Visuelle</p>
          </div>

          <div>
            <label className="block text-sm text-gray-400 mb-1">Sélectionner la Teinte</label>
            <select className="w-full bg-black/40 border border-white/10 rounded-lg p-3 text-white"
              value={formData.shade} onChange={e => setFormData({...formData, shade: e.target.value})}>
              <optgroup label="Rouges-Bruns (A)">
                <option value="A1">A1</option>
                <option value="A2">A2</option>
                <option value="A3">A3</option>
                <option value="A3.5">A3.5</option>
                <option value="A4">A4</option>
              </optgroup>
              <optgroup label="Jaunes-Rouges (B)">
                <option value="B1">B1</option>
                <option value="B2">B2</option>
                <option value="B3">B3</option>
                <option value="B4">B4</option>
              </optgroup>
              <optgroup label="Gris (C)">
                <option value="C1">C1</option>
                <option value="C2">C2</option>
                <option value="C3">C3</option>
                <option value="C4">C4</option>
              </optgroup>
              <optgroup label="Gris-Rouges (D)">
                <option value="D2">D2</option>
                <option value="D3">D3</option>
                <option value="D4">D4</option>
              </optgroup>
            </select>
          </div>
          <div className="col-span-2">
            <label className="block text-sm text-gray-400 mb-2">Choix du Matériau</label>
            <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
              {[
                { name: "Zircone", price: 1200 },
                { name: "E-Max", price: 1500 },
                { name: "Céramo-Métal", price: 800 },
                { name: "100% Métal", price: 500 },
                { name: "Provisoire Résine", price: 200 }
              ].map(mat => (
                <div 
                  key={mat.name}
                  onClick={() => setFormData({...formData, material: mat.name})}
                  className={`flex flex-col items-center justify-center p-4 rounded-xl cursor-pointer transition-all text-center border ${
                    formData.material === mat.name 
                      ? "ring-2 ring-sky-500 bg-sky-900/30 border-sky-500" 
                      : "bg-black/40 border-white/10 hover:border-white/30"
                  }`}
                >
                  <span className="text-white font-semibold mb-1">{mat.name}</span>
                  <span className="text-sm text-sky-400">{mat.price} MAD</span>
                </div>
              ))}
            </div>
          </div>
          
          {/* ── Urgence 30% Toggle ── */}
          <div className="col-span-2 border border-white/10 rounded-xl p-4 flex items-center justify-between bg-black/20">
            <div>
              <div className="font-medium flex items-center gap-2"><Zap className="w-4 h-4 text-amber-400" /> Urgence 24h-48h</div>
              <div className="text-sm text-gray-400">Majoration +30% ({fastTrackSurcharge > 0 ? `+${fastTrackSurcharge} MAD` : "Désactivé"})</div>
            </div>
            <label className="relative inline-flex items-center cursor-pointer">
              <input type="checkbox" className="sr-only peer" checked={formData.is_fast_track} onChange={e => setFormData({...formData, is_fast_track: e.target.checked})} />
              <div className="w-11 h-6 bg-gray-700 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-violet-500"></div>
            </label>
          </div>

          <div className="col-span-2 border border-emerald-500/30 bg-emerald-500/5 rounded-xl p-4 flex items-start gap-3">
            <input type="checkbox" required id="lock" className="mt-1 w-4 h-4 accent-emerald-500" 
              checked={formData.disinfected} onChange={e => setFormData({...formData, disinfected: e.target.checked})} />
            <label htmlFor="lock" className="cursor-pointer">
              <div className="font-medium text-emerald-400">Verrou Sanitaire Obligatoire</div>
              <div className="text-sm text-gray-400">Je confirme que les empreintes ont été désinfectées selon le protocole.</div>
            </label>
          </div>
        </form>
      </div>

      {/* ── Devis Panel ── */}
      <div className="col-span-1">
        <div className="bg-white/5 border border-white/10 rounded-2xl p-6 sticky top-24">
          <h3 className="text-lg font-semibold mb-4 text-gray-200">Devis Estimatif</h3>
          <div className="space-y-3 mb-6">
            <div className="flex justify-between text-gray-400"><span>Base ({formData.material})</span><span>{basePrice} MAD</span></div>
            {formData.is_fast_track && <div className="flex justify-between text-amber-400"><span>⚡ Urgence +30%</span><span>+{fastTrackSurcharge} MAD</span></div>}
            <div className="border-t border-white/10 pt-3 flex justify-between font-bold text-lg text-white">
              <span>Total</span><span>{totalPrice} MAD</span>
            </div>
            <div className="text-xs text-gray-500 text-right">
              {formData.is_fast_track ? "Délai : 24h-48h" : "Délai : 3 à 5 jours"}
            </div>
          </div>
          {formData.impression_type === "NUMERIQUE" && formData.stl_file_name && (
            <div className="mb-4 text-xs text-violet-300 bg-violet-500/10 border border-violet-500/20 p-2 rounded-lg flex items-center gap-2">
              💻 Fichier: {formData.stl_file_name}
            </div>
          )}
          <button form="dentistForm" type="submit" disabled={loading} className="w-full bg-violet-600 hover:bg-violet-700 text-white font-semibold py-3 rounded-xl transition-colors shadow-lg disabled:opacity-50">
            {loading ? "Envoi..." : "Envoyer au Labo"}
          </button>
        </div>
      </div>
    </div>
  );
}

function DentistList({ orders }) {
  const statusColors = {
    ATTENTE_RAMASSAGE: "bg-amber-500/20 text-amber-300 border-amber-500/30",
    EN_ROUTE_LABO: "bg-blue-500/20 text-blue-300 border-blue-500/30",
    A_CONFIRMER: "bg-gray-500/20 text-gray-300 border-gray-500/30",
    SALLE_CAO: "bg-blue-500/20 text-blue-300 border-blue-500/30",
    USINAGE_CNC: "bg-indigo-500/20 text-indigo-300 border-indigo-500/30",
    FRITTAGE_9H: "bg-orange-500/20 text-orange-300 border-orange-500/30",
    CONTROLE_QUALITE: "bg-cyan-500/20 text-cyan-300 border-cyan-500/30",
    PRET_EXPEDITION: "bg-amber-500/20 text-amber-300 border-amber-500/30",
    EN_ROUTE_CABINET: "bg-purple-500/20 text-purple-300 border-purple-500/30",
    EN_ROUTE: "bg-purple-500/20 text-purple-300 border-purple-500/30",
    LIVRE: "bg-emerald-500/20 text-emerald-300 border-emerald-500/30"
  };

  const statusLabels = {
    ATTENTE_RAMASSAGE: "Attente Ramassage",
    EN_ROUTE_LABO: "En Route Labo",
    A_CONFIRMER: "Réception",
    SALLE_CAO: "CAO",
    USINAGE_CNC: "Usinage",
    FRITTAGE_9H: "Frittage",
    CONTROLE_QUALITE: "Contrôle",
    PRET_EXPEDITION: "Prêt Expédition",
    EN_ROUTE_CABINET: "En Livraison",
    EN_ROUTE: "En Route",
    LIVRE: "Livré"
  };

  if (orders.length === 0) return <div className="text-gray-400">Aucune commande.</div>;

  return (
    <div className="grid gap-4">
      {orders.map(o => (
        <div key={o.id} className="bg-white/5 border border-white/10 rounded-xl p-5 flex items-center justify-between">
          <div>
            <div className="flex items-center gap-3 mb-1">
              <span className="font-bold text-lg">{o.patient_ref}</span>
              <span className="bg-black/50 px-2 py-1 rounded text-xs text-gray-400">Dent {o.tooth_number}</span>
              {o.is_fast_track && <span className="bg-amber-500/20 text-amber-400 px-2 py-1 rounded flex items-center gap-1 text-xs font-medium"><Zap className="w-3 h-3"/> Urgence</span>}
              {o.impression_type === "NUMERIQUE" && <span className="bg-violet-500/20 text-violet-300 px-2 py-1 rounded text-xs font-medium">💻 .STL</span>}
            </div>
            <div className="text-sm text-gray-400">{o.material} - Teinte {o.shade}</div>
            {o.laboratory_name && <p className="mt-1 text-xs text-sky-300">Laboratoire : {o.laboratory_name}</p>}
          </div>
          <div className="text-right">
            <div className={`inline-flex px-3 py-1 rounded-full text-xs font-semibold border ${statusColors[o.status] || "bg-gray-500/20 text-gray-300 border-gray-500/30"}`}>
              {o.status_label || statusLabels[o.status] || o.status}
            </div>
            {o.delivery_date && <div className="text-xs text-gray-400 mt-2 flex items-center justify-end gap-1"><Clock className="w-3 h-3"/> Prévu: {o.delivery_date}</div>}
          </div>
        </div>
      ))}
    </div>
  );
}

// ════════════════════════════════════════
//  LAB PORTAL
// ════════════════════════════════════════

function LabPortal({ section, orders, refresh, activeTab, setActiveTab, configTarget, alertState, alertFocus, onAlertSelect }) {
  const patchOrder = async (id, payload) => {
    await api.patch(`prescriptions/${id}/`, payload);
    await refresh();
  };
  if (section === 'configuration') return <LabBusinessConfiguration key={configTarget?.request || 'configuration'} target={configTarget} />;
  if (section === 'orders') return <OrderManagement orders={orders} patchOrder={patchOrder} />;
  if (section === 'billing') return <div className="space-y-6"><div><p className="text-xs uppercase tracking-widest text-sky-400">Gestion</p><h1 className="mt-2 text-2xl font-semibold">Facturation</h1></div><BillingPipeline orders={orders} patchOrder={patchOrder} /></div>;
  return <LabOverview orders={orders} tab={activeTab} setTab={setActiveTab} alertState={alertState} alertFocus={alertFocus} onAlertSelect={onAlertSelect} />;
}

const FINANCE_CHAIN = ["COMMANDE", "SITUATION", "FACTURE"];

function BillingPipeline({ orders, patchOrder }) {
  const [draggedFinanceOrder, setDraggedFinanceOrder] = useState(null);

  const commandeOrders  = orders.filter(o => (o.billing_stage || "COMMANDE") === "COMMANDE");
  const situationOrders = orders.filter(o => o.billing_stage === "SITUATION");
  const factureOrders   = orders.filter(o => o.billing_stage === "FACTURE");

  const situationTotal = situationOrders.reduce((sum, o) => sum + (o.total_price || 0), 0);

  const currentStage = draggedFinanceOrder ? (draggedFinanceOrder.billing_stage || "COMMANDE") : null;
  const nextValidFinance = currentStage
    ? FINANCE_CHAIN[FINANCE_CHAIN.indexOf(currentStage) + 1]
    : null;

  const handleDrop = (e, targetStage) => {
    e.preventDefault();
    if (!draggedFinanceOrder) return;
    const currentIndex = FINANCE_CHAIN.indexOf(draggedFinanceOrder.billing_stage || "COMMANDE");
    const targetIndex = FINANCE_CHAIN.indexOf(targetStage);

    // ONLY advance if target stage is exactly the next step
    if (targetIndex === currentIndex + 1) {
      patchOrder(draggedFinanceOrder.id, { billing_stage: targetStage });
    }
    setDraggedFinanceOrder(null);
  };

  const handleDragOver = (e) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = "move";
  };

  const bulkPatch = async (ids, payload) => {
    for (const id of ids) {
      await api.patch(`prescriptions/${id}/`, payload);
    }
    patchOrder(ids[0], {});
  };

  return (
    <div className="space-y-8">
      {/* ── Step 1: Commandes (Bons de Livraison) ── */}
      <div
        onDragOver={handleDragOver}
        onDrop={(e) => handleDrop(e, "COMMANDE")}
        className={`border rounded-2xl p-6 transition-all duration-200 ${
          nextValidFinance === "COMMANDE"
            ? "ring-2 ring-emerald-500/50 bg-emerald-900/10 border-emerald-500/40"
            : "bg-black/20 border-white/10"
        }`}
      >
        <div className="flex items-center justify-between mb-4">
          <h3 className="font-semibold text-white flex items-center gap-2">
            <span className="bg-sky-500/20 text-sky-400 text-xs font-bold px-2 py-0.5 rounded">1</span>
            Commandes (Bons de Livraison)
          </h3>
          <span className="text-xs text-slate-500">{commandeOrders.length} commande(s)</span>
        </div>
        {commandeOrders.length === 0 && <div className="text-sm text-slate-500 text-center py-3">Aucune commande en attente de situation.</div>}
        <div className="space-y-3">
          {commandeOrders.map(o => (
            <div
              key={o.id}
              draggable={true}
              onDragStart={(e) => {
                e.dataTransfer.setData("text/plain", o.id);
                setDraggedFinanceOrder(o);
              }}
              onDragEnd={() => setDraggedFinanceOrder(null)}
              className={`bg-white/5 border border-white/10 rounded-xl p-4 flex items-center justify-between cursor-grab active:cursor-grabbing transition-all ${
                draggedFinanceOrder?.id === o.id ? "opacity-30 scale-95 border-emerald-500/50" : "opacity-100 hover:border-white/20"
              }`}
            >
              <div>
                <div className="flex items-center gap-3">
                  <span className="font-bold">{o.patient_ref}</span>
                  <span className="text-xs text-gray-400">{o.dentist_name}</span>
                  <span className="text-xs text-sky-400 font-mono">{o.total_price || 0} MAD</span>
                </div>
                <div className="text-xs text-gray-500 mt-1">{o.material} — Dent {o.tooth_number}</div>
              </div>
              <div className="flex items-center gap-3">
                <span className="text-[10px] text-slate-500 font-mono">⠿ Glisser vers Étape 2</span>
                <button
                  onClick={() => patchOrder(o.id, { billing_stage: "SITUATION" })}
                  className="bg-sky-600/20 hover:bg-sky-600/40 text-sky-300 border border-sky-500/30 text-xs font-medium px-3 py-1.5 rounded-lg transition-colors"
                >
                  Inclure dans la Situation ➔
                </button>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* ── Step 2: État de Situation (Relevé Mensuel) ── */}
      <div
        onDragOver={handleDragOver}
        onDrop={(e) => handleDrop(e, "SITUATION")}
        className={`border rounded-2xl p-6 transition-all duration-200 ${
          nextValidFinance === "SITUATION"
            ? "ring-2 ring-emerald-500/50 bg-emerald-900/10 border-emerald-500/40"
            : "bg-black/20 border-amber-500/20"
        }`}
      >
        <div className="flex items-center justify-between mb-4">
          <h3 className="font-semibold text-white flex items-center gap-2">
            <span className="bg-amber-500/20 text-amber-400 text-xs font-bold px-2 py-0.5 rounded">2</span>
            État de Situation (Relevé Mensuel)
            {nextValidFinance === "SITUATION" && (
              <span className="text-[10px] bg-emerald-500/20 text-emerald-400 px-2 py-0.5 rounded-full border border-emerald-500/30 animate-pulse">
                Zone de Dépôt Valide
              </span>
            )}
          </h3>
          <div className="flex items-center gap-4">
            <span className="text-xs text-slate-500">{situationOrders.length} commande(s)</span>
            <span className="text-sm font-bold text-amber-400 font-mono">{situationTotal.toLocaleString()} MAD</span>
          </div>
        </div>
        {situationOrders.length === 0 && <div className="text-sm text-slate-500 text-center py-3">Aucune commande en situation. Glissez une commande ici.</div>}
        <div className="space-y-3 mb-4">
          {situationOrders.map(o => (
            <div
              key={o.id}
              draggable={true}
              onDragStart={(e) => {
                e.dataTransfer.setData("text/plain", o.id);
                setDraggedFinanceOrder(o);
              }}
              onDragEnd={() => setDraggedFinanceOrder(null)}
              className={`bg-white/5 border border-white/10 rounded-xl p-4 flex items-center justify-between cursor-grab active:cursor-grabbing transition-all ${
                draggedFinanceOrder?.id === o.id ? "opacity-30 scale-95 border-emerald-500/50" : "opacity-100 hover:border-white/20"
              }`}
            >
              <div>
                <div className="flex items-center gap-3">
                  <span className="font-bold">{o.patient_ref}</span>
                  <span className="text-xs text-gray-400">{o.dentist_name}</span>
                  <span className="text-xs text-amber-400 font-mono">{o.total_price || 0} MAD</span>
                </div>
                <div className="text-xs text-gray-500 mt-1">{o.material} — Dent {o.tooth_number}</div>
              </div>
              <div className="flex items-center gap-3">
                <span className="text-[10px] text-slate-500 font-mono">⠿ Glisser vers Étape 3</span>
                <span className="bg-amber-500/20 text-amber-300 px-2 py-1 rounded text-xs font-semibold">En Situation</span>
              </div>
            </div>
          ))}
        </div>
        {situationOrders.length > 0 && (
          <div className="border-t border-white/10 pt-4 flex items-center justify-between">
            <div>
              <div className="text-sm text-slate-300">Total à facturer</div>
              <div className="text-2xl font-bold text-amber-400 font-mono">{situationTotal.toLocaleString()} MAD</div>
            </div>
            <button
              onClick={() => bulkPatch(situationOrders.map(o => o.id), { billing_stage: "FACTURE" })}
              className="bg-amber-600 hover:bg-amber-500 text-white font-semibold px-5 py-2.5 rounded-xl transition-colors shadow-lg"
            >
              Valider Situation & Émettre Facture ➔
            </button>
          </div>
        )}
      </div>

      {/* ── Step 3: Facturation Définitive ── */}
      <div
        onDragOver={handleDragOver}
        onDrop={(e) => handleDrop(e, "FACTURE")}
        className={`border rounded-2xl p-6 transition-all duration-200 ${
          nextValidFinance === "FACTURE"
            ? "ring-2 ring-emerald-500/50 bg-emerald-900/10 border-emerald-500/40"
            : "bg-black/20 border-emerald-500/20"
        }`}
      >
        <div className="flex items-center justify-between mb-4">
          <h3 className="font-semibold text-white flex items-center gap-2">
            <span className="bg-emerald-500/20 text-emerald-400 text-xs font-bold px-2 py-0.5 rounded">3</span>
            Facturation Définitive
            {nextValidFinance === "FACTURE" && (
              <span className="text-[10px] bg-emerald-500/20 text-emerald-400 px-2 py-0.5 rounded-full border border-emerald-500/30 animate-pulse">
                Zone de Dépôt Valide
              </span>
            )}
          </h3>
          <span className="text-xs text-slate-500">{factureOrders.length} facture(s)</span>
        </div>
        {factureOrders.length === 0 && <div className="text-sm text-slate-500 text-center py-3">Aucune facture émise. Glissez une commande validée ici.</div>}
        <div className="space-y-3">
          {factureOrders.map(o => (
            <div key={o.id} className="bg-white/5 border border-emerald-500/20 rounded-xl p-4 flex items-center justify-between">
              <div>
                <div className="flex items-center gap-3">
                  <span className="font-bold">{o.patient_ref}</span>
                  <span className="text-xs text-gray-400">{o.dentist_name}</span>
                  <span className="text-xs text-emerald-400 font-mono">{o.total_price || 0} MAD</span>
                </div>
                <div className="text-xs text-gray-500 mt-1">{o.material} — Dent {o.tooth_number}</div>
              </div>
              <div className="flex items-center gap-3">
                <span className="bg-emerald-500/20 text-emerald-400 px-2 py-1 rounded text-xs font-semibold">✅ Facturé</span>
                <button className="bg-white/10 hover:bg-white/20 text-white px-3 py-1.5 rounded-lg text-xs transition-colors flex items-center gap-1">
                  <Download className="w-3 h-3" /> 📄 Télécharger Facture PDF
                </button>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

// ════════════════════════════════════════
//  COURIER PORTAL (Two-Way Routing)
// ════════════════════════════════════════

function CourierPortal({ orders, refresh }) {
  const [verifyingId, setVerifyingId] = useState(null);
  const [pin, setPin] = useState("");

  const patchOrder = async (id, payload) => {
    await api.patch(`prescriptions/${id}/`, payload);
    await refresh();
  };

  const handleConfirmDelivery = (id) => {
    if (pin.length > 0) {
      patchOrder(id, { status: "LIVRE" });
      setVerifyingId(null);
      setPin("");
    }
  };

  // Phase 1: Pickup physical impressions from dental cabinets
  const phase1Orders = orders.filter(
    o => o.status === "ATTENTE_RAMASSAGE" || o.status === "EN_ROUTE_LABO"
  );

  // Phase 2: Deliver completed prosthetics to dental cabinets
  const phase2Orders = orders.filter(
    o => o.status === "PRET_EXPEDITION" || o.status === "EN_ROUTE_CABINET"
  );

  return (
    <div className="max-w-2xl mx-auto bg-black/40 border border-white/10 p-6 rounded-3xl min-h-[800px] shadow-2xl relative overflow-hidden space-y-8">
      {/* Header */}
      <div className="border-b border-white/10 pb-5">
        <h2 className="text-xl font-bold text-white mb-2">Interface Logistique Coursier</h2>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2 bg-emerald-500/10 border border-emerald-500/20 px-3 py-1.5 rounded-full">
            <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></div>
            <span className="text-xs font-semibold text-emerald-400">MedLogistics Two-Way Connecté</span>
          </div>
          <div className="text-xs text-slate-400">
            {phase1Orders.length} ramassage(s) • {phase2Orders.length} livraison(s)
          </div>
        </div>
      </div>

      {/* ════ SECTION A: PHASE 1 - RAMASSAGES AU CABINET ════ */}
      <div className="bg-black/30 border border-amber-500/30 rounded-2xl p-5 space-y-4">
        <div className="flex items-center justify-between border-b border-white/10 pb-3">
          <h3 className="text-base font-bold text-amber-300 flex items-center gap-2">
            <Package className="w-5 h-5 text-amber-400" />
            Phase 1 : Ramassages au Cabinet
          </h3>
          <span className="bg-amber-500/20 text-amber-300 text-xs px-2.5 py-0.5 rounded-full font-semibold">
            {phase1Orders.length}
          </span>
        </div>

        <div className="space-y-4">
          {phase1Orders.map(o => (
            <div key={o.id} className="bg-white/5 border border-white/10 rounded-2xl p-4">
              <div className="flex justify-between items-center mb-3">
                <span className="font-mono text-sm font-bold text-white">REF: {o.patient_ref}</span>
                <span className={`text-[10px] px-2.5 py-0.5 rounded font-bold uppercase ${
                  o.status === "ATTENTE_RAMASSAGE"
                    ? "bg-amber-500/20 text-amber-300 border border-amber-500/30"
                    : "bg-blue-500/20 text-blue-300 border border-blue-500/30 animate-pulse"
                }`}>
                  {o.status === "ATTENTE_RAMASSAGE" ? "📦 En Attente de Ramassage" : "🚚 En Route vers Labo"}
                </span>
              </div>

              {/* Two-Way Routing: Cabinet -> Labo */}
              <div className="relative pl-6 mb-4 space-y-3">
                <div className="absolute left-[11px] top-2 bottom-2 w-0.5 border-l-2 border-dashed border-amber-500/30"></div>
                <div className="relative">
                  <div className="absolute -left-6 top-0.5 text-base">🏥</div>
                  <div className="text-sm font-medium text-amber-300">Point A: {o.dentist_name}</div>
                  <div className="text-xs text-slate-400">Cabinet de départ — Empreinte Physique</div>
                </div>
                <div className="relative">
                  <div className="absolute -left-6 top-0.5 text-base">📍</div>
                  <div className="text-sm font-medium text-white">Point B: Laboratoire CFAO</div>
                  <div className="text-xs text-slate-400">Destination — Réception & Modèle</div>
                </div>
              </div>

              {/* Action Buttons */}
              <div>
                {o.status === "ATTENTE_RAMASSAGE" && (
                  <button
                    onClick={() => patchOrder(o.id, { status: "EN_ROUTE_LABO" })}
                    className="w-full bg-amber-600 hover:bg-amber-500 text-white rounded-xl py-3 flex justify-center items-center gap-2 font-semibold text-xs transition-colors shadow-lg"
                  >
                    📦 Scanner & Récupérer
                  </button>
                )}
                {o.status === "EN_ROUTE_LABO" && (
                  <button
                    onClick={() => patchOrder(o.id, { status: "A_CONFIRMER" })}
                    className="w-full bg-blue-600 hover:bg-blue-500 text-white rounded-xl py-3 flex justify-center items-center gap-2 font-semibold text-xs transition-colors shadow-lg"
                  >
                    🏭 Déposer au Labo
                  </button>
                )}
              </div>
            </div>
          ))}
          {phase1Orders.length === 0 && (
            <div className="text-sm text-center text-slate-500 py-4">
              Aucun ramassage en attente.
            </div>
          )}
        </div>
      </div>

      {/* ════ SECTION B: PHASE 2 - LIVRAISONS AU CABINET ════ */}
      <div className="bg-black/30 border border-emerald-500/30 rounded-2xl p-5 space-y-4">
        <div className="flex items-center justify-between border-b border-white/10 pb-3">
          <h3 className="text-base font-bold text-emerald-300 flex items-center gap-2">
            <Truck className="w-5 h-5 text-emerald-400" />
            Phase 2 : Livraisons au Cabinet
          </h3>
          <span className="bg-emerald-500/20 text-emerald-300 text-xs px-2.5 py-0.5 rounded-full font-semibold">
            {phase2Orders.length}
          </span>
        </div>

        <div className="space-y-4">
          {phase2Orders.map(o => (
            <div key={o.id} className="bg-white/5 border border-white/10 rounded-2xl p-4">
              <div className="flex justify-between items-center mb-3">
                <span className="font-mono text-sm font-bold text-white">REF: {o.patient_ref}</span>
                <span className={`text-[10px] px-2.5 py-0.5 rounded font-bold uppercase ${
                  o.status === "EN_ROUTE_CABINET"
                    ? "bg-purple-500/20 text-purple-300 border border-purple-500/30 animate-pulse"
                    : "bg-emerald-500/20 text-emerald-300 border border-emerald-500/30"
                }`}>
                  {o.status === "EN_ROUTE_CABINET" ? "🚚 En Route vers Cabinet" : "📦 Prêt pour Expédition"}
                </span>
              </div>

                {/* Routing: Labo -> Cabinet */}
                <div className="relative pl-6 mb-4 space-y-3">
                  <div className="absolute left-[11px] top-2 bottom-2 w-0.5 border-l-2 border-dashed border-emerald-500/30"></div>
                  <div className="relative">
                    <div className="absolute -left-6 top-0.5 text-base">📍</div>
                    <div className="text-sm font-medium text-white">Point A: Laboratoire CFAO</div>
                    <div className="text-xs text-slate-400">Départ — Prothèse terminée</div>
                  </div>
                  <div className="relative">
                    <div className="absolute -left-6 top-0.5 text-base">🏥</div>
                    <div className="text-sm font-medium text-emerald-400">Point B: {o.dentist_name}</div>
                    <div className="text-xs text-slate-400">Destination — Cabinet Dentaire</div>
                  </div>
                </div>

                {/* Action Buttons */}
                <div>
                  {o.status === "PRET_EXPEDITION" && (
                    <button
                      onClick={() => patchOrder(o.id, { status: "EN_ROUTE_CABINET" })}
                      className="w-full bg-indigo-600 hover:bg-indigo-500 text-white rounded-xl py-3 flex justify-center items-center gap-2 font-semibold text-xs transition-colors shadow-lg"
                    >
                      📷 Scanner & Récupérer
                    </button>
                  )}
                  {o.status === "EN_ROUTE_CABINET" && (
                    verifyingId === o.id ? (
                      <div className="bg-black/50 border border-white/10 p-3 rounded-xl flex gap-2">
                        <input
                          type="text"
                          placeholder="Code PIN (Ex: 1234)"
                          value={pin}
                          onChange={e => setPin(e.target.value)}
                          className="flex-1 bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-sm text-white focus:border-emerald-500 focus:outline-none"
                          autoFocus
                        />
                        <button
                          onClick={() => handleConfirmDelivery(o.id)}
                          className="bg-emerald-600 hover:bg-emerald-500 text-white font-semibold px-4 py-2 rounded-lg text-sm transition-colors"
                        >
                          Confirmer
                        </button>
                        <button
                          onClick={() => { setVerifyingId(null); setPin(""); }}
                          className="bg-white/10 hover:bg-white/20 text-slate-300 font-semibold px-3 py-2 rounded-lg text-sm transition-colors"
                        >
                          X
                        </button>
                      </div>
                    ) : (
                      <button
                        onClick={() => setVerifyingId(o.id)}
                        className="w-full bg-emerald-600 hover:bg-emerald-500 text-white rounded-xl py-3 flex justify-center items-center gap-2 font-semibold text-xs transition-colors shadow-[0_0_15px_rgba(5,150,105,0.3)]"
                      >
                        ✅ Valider PIN & Livrer
                      </button>
                    )
                  )}
                </div>
              </div>
            )
          )}
          {phase2Orders.length === 0 && (
            <div className="text-sm text-center text-slate-500 py-4">
              Aucune livraison en attente.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
