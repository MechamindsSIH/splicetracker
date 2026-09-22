import { useCallback } from 'react';
import { useParams, Link } from 'react-router-dom';
import { api } from '../services/api';
import { usePolling } from '../hooks/usePolling';
import StatusBadge from '../components/StatusBadge';
import FusionDisplay from '../components/FusionDisplay';
import LoadingSpinner from '../components/LoadingSpinner';
import ErrorDisplay from '../components/ErrorDisplay';

export default function EventInspector() {
  const { id } = useParams<{ id: string }>();
  const eventId = parseInt(id || '1');
  const { data, loading, error, refetch } = usePolling(useCallback(() => api.getEvent(eventId), [eventId]), 10000);

  if (loading) return <LoadingSpinner />;
  if (error) return <ErrorDisplay message={error} onRetry={refetch} />;
  if (!data) return <ErrorDisplay message="Event not found" />;

  const event = data.event || {};
  const fusion = data.fusion_result;
  const atce = data.atce_result || {};
  const risk = data.risk_result || {};
  const localization = data.localization || {};
  const alert = data.alert;

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <Link to="/" className="text-sm text-blue-500 hover:underline">&larr; Back</Link>
        <h2 className="text-lg font-bold text-slate-800">Event: {event.event_id || `#${eventId}`}</h2>
        {event.status && <StatusBadge value={event.status} />}
      </div>

      <div className="grid grid-cols-12 gap-4">
        <div className="col-span-4 bg-white rounded-lg border border-slate-200 p-4">
          <h3 className="text-xs text-slate-500 mb-3">Event Metadata</h3>
          <dl className="space-y-1.5 text-xs">
            {[
              ['Event ID', event.event_id],
              ['Type', event.event_type],
              ['Splice', event.splice_id],
              ['Confidence', `${((event.confidence || 0) * 100).toFixed(0)}%`],
              ['Persistence', event.persistence_count],
              ['Status', event.status],
              ['Start', event.start_time ? new Date(event.start_time).toLocaleString() : 'N/A'],
            ].map(([k, v]) => (
              <div key={String(k)} className="flex justify-between">
                <dt className="text-slate-500">{k}</dt>
                <dd className="font-mono text-slate-700">{String(v || 'N/A')}</dd>
              </div>
            ))}
          </dl>
        </div>

        <div className="col-span-4">
          <FusionDisplay fusion={fusion} />
        </div>

        <div className="col-span-4 bg-white rounded-lg border border-slate-200 p-4">
          <h3 className="text-xs text-slate-500 mb-3">ATCE Temporal</h3>
          <dl className="space-y-1.5 text-xs">
            {[
              ['Previous', atce.previous_state],
              ['Current', atce.current_state],
              ['Trend', atce.trend],
              ['Persistence', atce.persistence],
              ['Recurrence', atce.recurrence ? 'Yes' : 'No'],
              ['Classification', atce.classification],
            ].map(([k, v]) => (
              <div key={String(k)} className="flex justify-between">
                <dt className="text-slate-500">{k}</dt>
                <dd className="font-mono text-slate-700">{String(v || 'N/A')}</dd>
              </div>
            ))}
          </dl>
        </div>
      </div>

      <div className="grid grid-cols-12 gap-4">
        <div className="col-span-4 bg-white rounded-lg border border-slate-200 p-4">
          <h3 className="text-xs text-slate-500 mb-3">Risk Assessment</h3>
          <div className="text-2xl font-bold font-mono mb-2">{risk.risk_score?.toFixed(0) || 0}/100</div>
          <StatusBadge value={risk.risk_level || 'LOW'} />
          {risk.contributing_factors?.length > 0 && (
            <div className="mt-3 space-y-1">
              {risk.contributing_factors.map((f: any, i: number) => (
                <div key={i} className="flex justify-between text-[10px]">
                  <span className="text-slate-600">{f.description || f.factor}</span>
                  <span className="font-mono text-slate-500">+{f.score}</span>
                </div>
              ))}
            </div>
          )}
          {risk.recommended_action && (
            <p className="text-[10px] text-slate-500 mt-2 italic">{risk.recommended_action}</p>
          )}
        </div>

        <div className="col-span-4 bg-white rounded-lg border border-slate-200 p-4">
          <h3 className="text-xs text-slate-500 mb-3">Localization</h3>
          <dl className="space-y-1.5 text-xs">
            {[
              ['Belt', localization.belt_id],
              ['Splice', localization.splice_id],
              ['Position', localization.position ? `${localization.position.toFixed(2)}m` : 'N/A'],
              ['Confidence', localization.position_confidence ? `${(localization.position_confidence * 100).toFixed(0)}%` : 'N/A'],
              ['Estimated', localization.is_estimated ? 'Yes' : 'No'],
            ].map(([k, v]) => (
              <div key={String(k)} className="flex justify-between">
                <dt className="text-slate-500">{k}</dt>
                <dd className="font-mono text-slate-700">{String(v || 'N/A')}</dd>
              </div>
            ))}
          </dl>
        </div>

        {alert && (
          <div className="col-span-4 bg-white rounded-lg border border-red-200 p-4">
            <h3 className="text-xs text-red-500 mb-3">Associated Alert</h3>
            <dl className="space-y-1.5 text-xs">
              <div className="flex justify-between"><dt className="text-slate-500">Severity</dt><dd><StatusBadge value={alert.severity} size="xs" /></dd></div>
              <div className="flex justify-between"><dt className="text-slate-500">Status</dt><dd><StatusBadge value={alert.status} size="xs" /></dd></div>
            </dl>
            <p className="text-xs text-slate-600 mt-2">{alert.reason}</p>
          </div>
        )}
      </div>
    </div>
  );
}
