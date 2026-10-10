import { useEffect, useRef, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import {
  FaSearch, FaDownload, FaEye, FaSpinner, FaExclamationTriangle, FaFilter, FaTimes,
} from "react-icons/fa";
import { useStore } from "../store";
import Tag from "../components/Tag";
import AlertDrawer from "../components/AlertDrawer";
import AlertSimulation from "../components/AlertSimulation";
import Pagination, { buildPageWindow } from "../components/Pagination";

const emptyFilters = { severity: "", device_id: "", event_id: "", ip_address: "", search: "" };
const columns = ["#", "Event ID", "Time", "Device", "Device ID", "IP", "Severity", "Message", ""];
const severityOptions = ["P1", "P2", "P3", "P4"];

function normalizeEventId(value) {
  let eventId = value;
  while (eventId && typeof eventId === "object") eventId = eventId.event_id ?? eventId.id;
  if (eventId === null || eventId === undefined || eventId === "") return null;
  const numericEventId = Number(eventId);
  return Number.isSafeInteger(numericEventId) ? numericEventId : null;
}

function simulatedEventForDetails(event, knownAlerts = []) {
  const parsedTime = Date.parse(event.event_time);
  let timestamp = parsedTime;
  if (Number.isNaN(timestamp)) {
    const timeOnly = String(event.event_time || "").match(/^(\d{2}):(\d{2}):(\d{2})(?:\.(\d+))?$/);
    if (timeOnly) {
      const eventDate = new Date();
      eventDate.setHours(
        Number(timeOnly[1]),
        Number(timeOnly[2]),
        Number(timeOnly[3]),
        Number((timeOnly[4] || "").padEnd(3, "0").slice(0, 3) || 0),
      );
      timestamp = eventDate.getTime();
    }
  }

  const typeName = String(event.event_type_name || "").trim().toLowerCase();
  const knownType = knownAlerts.find(
    (alert) =>
      String(alert.event_type_name || "").trim().toLowerCase() === typeName ||
      String(alert.msg || "").trim().toLowerCase() === typeName,
  );

  return {
    id: event.event_id,
    t: Number.isNaN(timestamp) ? Date.now() : timestamp,
    sev: event.severity || "Unknown",
    msg: event.message || event.event_type_name || "Network event",
    st: "Open",
    who: "N/A",
    event_type_id: event.event_type_id ?? knownType?.event_type_id,
    event_type_name: event.event_type_name,
    category: event.category,
    simulated: event.simulated,
    d: {
      id: event.device_id,
      name: event.device_name || `Device ${event.device_id ?? "unknown"}`,
      ip: event.ip_address || "",
    },
  };
}

const fieldClass =
  "w-full rounded-lg border border-line-strong bg-paper px-3 py-2 text-[13.5px] text-ink outline-none transition-colors focus:border-brand focus:ring-2 focus:ring-brand/20 dark:border-white/15 dark:bg-white/5 dark:text-white";

export default function Alerts() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const {
    alerts, logTotal, logPage, logPageSize, loadingLogs, error, loadLogs, acknowledgedDeviceIds,
  } = useStore();

  const [filters, setFilters] = useState(emptyFilters);
  const [selected, setSelected] = useState(null);
  const skipNextSearch = useRef(false);
  const [simulatedEvents, setSimulatedEvents] = useState([]);
  const showUnacknowledgedOnly = searchParams.get("acknowledged") === "false";

  // Every filter — including device_id, event_id and ip_address — is passed
  // straight to the backend, which filters the whole dataset before paging.
  const buildQuery = (page, source = filters) => {
    const query = {};
    Object.entries(source).forEach(([key, value]) => {
      const text = String(value ?? "").trim();
      if (text) query[key] = text;
    });
    return { ...query, page };
  };

  // Load (and reload) whenever the URL query changes — this makes top-bar
  // searches and the "unacknowledged only" nav link re-filter the console.
  const paramSignature = searchParams.toString();
  const didInitialLoad = useRef(false);
  useEffect(() => {
    const next = {
      severity:
        !searchParams.get("severity") || searchParams.get("severity") === "all"
          ? ""
          : severityOptions.includes(searchParams.get("severity"))
            ? searchParams.get("severity")
            : "",
      device_id: searchParams.get("device_id") || "",
      event_id: searchParams.get("event_id") || "",
      ip_address: searchParams.get("ip_address") || "",
      search: searchParams.get("search") || "",
    };
    setFilters(next);
    if (didInitialLoad.current) {
      skipNextSearch.current = true; // the debounced effect would re-fire
      loadLogs(buildQuery(1, next)).catch(() => {});
    }
    didInitialLoad.current = true;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [paramSignature]);

  // Free-text search and the other text filters re-query the backend live,
  // debounced like the reference console, so results update while typing.
  const searchDebounceRef = useRef(null);
  const filtersSignature = [
    filters.search, filters.severity, filters.device_id, filters.event_id, filters.ip_address,
  ].join("\u0000");
  useEffect(() => {
    if (skipNextSearch.current) {
      skipNextSearch.current = false;
      return undefined;
    }
    window.clearTimeout(searchDebounceRef.current);
    searchDebounceRef.current = window.setTimeout(() => {
      loadLogs(buildQuery(1)).catch(() => {});
    }, 350);
    return () => window.clearTimeout(searchDebounceRef.current);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filtersSignature]);

  const updateFilter = (key, value) => setFilters((current) => ({ ...current, [key]: value }));

  const runQuery = (page = 1) => {
    loadLogs(buildQuery(page)).catch(() => {});
  };

  // Simulated events are client-side only, so text filters are applied locally
  // for them; everything else comes back pre-filtered from the backend.
  const eventIdMatches = (eventId) => !filters.event_id || String(eventId) === filters.event_id.trim();
  const ipAddressMatches = (ipAddress) =>
    !filters.ip_address || String(ipAddress || "").includes(filters.ip_address.trim());
  const searchTextMatches = (event) =>
    !filters.search ||
    `${event.message || ""} ${event.event_type_name || ""} ${event.device_name || ""} ${event.ip_address || ""} ${event.device_id ?? ""}`
      .toLowerCase()
      .includes(filters.search.trim().toLowerCase());
  const simulatedMatches = (event) => eventIdMatches(event.event_id)
    && ipAddressMatches(event.ip_address)
    && searchTextMatches(event);
  const filteredSimulationEvents = simulatedEvents.filter(simulatedMatches);
  const visibleAlerts = alerts
    .filter((alert) => !showUnacknowledgedOnly || !acknowledgedDeviceIds.includes(String(alert.d.id)));

  const totalPages = Math.max(1, Math.ceil(logTotal / logPageSize));

  const exportCsv = () => {
    const rows = [
      ...filteredSimulationEvents.map((event) => [
        event.event_id, event.event_time, event.device_name || `Device ${event.device_id ?? "unknown"}`,
        event.device_id ?? "", event.ip_address || "", event.severity || "Unknown",
        event.message || event.event_type_name || "Network event", event.simulated ? "Synthetic" : "Database event",
      ]),
      ...visibleAlerts.map((alert) => [
        alert.id, new Date(alert.t).toISOString(), alert.d.name, alert.d.id, alert.d.ip || "",
        alert.sev, alert.msg, "Database event",
      ]),
    ];
    const escapeCell = (value) => {
      const text = String(value ?? "");
      const safeText = /^[=+@-]/.test(text) ? `'${text}` : text;
      return `"${safeText.replace(/"/g, '""')}"`;
    };
    const csv = [["Event ID", "Time", "Device", "Device ID", "IP Address", "Severity", "Message", "Source"], ...rows]
      .map((row) => row.map(escapeCell).join(","))
      .join("\r\n");
    const url = URL.createObjectURL(new Blob([csv], { type: "text/csv;charset=utf-8" }));
    const link = document.createElement("a");
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
      /* detail route can still load without session storage */
    }
    navigate(`/alerts/event/${encodeURIComponent(eventId)}`);
  };

  const rowCount = filteredSimulationEvents.length + visibleAlerts.length;

  return (
    <div className="grid gap-5">
      <AlertSimulation onEvents={setSimulatedEvents} />

      {/* Filters */}
      <form
        onSubmit={(event) => { event.preventDefault(); runQuery(); }}
        className="rounded-card border border-line bg-paper p-5 shadow-card dark:border-white/10 dark:bg-[#0c2435]"
      >
        <div className="mb-3 flex items-center gap-2">
          <FaFilter className="text-brand" />
          <h2 className="text-[14px] font-bold text-ink dark:text-white">Filters</h2>
          {showUnacknowledgedOnly && (
            <span className="ml-auto inline-flex items-center gap-1.5 rounded-full bg-p1-bg px-2.5 py-0.5 text-[11.5px] font-bold text-p1-ink">
              Unacknowledged priority alerts only
            </span>
          )}
        </div>

        {/* Filter order: Severity → Search → Device ID → Event ID → IP address */}
        <div className="grid grid-cols-1 gap-3 md:grid-cols-2 lg:grid-cols-6">
          <select
            value={filters.severity}
            onChange={(event) => updateFilter("severity", event.target.value)}
            className={fieldClass}
            aria-label="Severity"
          >
            <option value="">All severities</option>
            {severityOptions.map((severity) => (
              <option key={severity} value={severity}>{severity}</option>
            ))}
          </select>
          <div className="relative lg:col-span-2">
            <FaSearch className="pointer-events-none absolute top-1/2 left-3 -translate-y-1/2 text-ink-3" />
            <input
              placeholder="Search message"
              value={filters.search}
              onChange={(event) => updateFilter("search", event.target.value)}
              className={`${fieldClass} pr-8 pl-9`}
            />
            {filters.search && (
              <button
                type="button"
                aria-label="Clear search"
                onClick={() => updateFilter("search", "")}
                className="absolute top-1/2 right-2 -translate-y-1/2 rounded p-1 text-ink-3 transition-colors hover:text-ink"
              >
                <FaTimes />
              </button>
            )}
          </div>
          <input
            type="text"
            inputMode="text"
            placeholder="Device ID"
            aria-label="Filter by device ID"
            value={filters.device_id}
            onChange={(event) => updateFilter("device_id", event.target.value)}
            className={fieldClass}
          />
          <input
            type="text"
            inputMode="numeric"
            placeholder="Event ID"
            aria-label="Filter by event ID"
            value={filters.event_id}
            onChange={(event) => updateFilter("event_id", event.target.value.replace(/\D/g, ""))}
            className={fieldClass}
          />
          <input
            type="text"
            inputMode="decimal"
            placeholder="IP address"
            aria-label="Filter by IP address"
            value={filters.ip_address}
            onChange={(event) => updateFilter("ip_address", event.target.value)}
            className={fieldClass}
          />
        </div>

        <div className="mt-3 flex flex-wrap items-center gap-3">
          <button
            type="submit"
            disabled={loadingLogs}
            className="inline-flex items-center gap-2 rounded-lg bg-brand px-4 py-2 text-[13.5px] font-semibold text-white shadow-sm transition-colors hover:bg-brand-hi disabled:opacity-60"
          >
            {loadingLogs ? <FaSpinner className="animate-spin" /> : <FaSearch />}
            {loadingLogs ? "Searching…" : "Search logs"}
          </button>
          <button
            type="button"
            onClick={() => {
              setFilters(emptyFilters);
              skipNextSearch.current = true; // the debounced effect would re-fire; run it once here
              runQuery(1);
            }}
            className="text-[13px] font-medium text-ink-3 transition-colors hover:text-brand"
          >
            Clear filters
          </button>
          <span className="ml-auto text-[13px] text-ink-3">
            <b className="text-ink-2">{logTotal.toLocaleString()}</b> events · page {logPage}
          </span>
          <button
            type="button"
            onClick={exportCsv}
            disabled={!rowCount}
            className="inline-flex items-center gap-2 rounded-lg border border-line-strong bg-paper px-3 py-2 text-[13px] font-semibold text-ink-2 transition-colors hover:border-brand hover:text-brand disabled:opacity-50 dark:border-white/15 dark:bg-white/5"
          >
            <FaDownload /> Export CSV
          </button>
        </div>

        {error && (
          <div role="alert" className="mt-3 flex items-center gap-2 rounded-lg border border-p1/25 bg-p1-bg px-3 py-2 text-[13px] text-p1-ink">
            <FaExclamationTriangle /> {error}
          </div>
        )}
      </form>

      {/* Table */}
      <div className="overflow-hidden rounded-card border border-line bg-paper shadow-card dark:border-white/10 dark:bg-[#0c2435]">
        <div className="overflow-x-auto">
          <table className="w-full border-collapse text-[13px]">
            <thead>
              <tr className="bg-paper-2 dark:bg-white/5">
                {columns.map((column, index) => (
                  <th
                    key={column || index}
                    className="sticky top-0 z-10 whitespace-nowrap border-b border-line px-3 py-2.5 text-left text-[11.5px] font-semibold tracking-wider text-ink-3 uppercase dark:border-white/10"
                  >
                    {column}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-line dark:divide-white/10">
              {filteredSimulationEvents.map((event, index) => (
                <tr
                  key={`simulation-${event.event_id}-${index}`}
                  onClick={() => setSelected(simulatedEventForDetails(event, alerts))}
                  className="cursor-pointer transition-colors hover:bg-paper-2 dark:hover:bg-white/5"
                >
                  <td className="px-3 py-2.5">
                    <span className="rounded-full border border-dashed border-warn/50 bg-warn-bg px-2 py-0.5 text-[10.5px] font-bold text-warn">
                      SIM
                    </span>
                  </td>
                  <td className="px-3 py-2.5 font-mono text-ink-2">{event.event_id}</td>
                  <td className="px-3 py-2.5 whitespace-nowrap text-ink-2">{event.event_time || "N/A"}</td>
                  <td className="px-3 py-2.5 text-ink-2">{event.device_name || `Device ${event.device_id ?? "unknown"}`}</td>
                  <td className="px-3 py-2.5 font-mono text-ink-3">{event.device_id ?? "N/A"}</td>
                  <td className="px-3 py-2.5 font-mono text-ink-3">{event.ip_address || "N/A"}</td>
                  <td className="px-3 py-2.5"><Tag s={event.severity || "Unknown"} /></td>
                  <td className="max-w-[320px] truncate px-3 py-2.5 text-ink-2" title={event.message || event.event_type_name}>
                    {event.message || event.event_type_name || "Network event"}
                  </td>
                  <td className="px-3 py-2.5 text-right">
                    <button
                      type="button"
                      title="View event details"
                      onClick={(clickEvent) => openEventDetails(clickEvent, simulatedEventForDetails(event, alerts))}
                      className="inline-grid h-8 w-8 place-items-center rounded-lg border border-line text-ink-3 transition-colors hover:border-brand hover:text-brand dark:border-white/15"
                    >
                      <FaEye />
                    </button>
                  </td>
                </tr>
              ))}

              {visibleAlerts.map((alert, index) => (
                <tr
                  key={alert.id}
                  onClick={() => setSelected(alert)}
                  className="cursor-pointer transition-colors hover:bg-paper-2 dark:hover:bg-white/5"
                >
                  <td className="px-3 py-2.5 tabular text-ink-3">{(logPage - 1) * logPageSize + index + 1}</td>
                  <td className="px-3 py-2.5 font-mono text-ink-2">{alert.id}</td>
                  <td className="px-3 py-2.5 whitespace-nowrap text-ink-2">{new Date(alert.t).toLocaleString()}</td>
                  <td className="px-3 py-2.5 text-ink-2">{alert.d.name}</td>
                  <td className="px-3 py-2.5 font-mono text-ink-3">{alert.d.id}</td>
                  <td className="px-3 py-2.5 font-mono text-ink-3">{alert.d.ip || "N/A"}</td>
                  <td className="px-3 py-2.5"><Tag s={alert.sev} /></td>
                  <td className="max-w-[320px] truncate px-3 py-2.5 text-ink-2" title={alert.msg}>{alert.msg}</td>
                  <td className="px-3 py-2.5 text-right">
                    <button
                      type="button"
                      title="View event details"
                      onClick={(event) => openEventDetails(event, alert)}
                      className="inline-grid h-8 w-8 place-items-center rounded-lg border border-line text-ink-3 transition-colors hover:border-brand hover:text-brand dark:border-white/15"
                    >
                      <FaEye />
                    </button>
                  </td>
                </tr>
              ))}

              {loadingLogs && !rowCount && Array.from({ length: 8 }, (_, index) => (
                <tr key={`skeleton-${index}`} aria-hidden="true">
                  {columns.map((column, cellIndex) => (
                    <td key={column || cellIndex} className="px-3 py-2.5">
                      <div className="skeleton h-4 rounded" style={{ width: cellIndex === 7 ? "80%" : column === "" ? "2.5rem" : undefined }} />
                    </td>
                  ))}
                </tr>
              ))}

              {!rowCount && !loadingLogs && (
                <tr>
                  <td colSpan={columns.length} className="px-3 py-14 text-center text-[13.5px] text-ink-3">
                    {showUnacknowledgedOnly
                      ? "No unacknowledged events found."
                      : "No events match the current filters."}
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination */}
        <Pagination
          page={logPage}
          totalPages={totalPages}
          disabled={loadingLogs}
          onPageChange={(next) => runQuery(next)}
        />
      </div>

      <AlertDrawer a={selected} onClose={() => setSelected(null)} />
    </div>
  );
}
