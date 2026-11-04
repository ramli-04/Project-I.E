export default function SidebarLogo({ collapsed = false }) {
  return <div className="brand-lockup"><span className="brand-symbol"><img src={`${import.meta.env.BASE_URL}gestion-labo-mark.svg?v=3`} width="35" height="35" alt="Gestion Labo" /></span>{!collapsed && <span className="brand-name">Gestion Labo<small>PROTHÈSES DENTAIRES</small></span>}</div>;
}
