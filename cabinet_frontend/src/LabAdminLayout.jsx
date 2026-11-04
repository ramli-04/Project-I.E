import { useState } from 'react';
import { LayoutGrid, ClipboardList, Wallet, Boxes, Activity, Settings2, PanelLeftClose, PanelLeftOpen, Menu, ArrowUpRight, HeartPulse } from 'lucide-react';
import SidebarLogo from './SidebarLogo';
const navigation = [
  ['main', 'Vue d’ensemble', LayoutGrid], ['orders', 'Commandes', ClipboardList], ['inventory', 'Stocks et lots', Boxes],
  ['billing', 'Facturation', Wallet], ['operations', 'Opérations', Activity], ['configuration', 'Configuration', Settings2],
];
export default function LabAdminLayout({ section, onNavigate, accountMenu, children }) {
  const [collapsed, setCollapsed] = useState(false); const [mobileOpen, setMobileOpen] = useState(false);
  const title = navigation.find(([key]) => key === section)?.[1] || 'Laboratoire';
  return <div className={`clinical-shell ${collapsed ? 'sidebar-collapsed' : ''}`}>
    <a href="#lab-main" className="skip-link">Aller au contenu</a>
    <aside id="lab-navigation" className={`clinical-sidebar ${mobileOpen ? 'mobile-open' : ''}`}>
      <SidebarLogo collapsed={collapsed} />
      <p className="nav-eyebrow">{collapsed ? '···' : 'Espace de travail'}</p>
      <nav aria-label="Navigation du laboratoire">{navigation.map(([key,label,Icon],index) => <div key={key}>{index === 3 && !collapsed && <p className="nav-eyebrow nav-divider">Gestion du laboratoire</p>}<button className={`sidebar-link ${key === section ? 'active' : ''}`} aria-label={label} aria-current={key === section ? 'page' : undefined} title={collapsed ? label : undefined} onClick={() => { onNavigate(key); setMobileOpen(false); }}><Icon size={19} strokeWidth={1.6}/>{!collapsed && <><span>{label}</span>{key === section && <span className="nav-active-dot"/>}</>}</button></div>)}</nav>
      {!collapsed && <div className="sidebar-note"><span className="note-icon"><HeartPulse size={21}/></span><p>La précision du geste.<small>De la prescription à la prothèse, chaque étape compte.</small></p><span className="note-decoration">✳</span></div>}
      <div className="sidebar-footer"><span className="profile-avatar">C<span/></span>{!collapsed && <div><strong>Mon laboratoire</strong><small>Gestion Labo · Espace professionnel</small></div>}<button aria-label={collapsed ? 'Développer la navigation' : 'Réduire la navigation'} onClick={() => setCollapsed(!collapsed)}>{collapsed ? <PanelLeftOpen size={16}/> : <PanelLeftClose size={16}/>}</button></div>
    </aside>
    {mobileOpen && <button className="sidebar-scrim" aria-label="Fermer la navigation" onClick={() => setMobileOpen(false)}/>}
    <div className="clinical-body"><header className="clinical-header"><div className="header-heading"><button className="mobile-menu" aria-label="Ouvrir la navigation" onClick={() => setMobileOpen(!mobileOpen)}><Menu size={20}/></button><div><span className="header-breadcrumb">MON ESPACE <span>/</span> {title}</span><h1>{section === 'main' ? 'Laboratoire de prothèses dentaires' : title}<span className="heading-dot"/></h1><p>Commandes, fabrication et livraisons : votre production en un regard.</p></div></div><div className="header-actions">{accountMenu}<button className="report-button" onClick={() => window.print()} title="Imprimer le rapport de la page"><ArrowUpRight size={16}/><span>Rapport</span></button></div></header>
      <main id="lab-main" tabIndex={-1} className="clinical-main"><div key={section} className="page-enter">{children}</div><footer className="workspace-footer"><span>Gestion Labo</span><span>Au service des prothésistes dentaires.</span><span className="connection-indicator"><i/> Espace connecté</span></footer></main>
    </div>
  </div>;
}
