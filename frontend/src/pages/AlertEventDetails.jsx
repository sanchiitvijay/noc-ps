import { useEffect, useMemo, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { getErrorInfo, runDiagnostic } from '../services/api';
import RelatedTickets from '../components/RelatedTickets';

function readEvent(eventId) {
  const key = `naap.event.detail.${eventId}`;
  try {
    const saved = sessionStorage.getItem(key);
    if (saved) return JSON.parse(saved);
    if (window.name.startsWith('naap-event:')) {
      const event = JSON.parse(window.name.slice('naap-event:'.length));
      window.name = '';
      if (String(event.id) === String(eventId)) {
        sessionStorage.setItem(key, JSON.stringify(event));
        return event;
      }
    }
  } catch {
    window.name = '';
  }
  return null;
}

function normalizeEventId(value) {
  let eventId = value;
  while (eventId && typeof eventId === 'object') eventId = eventId.event_id ?? eventId.id;
  if (eventId === null || eventId === undefined || eventId === '') return null;
  const numericEventId = Number(eventId);
  return Number.isSafeInteger(numericEventId) ? numericEventId : null;
}

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

function relativeTime(value) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return { label: 'Time unavailable', iso: '' };
  const seconds = Math.round((date.getTime() - Date.now()) / 1000);
  const units = [['year', 31536000], ['month', 2592000], ['week', 604800], ['day', 86400], ['hour', 3600], ['minute', 60]];
  const [unit, size] = units.find(([, size]) => Math.abs(seconds) >= size) || ['minute', 60];
  return { label: new Intl.RelativeTimeFormat(undefined, { numeric: 'auto' }).format(Math.round(seconds / size), unit), iso: date.toISOString() };
}

function parseRecommendedSolution(solution = {}) {
  if (typeof solution === 'string') return { steps: [], plainText: solution.trim(), summary: '' };
  const arraySteps = [solution.recommended_steps, solution.steps].find(Array.isArray);
  if (arraySteps?.length) return { steps: arraySteps.map(String), plainText: '', summary: solution.hypothesis || '' };

  const raw = [solution.recommended_solution, solution.recommended_steps, solution.solution, solution.hypothesis]
    .find((value) => typeof value === 'string' && value.trim());
  if (!raw) return { steps: [], plainText: '', summary: '' };
  const cleanRaw = raw.replace(/^\s*recommended\s+solution\s*:?\s*/i, '').replace(/\r/g, '');
  const lines = cleanRaw.split(/\n|\s+(?=\d+[.)]\s)/).map((line) => line.trim()).filter(Boolean);
  const numbered = lines.filter((line) => /^\d+[.)]\s+/.test(line)).map((line) => line.replace(/^\d+[.)]\s+/, '').trim()).filter(Boolean);
  if (numbered.length) return { steps: numbered, plainText: '', summary: solution.hypothesis || '' };
  return { steps: [], plainText: raw.trim(), summary: '' };
}

function formatResultLines(result) {
  if (typeof result === 'string') return result.split(/\r?\n/);
  return (JSON.stringify(result, null, 2) ?? String(result)).split('\n');
}

function parseTicketDate(value) {
  if (!value) return null;
  const match = String(value).match(/^(\d{2})-(\d{2})-(\d{4})(?:\s+(.*))?$/);
  const date = match ? new Date(`${match[3]}-${match[1]}-${match[2]}T${(match[4] || '00:00:00').replace(' ', 'T')}`) : new Date(value);
  return Number.isNaN(date.getTime()) ? null : date;
}

function WeeklySparkline({ tickets }) {
  const counts = useMemo(() => {
    const buckets = Array(7).fill(0);
    const today = new Date();
    today.setHours(23, 59, 59, 999);
    tickets.forEach((ticket) => {
      const date = parseTicketDate(ticket.created_on || ticket.event_time);
      if (!date) return;
      const daysAgo = Math.floor((today.getTime() - date.getTime()) / 86400000);
      if (daysAgo >= 0 && daysAgo < 7) buckets[6 - daysAgo] += 1;
    });
    return buckets;
  }, [tickets]);
  const max = Math.max(...counts, 1);
  const points = counts.map((count, index) => `${index * 24 + 3},${30 - (count / max) * 24}`).join(' ');
  return (
    <div className="event-weekly-trend">
      <div><b>Related incidents</b><span>Last 7 days</span></div>
      <svg viewBox="0 0 150 34" role="img" aria-label={`Weekly related incident counts: ${counts.join(', ')}`}>
        <path className="event-weekly-area" d={`M3,32 ${points.split(' ').map((point) => `L${point}`).join(' ')} L147,32 Z`} />
        <polyline points={points} />
        {counts.map((count, index) => <circle key={index} cx={index * 24 + 3} cy={30 - (count / max) * 24} r="2.5" />)}
      </svg>
      <span className="mu">From related ticket dates</span>
    </div>
  );
}

function CheckIcon({ name }) {
  const paths = {
    copy: <><rect x="8" y="8" width="10" height="12" rx="2" /><path d="M16 8V5a2 2 0 0 0-2-2H5a2 2 0 0 0-2 2v10a2 2 0 0 0 2 2h3" /></>,
    arrow: <><path d="M7 17 17 7M7 7h10v10" /></>,
    check: <path d="m5 12 4 4L19 6" />,
  };
  return <svg aria-hidden="true" viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">{paths[name]}</svg>;
}

function StateChip({ value }) {
  const state = String(value || '').toLowerCase();
  const tone = ['closed', 'resolved', 'acknowledged', 'complete', 'completed'].some((word) => state.includes(word))
    ? 'ok'
    : ['open', 'new', 'active', 'on hold', 'pending'].some((word) => state.includes(word)) ? 'warning' : 'neutral';
  return <span className={`event-state-chip tone-${tone}`}><i />{value || 'Unknown state'}</span>;
}

function AlertContext({ alert, device, ticketNumber, ticketUrl, opened, onCopyIp }) {
  return (
    <div className="event-alert-context" aria-label="Alert context">
      <div className="event-alert-context-status">
        <div className={`event-severity-chip severity-${String(alert.sev || 'Unknown').toLowerCase()}`}><i />{alert.sev || 'Unknown'}</div>
        <StateChip value={alert.st} />
      </div>
      <dl className="event-alert-context-grid">
        <div className="event-alert-context-device"><dt>Device</dt><dd>{device.device_name || alert.d.name || 'N/A'}</dd></div>
        <div><dt>IP address</dt><dd><span>{device.ip_address || alert.d.ip || 'IP unavailable'}</span><button type="button" className="event-icon-button" aria-label="Copy device IP address" title="Copy device IP address" onClick={onCopyIp}><CheckIcon name="copy" /></button></dd></div>
        <div><dt>Ticket</dt><dd>{ticketNumber && ticketUrl ? <a href={ticketUrl} target="_blank" rel="noreferrer">{ticketNumber}<CheckIcon name="arrow" /></a> : ticketNumber || 'Not linked'}</dd></div>
        <div><dt>Opened</dt><dd><time title={opened.iso || undefined}>{opened.label}</time></dd></div>
      </dl>
    </div>
  );
}

function CheckTile({ kind, value }) {
  const isPing = kind === 'ping';
  const failed = isPing ? value?.reachable === false : value?.completed === false;
  const passed = isPing ? value?.reachable === true : value?.completed === true;
  const tone = failed ? (isPing ? 'failed' : 'warning') : passed ? 'ok' : 'neutral';
  const label = failed ? (isPing ? 'Failed' : 'Incomplete') : passed ? 'Passed' : 'Not checked';
  return (
    <article className={`event-check-tile tone-${tone}`}>
      <div className="event-check-mark"><span /></div>
      <div className="event-check-copy"><span>{kind === 'ping' ? 'Ping' : 'Traceroute'}</span><b>{label}</b><small>{value ? isPing ? `${value.packet_loss_pct ?? '—'}% packet loss` : value.completed ? 'Route completed' : 'Route incomplete' : 'Run a check to see status'}</small></div>
    </article>
  );
}

function LoadingSkeleton({ rows = 4 }) {
  return <div className="event-skeleton" role="status" aria-label="Loading event information">{Array.from({ length: rows }, (_, index) => <i key={index} />)}</div>;
}

export default function AlertEventDetails() {
  const { eventId } = useParams();
  const [alert] = useState(() => readEvent(eventId));
  const detailEventId = normalizeEventId(alert?.event_id ?? alert?.id ?? eventId);
  const [info, setInfo] = useState(null);
  const [loadingInfo, setLoadingInfo] = useState(detailEventId !== null);
  const [error, setError] = useState('');
  const [retryCount, setRetryCount] = useState(0);
  const [host, setHost] = useState(alert?.d?.ip || '');
  const [busy, setBusy] = useState('');
  const [diagnosticLines, setDiagnosticLines] = useState([]);
  const [diagnosticError, setDiagnosticError] = useState('');
  const [rerunChecks, setRerunChecks] = useState({});

  useEffect(() => {
    if (detailEventId === null) {
      setLoadingInfo(false);
      setError('This event is missing its event ID, so related analysis cannot be loaded.');
      return undefined;
    }
    let cancelled = false;
    setLoadingInfo(true);
    setError('');
    getErrorInfo(detailEventId)
      .then((result) => { if (!cancelled) setInfo(result); })
      .catch((requestError) => { if (!cancelled) setError(`Could not load event and ticket information: ${requestError.message}`); })
      .finally(() => { if (!cancelled) setLoadingInfo(false); });
    return () => { cancelled = true; };
  }, [detailEventId, retryCount]);

  if (!alert) {
    return <section className="c alert-detail-unavailable"><h3>Event details unavailable</h3><p className="mu">Open this page using “View details” in Alerts Console.</p><Link to="/alerts">Return to Alerts Console</Link></section>;
  }

  const device = info?.device || {};
  const eventType = info?.event_type || {};
  const history = info?.historical_info || {};
  const checks = info?.preliminary_checks || {};
  const recentLogs = history.recent_event_logs || info?.recent_event_logs || [];
  const solution = info?.suggested_solution || {};
  const recommendations = parseRecommendedSolution(solution);
  const ticketNumbers = ticketReferences(alert, info);
  const ticketNumber = ticketNumbers[0];
  const firstRelatedTicket = history.related_tickets?.[0];
  const ticketUrl = alert.ticket_url || alert.itsm_url || alert.ticket?.url || info?.ticket_url || firstRelatedTicket?.url
    || (import.meta.env.VITE_ITSM_BASE_URL && ticketNumber ? `${import.meta.env.VITE_ITSM_BASE_URL.replace(/\/$/, '')}/nav_to.do?uri=task.do?sysparm_query=number%3D${encodeURIComponent(ticketNumber)}` : '');
  const pingResult = rerunChecks.ping || checks.ping;
  const routeResult = rerunChecks.traceroute || checks.traceroute;
  const eventTypeName = eventType.event_type_name || alert.event_type_name || alert.msg || '';
  const dataMismatch = eventTypeName.toLowerCase() === 'interface up' && pingResult?.reachable === false;
  const opened = relativeTime(alert.t);
  const absoluteEventId = detailEventId ?? eventId;
  const solutionSource = solution.generated_by === 'no_ticket_llm' ? 'LLM gave this response'
    : solution.generated_by === 'rule-based' ? 'Rule-based fallback'
      : solution.generated_by === 'gemini' ? 'Gemini analysis'
        : solution.generated_by || '';

  const run = async (kind) => {
    if (!host.trim()) {
      setDiagnosticError('Enter a device IP address or hostname, then retry the check.');
      return;
    }
    setBusy(kind);
    setDiagnosticError('');
    setDiagnosticLines([`$ ${kind} ${host.trim()}`, 'Connecting to diagnostics service…']);
    try {
      const result = await runDiagnostic(kind, { host: host.trim(), ...(kind === 'ping' ? { count: 4 } : {}) });
      const lines = formatResultLines(result);
      setDiagnosticLines([]);
      for (const line of lines) {
        setDiagnosticLines((current) => [...current, line]);
        await new Promise((resolve) => window.setTimeout(resolve, 24));
      }
      if (kind === 'ping' || kind === 'traceroute') setRerunChecks((current) => ({ ...current, [kind]: result }));
    } catch (requestError) {
      const message = `The ${kind} request failed: ${requestError.message}. Check the host and retry.`;
      setDiagnosticError(message);
      setDiagnosticLines((current) => [...current, `ERROR: ${message}`]);
    } finally {
      setBusy('');
    }
  };

  const copyIp = async () => {
    try {
      await navigator.clipboard.writeText(device.ip_address || alert.d.ip || '');
    } catch {
      setDiagnosticError('Could not copy the IP address. Select and copy it manually.');
    }
  };

  return (
    <div className="alert-event-detail event-detail-page" role="dialog" aria-modal="true" aria-label="Alert details">
      <Link className="event-back-link" to="/alerts" aria-label="Close alert details and return to Alerts Console">
        <svg aria-hidden="true" viewBox="0 0 20 20" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="1.8"><path d="M12.5 4.5 7 10l5.5 5.5M7.5 10H17" /></svg>
        <span>Close details · Alerts Console</span>
      </Link>
      <div className="event-detail-layout">
        <div className="event-detail-main">
          {error && <div className="event-error-banner" role="alert"><div><b>Event details could not be loaded</b><span>{error}</span></div>{detailEventId !== null ? <button type="button" onClick={() => setRetryCount((count) => count + 1)} disabled={loadingInfo}>{loadingInfo ? 'Retrying…' : 'Retry'}</button> : <Link to="/alerts">Back to Alerts</Link>}</div>}
          {dataMismatch && <div className="event-mismatch-banner" role="status"><b>Data mismatch detected</b><span>The event says Interface Up, but the latest ping check failed.</span></div>}

          <section className="event-panel event-primary-checks">
            <div className="event-section-heading event-section-heading-aligned"><div><span>PRELIMINARY</span><h2>Preliminary checks</h2></div></div>
            <AlertContext alert={alert} device={device} ticketNumber={ticketNumber} ticketUrl={ticketUrl} opened={opened} onCopyIp={copyIp} />
            {loadingInfo ? <div className="event-check-grid"><LoadingSkeleton rows={2} /></div> : <div className="event-check-grid"><CheckTile kind="ping" value={pingResult} /><CheckTile kind="traceroute" value={routeResult} /></div>}
            {!loadingInfo && checks.nslookup && <div className="event-dns-result"><b>DNS lookup</b><span>{checks.nslookup.reverse_lookup || checks.nslookup.addresses?.join(', ') || 'No DNS result returned'}</span>{checks.nslookup.error && <small>{checks.nslookup.error}</small>}</div>}
          </section>

          <section className="event-panel">
            <div className="event-section-heading"><div><span>RECORD</span><h2>Device and event</h2></div><span className="event-record-id">Event {absoluteEventId}</span></div>
            {loadingInfo ? <LoadingSkeleton rows={6} /> : <dl className="event-definition-rows">
              <div><dt>Device</dt><dd>{device.device_name || alert.d.name || 'N/A'}</dd></div>
              <div><dt>Device ID</dt><dd>{alert.d.id ?? device.device_id ?? 'N/A'}</dd></div>
              {device.node_id !== null && device.node_id !== undefined && <div><dt>Node ID</dt><dd>{device.node_id}</dd></div>}
              <div><dt>IP address</dt><dd>{device.ip_address || alert.d.ip || 'N/A'}</dd></div>
              {device.site_code && <div><dt>Site code</dt><dd>{device.site_code}</dd></div>}
              {device.site_name && <div><dt>Site</dt><dd>{device.site_name}</dd></div>}
              {device.machine_type && <div><dt>Device type</dt><dd>{device.machine_type}</dd></div>}
              {device.vendor && <div><dt>Vendor</dt><dd>{device.vendor}</dd></div>}
              {device.location && <div><dt>Location</dt><dd>{device.location}</dd></div>}
              {device.created_at && <div><dt>Device created</dt><dd>{device.created_at}</dd></div>}
              {eventType.event_type_id !== null && eventType.event_type_id !== undefined && <div><dt>Event type ID</dt><dd>{eventType.event_type_id}</dd></div>}
              <div><dt>Event type</dt><dd>{eventTypeName || 'N/A'}</dd></div>
              {eventType.severity && <div><dt>Event severity</dt><dd>{eventType.severity}</dd></div>}
              <div><dt>Category</dt><dd>{eventType.category || alert.category || 'N/A'}</dd></div>
              <div><dt>Message</dt><dd>{alert.msg || 'N/A'}</dd></div>
              <div><dt>Event time</dt><dd><time title={opened.iso || undefined}>{opened.label}</time></dd></div>
            </dl>}
          </section>

          <section className="event-panel">
            <div className="event-section-heading"><div><span>EVENT HISTORY</span><h2>Recent error logs</h2></div><span className="event-record-id">{loadingInfo ? 'Loading' : `${recentLogs.length} returned`}</span></div>
            {loadingInfo ? <LoadingSkeleton rows={3} /> : recentLogs.length ? <div className="event-recent-log-list">{recentLogs.map((log, index) => <article className="event-recent-log" key={log.event_id || `${log.event_time}-${index}`}>
              <div className="event-recent-log-head"><b>Event {log.event_id ?? 'N/A'}</b><time>{log.event_time || 'Time unavailable'}</time><span className={`event-current-status ${Number(log.current_status) === 0 ? 'tone-failed' : Number(log.current_status) === 1 ? 'tone-ok' : 'tone-neutral'}`}>{log.current_status === null || log.current_status === undefined ? 'Status unavailable' : Number(log.current_status) === 0 ? 'Down (0)' : Number(log.current_status) === 1 ? 'Up (1)' : `Status ${log.current_status}`}</span></div>
              <p>{log.message || 'No event message returned.'}</p>
              {log.raw_detail && <pre>{log.raw_detail}</pre>}
            </article>)}</div> : <p className="event-empty-note">No recent error logs were returned for this device and event type.</p>}
          </section>

          <section className="event-panel event-incidents-panel">
            <div className="event-section-heading"><div><span>HISTORY</span><h2>Related incidents</h2></div><div className="event-incident-total"><b>{loadingInfo ? '—' : history.total_incidents_6m ?? '0'}</b><span>event occurrences · 6 months</span></div></div>
            {loadingInfo ? <LoadingSkeleton rows={3} /> : <>
              <WeeklySparkline tickets={history.related_tickets || []} />
              <div className="event-related-ticket-heading"><b>Related ticket numbers</b><span>{history.related_tickets?.length || 0} returned by API</span></div>
              <RelatedTickets tickets={history.related_tickets || []} lastEventId={history.last_event_id} />
              {!history.related_tickets?.length && <p className="event-empty-note">The event history reports {history.total_incidents_6m ?? 0} occurrences, but the API returned no related ticket records or ticket numbers for this alert.</p>}
            </>}
          </section>
        </div>

        <aside className="event-detail-rail">
          <section className="event-panel event-recommendations">
            <div className="event-section-heading event-section-heading-aligned"><div><span>REMEDIATION</span><h2>Recommended steps</h2></div>{solutionSource && !loadingInfo && <span className="event-solution-source">{solutionSource}</span>}</div>
            {loadingInfo ? <LoadingSkeleton rows={4} /> : error ? <p className="event-empty-note">Recommendations failed to load. Use Retry above to request them again.</p> : recommendations.steps.length || recommendations.plainText || recommendations.summary ? <>
              {recommendations.summary && <p className="event-recommendation-plain">{recommendations.summary}</p>}
              {recommendations.steps.length > 0 && <p className="event-recommendation-plain">{recommendations.steps.map((step, index) => `${index + 1}. ${step}`).join('\n')}</p>}
              {recommendations.plainText && <p className="event-recommendation-plain">{recommendations.plainText}</p>}
            </> : <p className="event-empty-note">No recommended solution was returned for this event. Retry to request the latest solution.</p>}
          </section>

          <section className="event-panel event-diagnostics">
            <div className="event-section-heading"><div><span>TOOLS</span><h2>Diagnostics</h2></div></div>
            <label className="event-host-label" htmlFor="diagnostic-host">Target host</label>
            <input id="diagnostic-host" value={host} onChange={(event) => setHost(event.target.value)} placeholder="IP address or hostname" />
            <div className="event-diagnostic-buttons">{['ping', 'traceroute', 'nslookup'].map((kind) => <button key={kind} type="button" disabled={!host.trim() || !!busy} onClick={() => run(kind)}>{busy === kind ? 'Running…' : kind}</button>)}</div>
            {diagnosticError && <p className="event-diagnostic-error" role="alert">{diagnosticError}</p>}
            <div className="event-output-heading"><span>OUTPUT</span>{busy && <i className="event-output-pulse" />}</div>
            <pre className="event-output" aria-live="polite" aria-label="Diagnostic output">{diagnosticLines.length ? diagnosticLines.join('\n') : 'Output will appear here when a check runs.'}</pre>
          </section>
        </aside>
      </div>
    </div>
  );
}
