const COLORS: Record<string, string> = {
  NORMAL: 'bg-emerald-100 text-emerald-700',
  MINOR_ANOMALY: 'bg-yellow-100 text-yellow-700',
  WARNING: 'bg-amber-100 text-amber-700',
  DEGRADING: 'bg-orange-100 text-orange-700',
  HIGH_RISK: 'bg-red-100 text-red-700',
  CRITICAL: 'bg-red-200 text-red-800',
  LOW: 'bg-emerald-100 text-emerald-700',
  MEDIUM: 'bg-amber-100 text-amber-700',
  HIGH: 'bg-red-100 text-red-700',
  NONE: 'bg-slate-100 text-slate-600',
  ACTIVE: 'bg-red-100 text-red-700',
  ACKNOWLEDGED: 'bg-amber-100 text-amber-700',
  RESOLVED: 'bg-emerald-100 text-emerald-700',
  ONLINE: 'bg-emerald-100 text-emerald-700',
  OFFLINE: 'bg-red-100 text-red-700',
  STABLE: 'bg-slate-100 text-slate-600',
  IMPROVING: 'bg-emerald-100 text-emerald-700',
  WORSENING: 'bg-red-100 text-red-700',
  INCREASING: 'bg-red-100 text-red-700',
  DECREASING: 'bg-emerald-100 text-emerald-700',
};

export default function StatusBadge({ value, size = 'sm' }: { value: string; size?: 'xs' | 'sm' }) {
  const color = COLORS[value] || 'bg-slate-100 text-slate-600';
  const px = size === 'xs' ? 'px-1.5 py-0.5 text-[10px]' : 'px-2 py-0.5 text-xs';
  return (
    <span className={`inline-flex items-center rounded font-medium ${color} ${px}`}>
      {value.replace(/_/g, ' ')}
    </span>
  );
}
