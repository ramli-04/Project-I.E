import { cloneElement, useId, useState } from 'react';
export const control = 'w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 disabled:opacity-50';
export function Field({ label, children }) {
  const generatedId = useId(); const id = children.props.id || generatedId;
  return <div className="space-y-2 text-sm text-slate-600"><label className="block" htmlFor={id}>{label}</label>{cloneElement(children, { id })}</div>;
}
export function Button({ children, ...props }) { return <button type="button" {...props} className={`rounded-xl border border-sky-400/30 bg-teal-600/15 px-4 py-2 text-sm text-teal-800 disabled:opacity-40 ${props.className || ''}`}>{children}</button>; }
export function Feedback({ error, notice }) { return <>{error && <p role="alert" className="rounded-xl bg-red-500/10 p-3 text-sm text-red-700">{error}</p>}{notice && <p role="status" className="rounded-xl bg-emerald-500/10 p-3 text-sm text-emerald-700">{notice}</p>}</>; }
export function Panel({ title, children }) { return <section className="space-y-4 rounded-2xl border border-slate-200/80 bg-white p-5"><h2 className="font-semibold">{title}</h2>{children}</section>; }
export function Paged({ rows, children, size = 20 }) {
  const [page, setPage] = useState(1);
  const pages = Math.max(1, Math.ceil(rows.length / size)); const current = Math.min(page, pages);
  return <>{children(rows.slice((current - 1) * size, current * size))}<nav aria-label="Pagination" className="flex items-center justify-center gap-4 py-3"><Button disabled={current === 1} onClick={() => setPage(current - 1)}>Précédent</Button><span className="text-sm text-slate-500">{current} / {pages} · {rows.length} résultat(s)</span><Button disabled={current === pages} onClick={() => setPage(current + 1)}>Suivant</Button></nav></>;
}
