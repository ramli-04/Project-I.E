import { useState } from 'react';
import SidebarLogo from './SidebarLogo';

const navigation = [
  ['main', 'Vue d’ensemble', '01'],
  ['orders', 'Commandes', '02'],
  ['billing', 'Facturation', '03'],
  ['configuration', 'Configuration', '04'],
];

function LayoutIcon() {
  return <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="h-6 w-6"><rect x="3" y="3" width="18" height="18" rx="4" /><path d="M9 3v18M9 9h12" /></svg>;
}

export default function LabAdminLayout({ section, onNavigate, accountMenu, children }) {
  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const title = navigation.find(([key]) => key === section)?.[1] || 'Laboratoire';

  return <div className="flex h-dvh flex-col overflow-hidden bg-[#0d0914] font-sans text-slate-100">
    <a href="#lab-main" className="sr-only z-50 rounded-lg bg-sky-500 p-3 text-white focus:not-sr-only focus:absolute focus:left-4 focus:top-4">Aller au contenu</a>
    <header className="z-20 flex min-h-18 shrink-0 flex-wrap items-center justify-between gap-3 border-b border-white/10 bg-slate-900/50 px-4 py-3 backdrop-blur-md sm:flex-nowrap md:px-6">
      <div className="flex min-w-0 items-center gap-3">
        <button type="button" aria-label={mobileOpen ? 'Fermer la navigation' : 'Ouvrir la navigation'} aria-expanded={mobileOpen} aria-controls="lab-navigation" onClick={() => setMobileOpen(value => !value)} className="rounded-lg border border-white/10 p-2 hover:bg-white/5 focus-visible:outline-2 focus-visible:outline-sky-400 md:hidden"><LayoutIcon /></button>
        <span className="hidden text-sm text-slate-400 lg:block">{title}</span>
      </div>
      <div className="flex shrink-0 items-center gap-3">{accountMenu}</div>
    </header>
    <div className="flex min-h-0 flex-1 flex-col md:flex-row">
      <aside id="lab-navigation" className={`${mobileOpen ? 'block' : 'hidden'} ${collapsed ? 'md:w-20' : 'md:w-64'} max-h-[55dvh] shrink-0 overflow-y-auto border-b border-white/10 bg-slate-900/50 p-3 backdrop-blur-md md:block md:max-h-none md:border-r md:border-b-0`}>
        <SidebarLogo collapsed={collapsed} />
        <div className="mb-6 hidden items-center justify-between px-2 pt-3 md:flex">
          {!collapsed && <p className="text-[10px] font-semibold uppercase tracking-[0.2em] text-slate-500">Espace de travail</p>}
          <button type="button" onClick={() => setCollapsed(value => !value)} aria-label={collapsed ? 'Développer la navigation' : 'Réduire la navigation'} aria-expanded={!collapsed} className="rounded-lg p-2 text-slate-400 hover:bg-white/5 hover:text-white focus-visible:outline-2 focus-visible:outline-sky-400">{collapsed ? '→' : '←'}</button>
        </div>
        <nav aria-label="Navigation du laboratoire" className="space-y-2">{navigation.map(([key, label, number]) => <button key={key} type="button" title={collapsed ? label : undefined} aria-label={label} aria-current={section === key ? 'page' : undefined} onClick={() => { onNavigate(key); setMobileOpen(false); }} className={`flex w-full items-center gap-3 rounded-xl border px-3 py-3 text-left text-sm focus-visible:outline-2 focus-visible:outline-sky-400 ${section === key ? 'border-sky-400/20 bg-sky-400/10 text-sky-200' : 'border-transparent text-slate-400 hover:bg-white/5 hover:text-white'}`}>
          <span aria-hidden="true" className="font-mono text-xs text-slate-500">{number}</span><span className={collapsed ? 'md:hidden' : ''}>{label}</span>
        </button>)}</nav>
        {!collapsed && <div className="mt-10 hidden rounded-xl border border-white/10 bg-white/[0.02] p-4 md:block"><p className="text-xs font-medium text-slate-300">Votre laboratoire</p><p className="mt-2 break-words text-xs leading-relaxed text-slate-500">Personnel, production et partenaires réunis dans votre espace.</p></div>}
      </aside>
      <main id="lab-main" tabIndex={-1} className="min-h-0 min-w-0 flex-1 overflow-y-auto p-4 outline-none sm:p-6 lg:p-8"><div className="mx-auto max-w-7xl">{children}</div></main>
    </div>
  </div>;
}
