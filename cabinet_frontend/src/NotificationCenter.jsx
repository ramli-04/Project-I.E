import { useEffect, useState, useSyncExternalStore } from 'react';
import { createPortal } from 'react-dom';
import { dismissNotification, notify, snapshot, subscribe } from './notifications';

export default function NotificationCenter() {
  const notice = useSyncExternalStore(subscribe, snapshot);
  const [target, setTarget] = useState(document.body);
  useEffect(() => {
    const update = () => setTarget([...document.querySelectorAll('dialog[open]')].at(-1) || document.body);
    window.addEventListener('cabinet-dialog-change', update);
    return () => window.removeEventListener('cabinet-dialog-change', update);
  }, []);
  useEffect(() => {
    const invalid = event => {
      event.preventDefault();
      const input = event.target;
      if (input.form?.querySelector(':invalid') !== input) return;
      const label = input.labels?.[0]?.textContent?.trim();
      const message = input.validity.valueMissing ? 'Ce champ est obligatoire.' : 'Vérifiez le format ou la valeur saisis.';
      notify(`${label ? label + ' : ' : ''}${message}`, 'error');
      input.focus({ preventScroll: false });
    };
    document.addEventListener('invalid', invalid, true);
    return () => document.removeEventListener('invalid', invalid, true);
  }, []);
  useEffect(() => {
    if (!notice || notice.type === 'error') return;
    const timer = setTimeout(() => dismissNotification(notice.id), 8000);
    return () => clearTimeout(timer);
  }, [notice]);
  return notice && createPortal(<div className={`app-notification ${notice.type}`}>
    <p role={notice.type === 'error' ? 'alert' : 'status'} aria-live={notice.type === 'error' ? 'assertive' : 'polite'}>{notice.message}</p>
    <button type="button" aria-label="Fermer la notification" onClick={() => dismissNotification(notice.id)}>×</button>
  </div>, target);
}
