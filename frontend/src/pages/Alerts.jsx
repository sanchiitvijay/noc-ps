import { useEffect, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { getLogs } from '../services/api';
import { useStore } from '../store';
import Tag from '../components/Tag';
import AlertDrawer from '../components/AlertDrawer';
import AlertSimulation from '../components/AlertSimulation';

const emptyFilters = {
  severity: '',
  device_id: '',
  event_id: '',
  ip_address: '',
  search: '',
};

const columns = ['No.', 'Event ID', 'Time', 'Device', 'Device ID', 'IP', 'Severity', 'Message', 'Details'];
const severityOptions = ['P1', 'P2', 'P3', 'P4'];

function normalizeEventId(value) {
  let eventId = value;
  while (eventId && typeof eventId === 'object') eventId = eventId.event_id ?? eventId.id;
  if (eventId === null || eventId === undefined || eventId === '') return null;
  const numericEventId = Number(eventId);
  return Number.isSafeInteger(numericEventId) ? numericEventId : null;
}

function simulatedEventForDetails(event, knownAlerts = []) {
  const parsedTime = Date.parse(event.event_time);
  let timestamp = parsedTime;
  if (Number.isNaN(timestamp)) {
    const timeOnly = String(event.event_time || '').match(/^(\d{2}):(\d{2}):(\d{2})(?:\.(\d+))?$/);
    if (timeOnly) {
      const eventDate = new Date();
      eventDate.setHours(Number(timeOnly[1]), Number(timeOnly[2]), Number(timeOnly[3]), Number((timeOnly[4] || '').padEnd(3, '0').slice(0, 3) || 0));
      timestamp = eventDate.getTime();
    }
  }

  const typeName = String(event.event_type_name || '').trim().toLowerCase();
  const knownType = knownAlerts.find((alert) => (
    String(alert.event_type_name || '').trim().toLowerCase() === typeName
    || String(alert.msg || '').trim().toLowerCase() === typeName
  ));

  return {
    id: event.event_id,
    t: Number.isNaN(timestamp) ? Date.now() : timestamp,
    sev: event.severity || 'Unknown',
    msg: event.message || event.event_type_name || 'Network event',
    st: 'Open',
    who: 'N/A',
    event_type_id: event.event_type_id ?? knownType?.event_type_id,
    event_type_name: event.event_type_name,
    category: event.category,
    simulated: event.simulated,
    d: {
      id: event.device_id,
      name: event.device_name || `Device ${event.device_id ?? 'unknown'}`,
      ip: event.ip_address || '',
    },
  };
}

export default function Alerts() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const {
    alerts,
    logTotal,
    logPage,
    logPageSize,
    loadingLogs,
    error,
    loadLogs,
    acknowledgedDeviceIds,
  } = useStore();
  const [filters, setFilters] = useState(() => ({
    ...emptyFilters,
    severity: searchParams.get('severity') === 'all' ? '' : severityOptions.includes(searchParams.get('severity')) ? searchParams.get('severity') : '',
    device_id: searchParams.get('device_id') || '',
    event_id: searchParams.get('event_id') || '',
    ip_address: searchParams.get('ip_address') || '',
    search: searchParams.get('search') || '',
  }));
  const [selected, setSelected] = useState(null);
  const [simulatedEvents, setSimulatedEvents] = useState([]);
  const showUnacknowledgedOnly = searchParams.get('acknowledged') === 'false';

  useEffect(() => {
    // Initial load with filters parsed from URL
    const { ip_address, event_id, ...rest } = filters;
    const queryPayload = { ...rest };
    if (event_id && event_id.trim()) queryPayload.event_id = event_id.trim();
    loadLogs(queryPayload).catch(() => {});
  }, [loadLogs]);

  const updateFilter = (key, value) => {
    setFilters((current) => ({ ...current, [key]: value }));
  };

  const runQuery = (page = 1) => {
    const { ip_address, event_id, ...rest } = filters;
    const queryPayload = { ...rest, page };
    if (event_id && event_id.trim()) {
      queryPayload.event_id = event_id.trim();
    }
    loadLogs(queryPayload).catch(() => {});
  };

  const eventIdMatches = (eventId) => !filters.event_id || String(eventId) === filters.event_id.trim();
  const ipAddressMatches = (ipAddress) => !filters.ip_address
    || String(ipAddress || '').toLowerCase().includes(filters.ip_address.trim().toLowerCase());
  const visibleSimulationEvents = simulatedEvents.filter((event) => eventIdMatches(event.event_id));
  const filteredSimulationEvents = visibleSimulationEvents.filter((event) => ipAddressMatches(event.ip_address));
  const visibleAlerts = alerts
    .filter((alert) => !showUnacknowledgedOnly || !acknowledgedDeviceIds.includes(String(alert.d.id)))
    .filter((alert) => eventIdMatches(alert.id))
    .filter((alert) => ipAddressMatches(alert.d.ip));
  const totalPages = Math.max(1, Math.ceil(logTotal / logPageSize));
  // Keep the control compact while allowing the page range to continue as the
  // event history grows (1–10, then 11–20, and so on).
  const pageRangeStart = Math.floor((logPage - 1) / 10) * 10 + 1;
  const pageNumbers = Array.from(
    { length: Math.min(10, totalPages - pageRangeStart + 1) },
    (_, index) => pageRangeStart + index,
  );

  const exportCsv = () => {
    const rows = [
      ...filteredSimulationEvents.map((event) => [
        event.event_id, event.event_time, event.device_name || `Device ${event.device_id ?? 'unknown'}`,
        event.device_id ?? '', event.ip_address || '', event.severity || 'Unknown',
        event.message || event.event_type_name || 'Network event', event.simulated ? 'Synthetic' : 'Database event',
      ]),
      ...visibleAlerts.map((alert) => [
        alert.id, new Date(alert.t).toISOString(), alert.d.name, alert.d.id, alert.d.ip || '',
        alert.sev, alert.msg, 'Database event',
      ]),
    ];
    const escapeCell = (value) => {
      const text = String(value ?? '');
      const safeText = /^[=+@\-]/.test(text) ? `'${text}` : text;
      return `"${safeText.replace(/"/g, '""')}"`;
    };
    const csv = [['Event ID', 'Time', 'Device', 'Device ID', 'IP Address', 'Severity', 'Message', 'Source'], ...rows]
      .map((row) => row.map(escapeCell).join(','))
      .join('\r\n');
    const url = URL.createObjectURL(new Blob([csv], { type: 'text/csv;charset=utf-8' }));
    const link = document.createElement('a');
    link.href = url;
    link.download = `alerts-page-${logPage}-${new Date().toISOString().slice(0, 10)}.csv`;
    link.click();
    URL.revokeObjectURL(url);
  };

  const openEventDetails = (event, alert) => {
    event.stopPropagation();
    const eventId = normalizeEventId(alert.event_id ?? alert.id);
    const detailAlert = { ...alert, id: eventId };

    try {
      sessionStorage.setItem(`naap.event.detail.${eventId}`, JSON.stringify(detailAlert));
    } catch {
      // The detail route can still load if session storage is unavailable.
    }
    navigate(`/alerts/event/${encodeURIComponent(eventId)}`);
  };

  return (
    <>
      <AlertSimulation onEvents={setSimulatedEvents} />

      <div className="c">
        <form
          className="alerts-filter-form"
          onSubmit={(event) => {
            event.preventDefault();
            runQuery();
          }}
        >
          <select
            value={filters.severity}
            onChange={(event) => updateFilter('severity', event.target.value)}
          >
            <option value="">All severities</option>
            {severityOptions.map((severity) => <option key={severity} value={severity}>{severity}</option>)}
          </select>
          <input
            type="number"
            min="1"
            placeholder="Device ID"
            value={filters.device_id}
            onChange={(event) => updateFilter('device_id', event.target.value)}
          />
          <input
            type="text"
            inputMode="numeric"
            pattern="[0-9]*"
            placeholder="Event ID"
            aria-label="Filter by event ID"
            value={filters.event_id}
            onChange={(event) => updateFilter('event_id', event.target.value.replace(/\D/g, ''))}
          />
          <input
            type="text"
            inputMode="decimal"
            placeholder="IP address"
            aria-label="Filter by IP address"
            value={filters.ip_address}
            onChange={(event) => updateFilter('ip_address', event.target.value)}
          />
          <input
            placeholder="Search message or details"
            value={filters.search}
            onChange={(event) => updateFilter('search', event.target.value)}
          />
          <button
            type="submit"
            className="alerts-search-button"
            aria-label={loadingLogs ? 'Searching logs' : 'Search logs'}
            title={loadingLogs ? 'Searching logs' : 'Search logs'}
            disabled={loadingLogs}
          >
            <svg aria-hidden="true" viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
              <circle cx="10.8" cy="10.8" r="6.8" />
              <path d="m16 16 5 5" />
            </svg>
          </button>
        </form>
        {error && (
          <div role="alert" style={{ color: '#DC2626', marginBottom: 8 }}>
            {error}
          </div>
        )}
        <div className="alerts-results-toolbar">
          <span className="mu">{logTotal.toLocaleString()} events | Page {logPage}</span>
          <button type="button" className="alerts-export-button" onClick={exportCsv} disabled={!filteredSimulationEvents.length && !visibleAlerts.length}>
            <svg aria-hidden="true" viewBox="0 0 20 20" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="1.7"><path d="M10 2.5v9m0 0 3.5-3.5M10 11.5 6.5 8M3.5 12.5v4h13v-4" /></svg>
            Export CSV
          </button>
        </div>

        <div className="tw">
          <table className="alerts-table">
            <thead>
              <tr>{columns.map((column) => <th key={column}>{column}</th>)}</tr>
            </thead>
            <tbody>
              {filteredSimulationEvents.map((event, index) => (
                <tr key={`simulation-${event.event_id}-${index}`} className="simulation-alert-row" onClick={() => setSelected(simulatedEventForDetails(event, alerts))}>
                  <td><span className="simulation-row-label">{event.simulated ? 'SIM' : 'LIVE'}</span></td>
                  <td>{event.event_id}</td>
                  <td>{event.event_time || 'N/A'}</td>
                  <td>{event.device_name || `Device ${event.device_id ?? 'unknown'}`}</td>
                  <td>{event.device_id ?? 'N/A'}</td>
                  <td>{event.ip_address || 'N/A'}</td>
                  <td><Tag s={event.severity || 'Unknown'} /></td>
                  <td>{event.message || event.event_type_name || 'Network event'}</td>
                  <td>
                    <button
                      type="button"
                      className="event-new-tab-button"
                      aria-label={`View details for simulated event ${event.event_id}`}
                      title="View event details"
                      onClick={(clickEvent) => openEventDetails(clickEvent, simulatedEventForDetails(event, alerts))}
                    >
                      View details</button>
                  </td>
                </tr>
              ))}
              {visibleAlerts.map((alert, index) => (
                <tr
                  key={alert.id}
                  className="h"
                  onClick={() => setSelected(alert)}
                >
                  <td>{(logPage - 1) * logPageSize + index + 1}</td>
                  <td>{alert.id}</td>
                  <td>{new Date(alert.t).toLocaleString()}</td>
                  <td>{alert.d.name}</td>
                  <td>{alert.d.id}</td>
                  <td>{alert.d.ip || 'N/A'}</td>
                  <td><Tag s={alert.sev} /></td>
                  <td>{alert.msg}</td>
                  <td>
                    <button
                      type="button"
                      className="event-new-tab-button"
                      aria-label={`View details for event ${alert.id}`}
                      title="View event details"
                      onClick={(event) => openEventDetails(event, alert)}
                    >
                      View details</button>
                  </td>
                </tr>
              ))}
              {!filteredSimulationEvents.length && !visibleAlerts.length && (
                <tr>
                  <td colSpan="9" className="mu">
                    {loadingLogs ? 'Loading events...' : showUnacknowledgedOnly ? 'No unacknowledged events found.' : 'No events found.'}
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        <nav className="alerts-pagination" aria-label="Alert results pages">
          <button
            disabled={loadingLogs || logPage <= 1}
            onClick={() => runQuery(logPage - 1)}
          >
            Previous
          </button>
          <div className="alerts-page-numbers" aria-label={`Pages ${pageRangeStart} to ${pageNumbers.at(-1) || pageRangeStart}`}>
            {pageNumbers.map((page) => (
              <button
                key={page}
                type="button"
                className={page === logPage ? 'is-active' : ''}
                aria-current={page === logPage ? 'page' : undefined}
                aria-label={`Go to page ${page}`}
                disabled={loadingLogs || page === logPage}
                onClick={() => runQuery(page)}
              >
                {page}
              </button>
            ))}
          </div>
          <button
            disabled={loadingLogs || logPage * logPageSize >= logTotal}
            onClick={() => runQuery(logPage + 1)}
          >
            Next
          </button>
        </nav>
      </div>

      <AlertDrawer a={selected} onClose={() => setSelected(null)} />
    </>
  );
}
