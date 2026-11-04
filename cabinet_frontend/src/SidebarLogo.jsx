import logo from './assets/logo.png';

export default function SidebarLogo({ src = logo, collapsed = false }) {
  return (
    <div className="isolate flex items-center justify-center gap-3 py-4">
      <div className="relative flex h-12 w-12 shrink-0 items-center justify-center">
        <div
          aria-hidden="true"
          className="pointer-events-none absolute h-10 w-10 rounded-full bg-indigo-500/20 blur-xl"
        />
        <img
          src={src}
          alt=""
          width={48}
          height={48}
          className="relative h-12 w-12 object-contain opacity-80 mix-blend-screen transition-opacity duration-300 hover:opacity-100 motion-reduce:transition-none"
        />
      </div>
      <span
        className={collapsed
          ? 'sr-only'
          : 'whitespace-nowrap bg-gradient-to-r from-slate-200 to-slate-400 bg-clip-text text-lg font-bold tracking-tight text-transparent'}
      >
        Cabinet 2.0
      </span>
    </div>
  );
}
