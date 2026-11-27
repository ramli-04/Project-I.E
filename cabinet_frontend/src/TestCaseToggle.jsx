import { useState } from 'react';
import { readShowTestCases, splitTestCases, writeShowTestCases } from './testCases';

export function useTestCaseFilter(rows) {
  const [show, setShow] = useState(readShowTestCases);
  const { visible, hiddenCount } = splitTestCases(rows, show);
  const toggle = hiddenCount > 0 || show ? <label className="flex items-center gap-2 text-xs text-slate-500"><input type="checkbox" checked={show} onChange={event => { setShow(event.target.checked); writeShowTestCases(event.target.checked); }} />Afficher les dossiers de test et archivés ({hiddenCount})</label> : null;
  return { visible, toggle };
}
