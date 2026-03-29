import { useState } from 'react'
import { Satellite, BarChart3, Activity, Zap, Settings, BookOpen, ChevronRight } from 'lucide-react'

const NAV = [
  { id: 'dashboard',   label: 'Dashboard',    icon: Satellite },
  { id: 'history',     label: 'History',      icon: Activity },
  { id: 'scenarios',   label: 'Scenarios',    icon: BarChart3 },
  { id: 'optimize',    label: 'Optimize',     icon: Settings },
  { id: 'explain',     label: 'How It Works', icon: BookOpen },
]

export default function Layout({ currentPage, onNavigate, result, children }) {
  const [sidebarOpen, setSidebarOpen] = useState(true)
  const risk = result?.risk?.toLowerCase()

  const statusColor = {
    none:     '#16A34A',
    low:      '#65A30D',
    moderate: '#D97706',
    high:     '#EA580C',
    severe:   '#DC2626',
  }[risk] || '#64748B'

  return (
    <div className="min-h-screen bg-slate-50 flex">
      {/* ── Sidebar ── */}
      <aside className={`${sidebarOpen ? 'w-56' : 'w-16'} transition-all duration-200
        bg-white border-r border-slate-100 flex flex-col shrink-0 shadow-sm`}>

        {/* Logo */}
        <div className="px-4 py-4 border-b border-slate-100 flex items-center gap-3">
          <div
            className="w-8 h-8 rounded-xl flex items-center justify-center text-white text-base shrink-0"
            style={{ background: statusColor }}
          >
            🛰️
          </div>
          {sidebarOpen && (
            <div>
              <div className="font-bold text-slate-800 text-sm leading-tight">SatComm</div>
              <div className="text-xs text-slate-400 leading-tight">Monitor</div>
            </div>
          )}
          <button
            onClick={() => setSidebarOpen(v => !v)}
            className="ml-auto text-slate-300 hover:text-slate-500 transition-colors"
          >
            <ChevronRight size={14} className={`transition-transform ${sidebarOpen ? 'rotate-180' : ''}`} />
          </button>
        </div>

        {/* Nav */}
        <nav className="flex-1 px-2 py-3 flex flex-col gap-1">
          {NAV.map(({ id, label, icon: Icon }) => (
            <button
              key={id}
              onClick={() => onNavigate(id)}
              className={`flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm
                font-medium transition-all text-left w-full
                ${currentPage === id
                  ? 'bg-blue-50 text-blue-700'
                  : 'text-slate-500 hover:bg-slate-50 hover:text-slate-800'
                }`}
            >
              <Icon size={16} className="shrink-0" />
              {sidebarOpen && <span className="truncate">{label}</span>}
            </button>
          ))}
        </nav>

        {/* Status dot */}
        {sidebarOpen && result && (
          <div className="px-4 py-3 border-t border-slate-100">
            <div className="flex items-center gap-2">
              <span
                className="w-2.5 h-2.5 rounded-full animate-pulse-slow shrink-0"
                style={{ background: statusColor }}
              />
              <span className="text-xs text-slate-500 capitalize truncate">
                {risk || 'Standing by'}
              </span>
            </div>
          </div>
        )}
      </aside>

      {/* ── Main content ── */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Topbar */}
        <header className="bg-white border-b border-slate-100 px-6 py-3.5 flex items-center justify-between shadow-sm">
          <div>
            <h1 className="font-bold text-slate-800 text-base">
              {NAV.find(n => n.id === currentPage)?.label || 'Dashboard'}
            </h1>
            <p className="text-xs text-slate-400 mt-0.5">
              GEO orbit · Ku-band · 35,786 km · Physics-based · Deterministic
            </p>
          </div>

          <div className="flex items-center gap-3">
            {result && (
              <div
                className="text-xs font-semibold px-3 py-1.5 rounded-lg"
                style={{ color: statusColor, background: statusColor + '15' }}
              >
                SNR {result.snr >= 0 ? '+' : ''}{result.snr?.toFixed(1)} dB
              </div>
            )}
            <div className="text-xs text-slate-400 text-right hidden sm:block">
              <div>No ML · No approximations</div>
              <div className="text-slate-300">physics_model.py</div>
            </div>
          </div>
        </header>

        {/* Page */}
        <main className="flex-1 overflow-y-auto">
          {children}
        </main>
      </div>
    </div>
  )
}
