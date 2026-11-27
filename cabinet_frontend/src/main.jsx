import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.jsx'
import { TenantProvider } from './contexts/TenantContext.jsx'

createRoot(document.getElementById('root')).render(
  <StrictMode>
    {import.meta.env.VITE_SIMULATION === '1' && (
      <div role="status" className="bg-amber-300 px-4 py-2 text-center text-sm font-bold text-slate-950">
        SIMULATION — laboratoire virtuel, données fictives. Aucun appareil connecté.
      </div>
    )}
    <TenantProvider>
      <App />
    </TenantProvider>
  </StrictMode>,
)
