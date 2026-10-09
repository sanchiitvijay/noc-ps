import { useEffect, useState } from 'react';
import { getErrorInfo, runDiagnostic } from '../services/api';
import Tag from './Tag';
import RelatedTickets from './RelatedTickets';

const DIAGNOSTICS = ['ping', 'traceroute', 'nslookup'];

function ticketReferences(event, info) {
  const references = [
    event?.ticket_number, event?.ticket_no, event?.ritm_number, event?.ritm_no,
    typeof event?.ritm === 'object' ? event.ritm.number : event?.ritm, event?.request_number,
    event?.request_item_number, event?.ticket?.number, event?.ticket?.ticket_number,
    info?.ticket_number, info?.ticket_no, info?.ritm_number, info?.ritm_no,
    typeof info?.ritm === 'object' ? info.ritm.number : info?.ritm, info?.request_number,
    ...(info?.historical_info?.related_tickets || []).map((ticket) => ticket.ticket_number),
  ];
  return [...new Set(references.filter(Boolean).map(String))];
}

export default function AlertDrawer({ a, onClose }) {
  const [info, setInfo] = useState(null);
  const [loadingInfo, setLoadingInfo] = useState(false);
  const [error, setError] = useState('');
  const [diagnostic, setDiagnostic] = useState(null);
  const [busy, setBusy] = useState('');
  const [host, setHost] = useState('');

  useEffect(() => {
    const eventId = a?.event_id ?? a?.id;
    const hasEventId = eventId !== null
      && eventId !== undefined
      && eventId !== ''
      && Number.isSafeInteger(Number(eventId));

    setInfo(null);
    setLoadingInfo(hasEventId);
    setError('');
    setDiagnostic(null);
    setHost(a?.d.ip || '');

    if (!hasEventId) return;

    let cancelled = false;
    getErrorInfo(eventId)
      .then((result) => { if (!cancelled) setInfo(result); })
      .catch((requestError) => { if (!cancelled) setError(requestError.message); })
      .finally(() => { if (!cancelled) setLoadingInfo(false); });
    return () => { cancelled = true; };
  }, [a]);

  if (!a) {
    return <aside id="dr" />;
  }

  const data = info || {};
  const checks = data.preliminary_checks || {};
  const solution = data.suggested_solution || {};
  const ticketNumbers = ticketReferences(a, data);

  const run = async (kind) => {
    setBusy(kind);
    setError('');

    try {
      const body = {
        host: host.trim(),
        ...(kind === 'ping' ? { count: 4 } : {}),
      };
      const result = await runDiagnostic(kind, body);
      setDiagnostic({ kind, result });
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setBusy('');
    }
  };

  return (
    <aside id="dr" className="on">
      <div style={{ display: 'flex', justifyContent: 'space-between' }}>
        <h2 style={{ margin: 0 }}>{a.d.name}</h2>
        <button onClick={onClose}>Close</button>
      </div>
      <p><Tag s={a.sev} /> {a.msg}  |  {a.st}</p>

      {error && (
        <div role="alert" className="c" style={{ color: '#DC2626' }}>
          {error}
        </div>
      )}

      <section className="c">
        <h3>Device and event context</h3>
        <div>Device: <b>{data.device?.device_name || a.d.name}</b></div>
        <div>IP: <b>{data.device?.ip_address || a.d.ip || 'N/A'}</b></div>
        <div>Event: <b>{data.event_type?.event_type_name || a.event_type_name || a.msg}</b></div>
        <div>Category: <b>{data.event_type?.category || 'N/A'}</b></div>
        <div>RITM / Ticket: <b>{ticketNumbers.length ? ticketNumbers.join(', ') : 'Not linked'}</b></div>
        {(a.event_id ?? a.id) === null || (a.event_id ?? a.id) === undefined || (a.event_id ?? a.id) === '' ? (
          <p className="mu">
            This event has no event ID, so its error details cannot be loaded.
          </p>
        ) : null}
      </section>

      <section className="c historical-incidents-card">
        <div className="historical-incidents-heading">
          <div><span className="mu">RELATED TICKETS</span><h3>Historical incidents</h3></div>
          <div className="historical-incidents-count"><b>{data.historical_info?.total_incidents_6m ?? 'N/A'}</b><span>incidents · 6 months</span></div>
        </div>
        <RelatedTickets tickets={data.historical_info?.related_tickets || []} lastEventId={data.historical_info?.last_event_id} />
      </section>

      <section className="c">
        <h3>Preliminary checks</h3>
        <div>
          Ping: <b>{checks.ping
            ? `${checks.ping.reachable ? 'Reachable' : 'Unreachable'}  |  ${checks.ping.packet_loss_pct}% loss`
            : 'Not loaded'}</b>
        </div>
        <div>
          Traceroute: <b>{checks.traceroute
            ? checks.traceroute.completed ? 'Completed' : 'Incomplete'
            : 'Not loaded'}</b>
        </div>
      </section>

      <section className="c">
        <h3>Recommended solution</h3>
        {loadingInfo ? <div className="solution-loading" role="status" aria-label="Loading recommended solution"><span className="loading-orbit"><i /></span><div><b>Finding a recommended solution</b><span className="mu">Reviewing event context and history…</span></div><div className="solution-skeleton"><i /><i /><i /></div></div> : solution.hypothesis ? (
          <>
            <p>{solution.hypothesis}</p>
            <ol>
              {(solution.recommended_steps || []).map((step) => <li key={step}>{step}</li>)}
            </ol>
            <span className="mu">
              Generated by {solution.generated_by || 'AI'}  |  Confidence {solution.confidence || 'N/A'}
            </span>
          </>
        ) : (
          <span className="mu">
            Error analysis is not available for this event.
          </span>
        )}
      </section>

      <section className="c">
        <h3>Run diagnostics</h3>
        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
          <input
            aria-label="Diagnostic host"
            placeholder="IP address or hostname"
            value={host}
            onChange={(event) => setHost(event.target.value)}
          />
          {DIAGNOSTICS.map((kind) => (
            <button
              key={kind}
              disabled={!host.trim() || !!busy}
              onClick={() => run(kind)}
            >
              {busy === kind ? 'Running...' : kind}
            </button>
          ))}
        </div>
        {diagnostic && (
          <pre style={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}>
            {JSON.stringify(diagnostic.result, null, 2)}
          </pre>
        )}
      </section>
    </aside>
  );
}
