import { useState, useEffect } from 'react';
import { Link, useLocation } from 'react-router-dom';
import {
  LayoutDashboard, Camera, Cpu, Clock, Shield, BarChart3,
  Wifi, Play, Settings, AlertTriangle, GitBranch, Menu, X, Layers, Sun, Moon, Wrench
} from 'lucide-react';
import { api } from '../services/api';

const NAV_ITEMS = [
  { path: '/', label: 'Dashboard', icon: LayoutDashboard },
  { path: '/architecture', label: '3D Architecture', icon: Layers },
  { path: '/inspection', label: 'Live Inspection', icon: Camera },
  { path: '/history', label: 'Condition History', icon: Clock },
  { path: '/twin', label: 'Temporal Twin', icon: Cpu },
  { path: '/alerts', label: 'Alerts', icon: AlertTriangle },
  { path: '/analytics', label: 'Analytics', icon: BarChart3 },
  { path: '/pipeline', label: 'Pipeline', icon: GitBranch },
  { path: '/hardware', label: 'Hardware', icon: Wifi },
  { path: '/simulation', label: 'Simulation', icon: Play },
  { path: '/maintenance', label: 'Maintenance Guide', icon: Wrench },
  { path: '/settings', label: 'Settings', icon: Settings },
];

export default function MainLayout({ children }: { children: React.ReactNode }) {
  const location = useLocation();
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [systemOnline, setSystemOnline] = useState(false);
  const [simRunning, setSimRunning] = useState(false);
  const [darkMode, setDarkMode] = useState(() => localStorage.getItem('splicetracker-theme') === 'dark');

  useEffect(() => {
    localStorage.setItem('splicetracker-theme', darkMode ? 'dark' : 'light');
  }, [darkMode]);

  useEffect(() => {
    const check = async () => {
      try {
        const h = await api.health();
        setSystemOnline(h?.status === 'healthy');
      } catch { setSystemOnline(false); }
    };
    check();
    const t = setInterval(check, 10000);
    return () => clearInterval(t);
  }, []);

  return (
    <div className={`flex h-screen bg-slate-50 ${darkMode ? 'dark' : ''}`}>
      <aside className={`${sidebarOpen ? 'w-56' : 'w-0 overflow-hidden'} bg-white border-r border-slate-200 flex flex-col transition-all duration-200`}>
        <div className="p-4 border-b border-slate-200">
          <h1 className="text-lg font-bold text-slate-800 tracking-tight">SPLICE TRACKER</h1>
          <p className="text-xs text-slate-500 mt-0.5">Industrial Monitoring</p>
        </div>
        <nav className="flex-1 p-2 space-y-0.5 overflow-y-auto">
          {NAV_ITEMS.map((item) => {
            const active = location.pathname === item.path;
            const Icon = item.icon;
            return (
              <Link
                key={item.path}
                to={item.path}
                className={`flex items-center gap-2.5 px-3 py-2 rounded-md text-sm transition-colors ${
                  active
                    ? 'bg-blue-50 text-blue-700 font-medium'
                    : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900'
                }`}
              >
                <Icon size={16} />
                {item.label}
              </Link>
            );
          })}
        </nav>
      </aside>

      <div className="flex-1 flex flex-col min-w-0">
        <header className="h-12 bg-white border-b border-slate-200 flex items-center justify-between px-4">
          <div className="flex items-center gap-3">
            <button onClick={() => setSidebarOpen(!sidebarOpen)} className="text-slate-500 hover:text-slate-700">
              {sidebarOpen ? <X size={18} /> : <Menu size={18} />}
            </button>
            <span className="text-sm font-medium text-slate-700">
              {NAV_ITEMS.find(n => n.path === location.pathname)?.label || 'SpliceTracker'}
            </span>
          </div>
          <div className="flex items-center gap-4">
            <button
              onClick={() => setDarkMode(value => !value)}
              className="theme-toggle flex items-center gap-1.5 rounded-md border border-slate-200 bg-slate-50 px-2 py-1 text-[11px] font-medium text-slate-600 transition-colors hover:bg-slate-100"
              title={darkMode ? 'Switch to light mode' : 'Switch to dark mode'}
            >
              {darkMode ? <Sun size={14} /> : <Moon size={14} />}
              {darkMode ? 'LIGHT' : 'DARK'}
            </button>
            {simRunning && (
              <span className="text-xs bg-amber-100 text-amber-700 px-2 py-0.5 rounded font-medium">SIMULATION</span>
            )}
            <div className="flex items-center gap-1.5">
              <div className={`w-2 h-2 rounded-full ${systemOnline ? 'bg-emerald-500' : 'bg-red-500'}`} />
              <span className="text-xs text-slate-500">{systemOnline ? 'ONLINE' : 'OFFLINE'}</span>
            </div>
          </div>
        </header>
        <main className="flex-1 overflow-auto p-4">
          {children}
        </main>
      </div>
    </div>
  );
}
