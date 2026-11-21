import { useEffect, useId, useRef } from 'react';
import { createPortal } from 'react-dom';

export default function ActionDialog({ open, onClose, title, busy = false, returnFocus, children }) {
  const dialog = useRef(null);
  const titleId = useId();
  useEffect(() => {
    const element = dialog.current;
    if (!open || !element) return;
    const previous = document.activeElement;
    const opener = returnFocus?.current;
    element.showModal();
    window.dispatchEvent(new Event('cabinet-dialog-change'));
    return () => {
      element.close();
      window.dispatchEvent(new Event('cabinet-dialog-change'));
      const target = opener?.isConnected ? opener : previous;
      if (target?.isConnected) target.focus({ preventScroll: true });
    };
  }, [open, returnFocus]);
  return open && createPortal(<dialog ref={dialog} className="action-dialog" aria-labelledby={titleId}
    onCancel={event => { event.preventDefault(); if (!busy) onClose(); }}>
    <header className="action-dialog-header"><h2 id={titleId}>{title}</h2>
      <button type="button" disabled={busy} onClick={onClose} aria-label="Fermer la fenêtre">Fermer ×</button></header>
    <div className="action-dialog-content">{children}</div>
  </dialog>, document.body);
}
