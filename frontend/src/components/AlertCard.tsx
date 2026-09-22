import StatusBadge from './StatusBadge';
import type { Alert } from '../types';

export default function AlertCard({ alert, onAcknowledge }: { alert: Alert; onAcknowledge?: (id: number) => void }) {
  return (
    <div className="bg-white rounded-lg border border-slate-200 p-3">
      <div className="flex items-center justify-between mb-1.5">
        <div className="flex items-center gap-2">
          <StatusBadge value={alert.severity} />
          <StatusBadge value={alert.status} size="xs" />
        </div>
        <span className="text-[10px] text-slate-400 font-mono">#{alert.id}</span>
      </div>
      <p className="text-sm text-slate-700 mb-1">{alert.reason}</p>
      <div className="flex items-center justify-between">
        <div className="text-[10px] text-slate-500 space-x-3">
          <span>Splice: {alert.splice_id}</span>
          {alert.location && <span>Pos: {alert.location}</span>}
          <span>Conf: {(alert.confidence * 100).toFixed(0)}%</span>
        </div>
        {alert.status === 'ACTIVE' && onAcknowledge && (
          <button
            onClick={() => onAcknowledge(alert.id)}
            className="text-[10px] px-2 py-0.5 bg-blue-50 text-blue-600 rounded hover:bg-blue-100"
          >
            Acknowledge
          </button>
        )}
      </div>
      {alert.recommended_action && (
        <p className="text-[10px] text-slate-500 mt-1.5 italic">{alert.recommended_action}</p>
      )}
    </div>
  );
}
