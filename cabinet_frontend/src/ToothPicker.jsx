import { useId } from 'react';
import { lowerTeeth, upperTeeth } from './toothPickerHelpers';

export function DentalTooth({ number = 16, active = false, selected = false, flip = false }) {
  const uid = useId().replaceAll(':',''); const molar = number % 10 >= 6;
  const body = molar ? 'M15 12C5 7 2 17 5 29L10 47C11 57 11 81 17 85C22 87 22 58 27 55C32 58 31 84 37 85C42 85 43 62 44 48L50 28C54 12 43 7 33 12C27 15 23 15 15 12Z' : 'M16 10C7 9 8 20 12 32C16 43 17 61 21 79C24 89 29 85 30 76L35 38C40 22 40 10 32 10C25 12 23 12 16 10Z';
  return <svg className={`dental-tooth ${selected ? 'tooth-selected' : ''}`} viewBox="0 0 56 94" aria-hidden="true" style={{ transform: flip ? 'rotate(180deg)' : undefined }}><defs><linearGradient id={`${uid}-body`} x1="3" y1="30" x2="51" y2="43" gradientUnits="userSpaceOnUse"><stop stopColor="#babec1"/><stop offset=".22" stopColor="#f5f5f3"/><stop offset=".48" stopColor="#fff"/><stop offset=".72" stopColor="#e4e4e2"/><stop offset="1" stopColor="#b6b9bd"/></linearGradient><linearGradient id={`${uid}-shine`} x1="20" y1="11" x2="30" y2="78" gradientUnits="userSpaceOnUse"><stop stopColor="white"/><stop offset="1" stopColor="#c9c5c1" stopOpacity=".3"/></linearGradient><radialGradient id={`${uid}-glow`}><stop stopColor="#e99b9e" stopOpacity=".8"/><stop offset="1" stopColor="#f4c3c5" stopOpacity="0"/></radialGradient></defs><path d={body} fill={`url(#${uid}-body)`} stroke="#c6cacc" strokeWidth=".6"/><path d={molar ? 'M12 15Q20 10 25 20Q29 14 41 15M15 22Q23 17 27 29Q33 18 42 23M25 31Q21 41 20 48M29 34L34 46' : 'M17 15Q23 11 32 15M15 24Q24 21 34 24'} fill="none" stroke="#c5c6c6" strokeWidth="1" opacity=".6"/><path d={molar ? 'M13 32Q18 43 16 63M38 32Q33 43 37 69' : 'M18 30Q25 44 24 66'} stroke={`url(#${uid}-shine)`} strokeWidth="3" strokeLinecap="round" fill="none"/>{active && <g><circle cx="19" cy="24" r="15" fill={`url(#${uid}-glow)`}/><circle cx="19" cy="24" r="5" fill="#f2b1b1" fillOpacity=".5" stroke="#e99598" strokeWidth=".7"/><circle cx="19" cy="24" r="2" fill="#e58d93"/></g>}{selected && <path d="M8 90H46" stroke="#2d8076" strokeWidth="2" strokeLinecap="round"/>}</svg>;
}

function ToothButton({ number, selected, disabled, onToggle, lower = false }) {
  return <button type="button" disabled={disabled} className={`tooth-button ${selected ? 'selected' : ''}`} aria-label={`Dent ${number}`} aria-pressed={selected} onClick={() => onToggle(number)}>
    {!lower && <span className="tooth-number">{number}</span>}
    <DentalTooth number={number} active={selected} selected={selected} flip={lower} />
    {lower && <span className="tooth-number">{number}</span>}
  </button>;
}

export default function ToothPicker({ selected, onToggle, disabled = false, error = '' }) {
  const chosen = new Set(selected.map(Number));
  const count = chosen.size;
  return <section className="tooth-picker" aria-labelledby="tooth-picker-title">
    <div className="chart-caption"><span id="tooth-picker-title">Touchez les dents à prothéser · notation FDI</span><span aria-live="polite">{count} dent{count > 1 ? 's' : ''} sélectionnée{count > 1 ? 's' : ''}</span></div>
    <div className="tooth-chart" role="group" aria-label="Schéma dentaire FDI">
      <div className="tooth-row">{upperTeeth.map(n => <ToothButton key={n} number={n} selected={chosen.has(n)} disabled={disabled} onToggle={onToggle} />)}</div>
      <div className="occlusal-line"><span>MAXILLAIRE</span><div/><span>MANDIBULE</span></div>
      <div className="tooth-row lower-row">{lowerTeeth.map(n => <ToothButton key={n} number={n} lower selected={chosen.has(n)} disabled={disabled} onToggle={onToggle} />)}</div>
    </div>
    {error && <p className="mt-2 text-sm text-amber-800">{error}</p>}
  </section>;
}
