import { useEffect, useMemo, useRef, useState } from "react";
import {
  Area, AreaChart, Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import {
  FaSearch, FaDownload, FaTimes, FaArrowUp, FaArrowDown, FaServer,
  FaExclamationTriangle, FaBell, FaLayerGroup, FaSpinner,
} from "react-icons/fa";
import { useStore } from "../store";

const SEVERITIES = ["Critical", "Warning", "Info", "Unknown"];
const COLORS = {
  Critical: "#c8102e", Warning: "#e07a1f", Info: "#0b5d8f", Unknown: "#77787b",
  P1: "#c8102e", P2: "#e07a1f", P3: "#c29100", P4: "#2f8f83",
};
const RANGES = [
  { id: "24h", label: "24 hours" },
  { id: "7d", label: "7 days" },
  { id: "30d", label: "30 days" },
  { id: "all", label: "All time" },
];
const GRID = "#dce3e9";
const AXIS = "#8b98a5";
const fmt = (value) => Number(value || 0).toLocaleString();
const formatDeviceValue = (value) =>
  value === null || value === undefined || value === ""
    ? "—"
    : typeof value === "object"
      ? JSON.stringify(value)
      : String(value);
const labelDeviceField = (key) =>
  key.replace(/_/g, " ").replace(/\b\w/g, (letter) => letter.toUpperCase());

function formatTrendLabel(value, range) {
  const raw = String(value || "");
  const week = raw.match(/^(\d{4})-(\d{1,2})$/);
  if (range === "all" && week) return `Wk ${Number(week[2])}`;
  const date = new Date(raw.replace(" ", "T"));
  if (Number.isNaN(date.getTime())) return raw;
  return date.toLocaleString(undefined, range === "24h"
    ? { month: "short", day: "numeric", hour: "numeric" }
    : { month: "short", day: "numeric" });
}

function Kpi({ label, value, sub, icon: Icon, alarm, color }) {
  return (
    <article
      className={`relative overflow-hidden rounded-card border p-5 shadow-card ${
        alarm
          ? "border-p1/40 bg-linear-to-br from-p1/10 to-transparent dark:from-p1/20"
          : "border-line bg-paper dark:border-white/10 dark:bg-[#0c2435]"
      }`}
    >
      <div className="flex items-center gap-2 text-[12.5px] font-medium text-ink-3">
        <Icon className={color || "text-brand"} />
        {label}
      </div>
      <div className={`mt-2 text-[34px] leading-none font-extrabold tracking-tight tabular ${alarm ? "text-p1-ink" : "text-ink dark:text-white"}`}>
        {value}
      </div>
      <div className="mt-1.5 text-[12.5px] text-ink-3">{sub}</div>
    </article>
  );
}

function DeviceDrawer({ device, fields, events, onClose }) {
  useEffect(() => {
    if (!device) return undefined;
    const onKeyDown = (event) => { if (event.key === "Escape") onClose(); };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [device, onClose]);
  if (!device) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex justify-end bg-[rgba(2,20,33,0.48)] backdrop-blur-[3px] animate-fade"
      onMouseDown={(event) => { if (event.target === event.currentTarget) onClose(); }}
    >
      <aside
        aria-label={`Details for ${device.device_name || device.device_id || device.id || "device"}`}
        className="flex h-full w-full max-w-xl flex-col overflow-hidden border-l border-line bg-paper shadow-pop animate-rise dark:border-white/10 dark:bg-[#0c2435]"
      >
        <header className="flex items-start gap-3 border-b border-line px-5 py-4 dark:border-white/10">
          <span className="grid h-11 w-11 flex-none place-items-center rounded-xl bg-brand-tint text-brand dark:bg-brand/20 dark:text-brand-hi">
            <FaServer className="text-lg" />
          </span>
          <div className="min-w-0 flex-1">
            <span className="text-[11px] font-semibold tracking-wider text-ink-3 uppercase">Device details</span>
            <h2 className="truncate font-mono text-[17px] font-bold text-ink dark:text-white">
              {device.device_name || device.device_id || device.id || "Device"}
            </h2>
          </div>
          <button
            onClick={onClose}
            aria-label="Close device details"
            className="grid h-9 w-9 flex-none place-items-center rounded-lg border border-line text-ink-3 transition-colors hover:border-brand hover:text-brand dark:border-white/15"
          >
            <FaTimes />
          </button>
        </header>

        <div className="flex-1 space-y-6 overflow-y-auto px-5 py-5">
          <dl className="grid grid-cols-1 gap-x-6 gap-y-1.5 text-[13.5px] sm:grid-cols-2">
            {fields.map((field) => (
              <div key={field} className="flex gap-2 border-b border-line/60 py-1 dark:border-white/5">
                <dt className="w-32 shrink-0 text-ink-3">{labelDeviceField(field)}</dt>
                <dd className="min-w-0 break-words text-ink-2">{formatDeviceValue(device[field])}</dd>
              </div>
            ))}
          </dl>

          <section>
            <h3 className="mb-3 text-[14px] font-bold text-ink dark:text-white">Recent events</h3>
            {events.length ? (
              <div className="grid gap-2">
                {events.map((event) => (
                  <div key={event.id} className="flex items-start gap-3 rounded-lg border border-line bg-paper-2 px-3 py-2 dark:border-white/10 dark:bg-white/5">
                    <i className="mt-1.5 h-2.5 w-2.5 flex-none rounded-sm" style={{ background: COLORS[event.sev] || COLORS.Unknown }} />
                    <div className="min-w-0">
                      <b className="block text-[13.5px] text-ink dark:text-white">{event.msg}</b>
                      <span className="text-[12px] text-ink-3">{new Date(event.t).toLocaleString()} · {event.sev}</span>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-[13px] text-ink-3">No recent events for this device.</p>
            )}
          </section>
        </div>
      </aside>
    </div>
  );
}

function DeviceTable({ rows, fields, loading, onSelect, sort, toggleSort }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full border-collapse text-[13px]">
        <thead>
          <tr className="bg-paper-2 dark:bg-white/5">
            {fields.map((field) => (
              <th
                key={field}
                className="sticky top-0 z-10 whitespace-nowrap border-b border-line px-3 py-2.5 text-left text-[11.5px] font-semibold tracking-wider text-ink-3 uppercase dark:border-white/10"
              >
                <button
                  onClick={() => toggleSort(field)}
                  className="inline-flex items-center gap-1.5 transition-colors hover:text-brand"
                >
                  {labelDeviceField(field)}
                  {sort.key === field && (sort.dir === 1 ? <FaArrowUp className="text-[9px]" /> : <FaArrowDown className="text-[9px]" />)}
                </button>
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-line dark:divide-white/10">
          {rows.map((device, index) => (
            <tr
              key={device.device_id ?? device.id ?? device.device_name ?? index}
              tabIndex={0}
              role="button"
              onClick={() => onSelect(device)}
              onKeyDown={(event) => { if (event.key === "Enter") onSelect(device); }}
              className="cursor-pointer transition-colors hover:bg-paper-2 focus:bg-paper-2 dark:hover:bg-white/5 dark:focus:bg-white/5"
            >
              {fields.map((field) => (
                <td key={field} className="px-3 py-2.5 text-ink-2">{formatDeviceValue(device[field])}</td>
              ))}
            </tr>
          ))}
          {!rows.length && (
            <tr>
              <td colSpan={Math.max(1, fields.length)} className="px-3 py-14 text-center text-[13.5px] text-ink-3">
                {loading ? "Loading devices…" : "No device records were returned by the metrics API."}
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}

export default function Dashboard() {
  const { metrics, loadingMetrics, error, loadDashboard, say } = useStore();
  const [range, setRange] = useState(RANGES[0].id);
  const [selectedSeverities, setSelectedSeverities] = useState(SEVERITIES);
  const [search, setSearch] = useState("");
  const [sort, setSort] = useState({ key: "event_count", dir: -1 });
  const [selectedDevice, setSelectedDevice] = useState(null);
  const [deviceLimit, setDeviceLimit] = useState(10);
  const searchRef = useRef(null);

  useEffect(() => { loadDashboard({ time_window: range }).catch(() => {}); }, [loadDashboard, range]);

  useEffect(() => {
    const keydown = (event) => {
      if (event.key === "/" && !["INPUT", "TEXTAREA", "SELECT"].includes(document.activeElement?.tagName)) {
        event.preventDefault();
        searchRef.current?.focus();
      }
    };
    window.addEventListener("keydown", keydown);
    return () => window.removeEventListener("keydown", keydown);
  }, []);

  const rangeInfo = RANGES.find((item) => item.id === range) || RANGES[0];
  const severityTotals = metrics?.events_by_severity || {};
  const severityKeySignature = Object.keys(severityTotals).join("|");
  const severityKeys = useMemo(
    () => (severityKeySignature ? severityKeySignature.split("|") : SEVERITIES),
    [severityKeySignature],
  );

  useEffect(() => {
    if (severityKeySignature) setSelectedSeverities(severityKeySignature.split("|"));
  }, [severityKeySignature]);

  const rangeTotal = Number(metrics?.total_events || 0);
  const filteredSeverityTotals = useMemo(
    () => Object.fromEntries(
      severityKeys.map((key) => [key, selectedSeverities.includes(key) ? Number(severityTotals[key] || 0) : 0]),
    ),
    [severityTotals, selectedSeverities, severityKeys],
  );
  const selectedSeverityTotal = Object.values(filteredSeverityTotals).reduce((sum, value) => sum + value, 0);
  const filteredEvents = severityKeys.length ? selectedSeverityTotal : rangeTotal;
  const priorityOneKey = severityKeys.includes("P1") ? "P1" : "Critical";
  const priorityOneEvents = filteredSeverityTotals.P1 ?? filteredSeverityTotals.Critical ?? 0;
  const devices = metrics?.top_alerting_devices || [];
  const deviceFieldKeys = useMemo(
    () => [...new Set(devices.flatMap((device) => Object.keys(device || {})))],
    [devices],
  );
  const { alerts } = useStore();
  const alertingDeviceCount = new Set(alerts.map((event) => String(event.d.id))).size;
  const categories = metrics?.events_by_category || {};

  const busiestSites = metrics?.busiest_sites || [];
  const alertsByState = metrics?.alerts_by_state || [];
  const topEventTypes = metrics?.top_event_types || [];

  // Restore recent-events indexing: the device table joins the already-loaded
  // alert rows with the backend's top-devices list by id or name.
  const recentByDevice = useMemo(() => {
    const groups = new Map();
    const add = (key, event) => {
      if (key === undefined || key === null || key === "") return;
      const value = String(key);
      if (!groups.has(value)) groups.set(value, []);
      groups.get(value).push(event);
    };
    alerts.forEach((event) => {
      add(event.d.id, event);
      add(event.d.name, event);
    });
    return groups;
  }, [alerts]);

  // The backend always returns up to 20 (DEVICE_LIMIT) top devices; the 5/10/20
  // tabs slice that client-side so switching is instant.
  const DEVICE_LIMIT = 20;
  const rows = useMemo(
    () => devices.slice(0, DEVICE_LIMIT)
      .map((device) => {
        const events = recentByDevice.get(String(device.device_id))
          || recentByDevice.get(String(device.device_name))
          || [];
        const severityCounts = Object.fromEntries(
          severityKeys.map((severity) => [severity, events.filter((event) => event.sev === severity).length]),
        );
        return { ...device, device_id: device.device_id ?? device.id ?? device.device_name, severityCounts, events };
      })
      .filter((device) => !device.events.length || severityKeys.some((severity) => selectedSeverities.includes(severity) && device.severityCounts[severity] > 0))
      .filter((device) => !search || deviceFieldKeys.some((field) => formatDeviceValue(device[field]).toLowerCase().includes(search.toLowerCase())))
      .sort((a, b) => {
        const av = a[sort.key] ?? "";
        const bv = b[sort.key] ?? "";
        return (typeof av === "number" ? av - bv : String(av).localeCompare(String(bv))) * sort.dir;
      })
      .slice(0, deviceLimit),
    [devices, deviceFieldKeys, recentByDevice, selectedSeverities, severityKeys, search, sort, deviceLimit, alerts.length],
  );

  const toggleSeverity = (severity) => setSelectedSeverities((current) => {
    if (current.includes(severity) && current.length === 1) return current;
    return current.includes(severity) ? current.filter((item) => item !== severity) : [...current, severity];
  });
  const toggleSort = (key) => setSort((current) => ({ key, dir: current.key === key ? current.dir * -1 : -1 }));

  const exportCsv = () => {
    const content = [deviceFieldKeys, ...rows.map((device) => deviceFieldKeys.map((field) => formatDeviceValue(device[field])))]
      .map((record) => record.map((value) => `"${String(value ?? "").replaceAll('"', '""')}"`).join(","))
      .join("\r\n");
    const link = document.createElement("a");
    link.href = URL.createObjectURL(new Blob([content], { type: "text/csv;charset=utf-8" }));
    link.download = `dashboard-devices-${range}.csv`;
    link.click();
    URL.revokeObjectURL(link.href);
    say("Filtered device list exported");
  };

  const trend = (metrics?.events_trend || []).map((point) => ({
    ...point,
    count: Number(point.count || 0),
    label: formatTrendLabel(point.time, range),
  }));
  const severityBars = severityKeys.map((severity) => ({ severity, count: Number(severityTotals[severity] || 0) }));
  const categoryEntries = Object.entries(categories);
  const categoryMax = Math.max(1, ...categoryEntries.map(([, value]) => Number(value) || 0));

  return (
    <div className="grid gap-5">
      {/* Controls */}
      <section className="flex flex-wrap items-center gap-3 rounded-card border border-line bg-paper p-4 shadow-card dark:border-white/10 dark:bg-[#0c2435]">
        <b className="text-[13.5px] font-semibold text-ink dark:text-white">Severity · {rangeInfo.label}</b>
        <div className="flex flex-wrap gap-2">
          {severityKeys.map((severity) => {
            const on = selectedSeverities.includes(severity);
            return (
              <button
                key={severity}
                onClick={() => toggleSeverity(severity)}
                aria-pressed={on}
                className={`inline-flex items-center gap-2 rounded-full border px-3 py-1.5 text-[12.5px] font-semibold transition-colors ${
                  on
                    ? "border-brand bg-brand text-white"
                    : "border-line-strong bg-paper text-ink-2 hover:border-brand hover:text-brand dark:border-white/15 dark:bg-white/5"
                }`}
              >
                <i className="h-2.5 w-2.5 rounded-sm" style={{ background: COLORS[severity] || COLORS.Unknown }} />
                {severity}
                <span className={on ? "text-white/80" : "text-ink-3"}>{fmt(severityTotals[severity] || 0)}</span>
              </button>
            );
          })}
        </div>

        <div className="ml-auto inline-flex rounded-lg border border-line bg-paper-3 p-1 dark:border-white/10 dark:bg-white/5">
          {RANGES.map((item) => (
            <button
              key={item.id}
              onClick={() => setRange(item.id)}
              className={`rounded-md px-3 py-1.5 text-[12.5px] font-semibold transition-colors ${
                range === item.id
                  ? "bg-paper text-brand shadow-sm dark:bg-brand/25 dark:text-white"
                  : "text-ink-3 hover:text-ink-2"
              }`}
            >
              {item.label}
            </button>
          ))}
        </div>
      </section>

      {error && (
        <div role="alert" className="flex items-center gap-2 rounded-lg border border-p1/25 bg-p1-bg px-3 py-2 text-[13px] text-p1-ink">
          <FaExclamationTriangle /> {error}
        </div>
      )}

      {/* KPIs */}
      <section className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
        <Kpi
          icon={FaLayerGroup}
          label={`Events · ${rangeInfo.label}`}
          value={fmt(filteredEvents)}
          sub="Filtered event volume"
          color="text-brand"
        />
        <Kpi
          icon={FaExclamationTriangle}
          label={`${priorityOneKey} events`}
          value={fmt(priorityOneEvents)}
          sub={selectedSeverities.includes(priorityOneKey) ? "Included in severity filter" : "Filtered out"}
          alarm={priorityOneEvents > 0}
        />
        <Kpi
          icon={FaBell}
          label="Devices alerting"
          value={fmt(alertingDeviceCount || devices.length)}
          sub="Recent loaded alerting devices"
          color="text-p2"
        />
      </section>

      {/* Charts */}
      <section className="grid grid-cols-1 gap-5 lg:grid-cols-2" aria-busy={loadingMetrics}>
        <article className="rounded-card border border-line bg-paper p-5 shadow-card dark:border-white/10 dark:bg-[#0c2435]">
          <div className="mb-3 flex items-center gap-3">
            <div>
              <h3 className="text-[15px] font-bold text-ink dark:text-white">Events over time</h3>
              <span className="text-[12.5px] text-ink-3">Timestamped event volume</span>
            </div>
            <span className="ml-auto inline-flex items-center gap-2 text-[13px] font-semibold text-ink-2">
              {loadingMetrics && <FaSpinner className="animate-spin text-brand" />}
              {fmt(rangeTotal)}
            </span>
          </div>
          <div className="h-64 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={trend} margin={{ top: 12, right: 8, bottom: 0, left: 2 }}>
                <CartesianGrid stroke={GRID} vertical={false} />
                <XAxis dataKey="label" tick={{ fill: AXIS, fontSize: 10 }} axisLine={false} tickLine={false} minTickGap={16} />
                <YAxis tick={{ fill: AXIS, fontSize: 10 }} axisLine={false} tickLine={false} allowDecimals={false} tickFormatter={(value) => (value >= 1000 ? `${Math.round(value / 1000)}k` : value)} />
                <Tooltip formatter={(value) => [fmt(value), "Events"]} contentStyle={{ border: "1px solid #dce3e9", borderRadius: 10, fontSize: 12 }} />
                <Area type="monotone" dataKey="count" stroke="#00446a" strokeWidth={2} fill="#00446a" fillOpacity={0.22} />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </article>

        <article className="rounded-card border border-line bg-paper p-5 shadow-card dark:border-white/10 dark:bg-[#0c2435]">
          <div className="mb-3">
            <h3 className="text-[15px] font-bold text-ink dark:text-white">Events by severity</h3>
            <span className="text-[12.5px] text-ink-3">Severity totals for {rangeInfo.label.toLowerCase()}</span>
          </div>
          <div className="h-64 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={severityBars} margin={{ top: 12, right: 8, bottom: 0, left: 2 }}>
                <CartesianGrid stroke={GRID} vertical={false} />
                <XAxis dataKey="severity" tick={{ fill: AXIS, fontSize: 11 }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fill: AXIS, fontSize: 10 }} axisLine={false} tickLine={false} allowDecimals={false} tickFormatter={(value) => (value >= 1000 ? `${Math.round(value / 1000)}k` : value)} />
                <Tooltip formatter={(value) => [fmt(value), "Events"]} contentStyle={{ border: "1px solid #dce3e9", borderRadius: 10, fontSize: 12 }} />
                <Bar dataKey="count" radius={[4, 4, 0, 0]}>
                  {severityBars.map((entry) => (
                    <Cell key={entry.severity} fill={COLORS[entry.severity] || COLORS.Unknown} fillOpacity={selectedSeverities.includes(entry.severity) ? 0.9 : 0.25} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </article>
      </section>

      {/* Categories */}
      <article className="rounded-card border border-line bg-paper p-5 shadow-card dark:border-white/10 dark:bg-[#0c2435]">
        <h3 className="mb-4 text-[15px] font-bold text-ink dark:text-white">Events by category</h3>
        {categoryEntries.length ? (
          <div className="grid gap-2.5">
            {categoryEntries.map(([name, value]) => (
              <div key={name} className="grid grid-cols-[minmax(90px,150px)_1fr_auto] items-center gap-3 text-[13.5px]">
                <span className="truncate text-ink-2 capitalize">{name}</span>
                <span className="h-2.5 overflow-hidden rounded-full bg-paper-3 dark:bg-white/10">
                  <i
                    className="block h-full rounded-full bg-brand transition-[width] duration-700"
                    style={{ width: `${(Number(value) / categoryMax) * 100}%` }}
                  />
                </span>
                <b className="tabular min-w-12 text-right text-ink dark:text-white">{fmt(value)}</b>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-[13px] text-ink-3">No category breakdown returned for this window.</p>
        )}
      </article>

      {/* Platform breakdowns */}
      <section className="grid grid-cols-1 gap-5 lg:grid-cols-3">
        <article className="rounded-card border border-line bg-paper p-5 shadow-card dark:border-white/10 dark:bg-[#0c2435]">
          <h3 className="mb-4 text-[15px] font-bold text-ink dark:text-white">Busiest sites</h3>
          {busiestSites.length ? (
            <div className="grid gap-2">
              {busiestSites.map((site, index) => (
                <div key={site.site_code || site.site_name || index} className="flex items-center gap-3 text-[13px] text-ink-2">
                  <span className="grid h-6 w-6 flex-none place-items-center rounded-md bg-brand-tint text-[11px] font-bold text-brand dark:bg-brand/20 dark:text-brand-hi">{index + 1}</span>
                  <span className="min-w-0 flex-1 truncate">{site.site_name || site.site_code || "Unknown site"}</span>
                  <b className="tabular text-ink dark:text-white">{fmt(site.count)}</b>
                </div>
              ))}
            </div>
          ) : <p className="text-[13px] text-ink-3">No site data for this window.</p>}
        </article>

        <article className="rounded-card border border-line bg-paper p-5 shadow-card dark:border-white/10 dark:bg-[#0c2435]">
          <h3 className="mb-4 text-[15px] font-bold text-ink dark:text-white">Alerts by state</h3>
          {alertsByState.length ? (
            <div className="flex flex-wrap gap-2">
              {alertsByState.map((row) => (
                <span key={row.state} className="inline-flex items-center gap-2 rounded-full border border-line-strong bg-paper-2 px-3 py-1.5 text-[12.5px] font-semibold text-ink-2 dark:border-white/15 dark:bg-white/5">
                  {row.state}
                  <span className="tabular text-ink-3">{fmt(row.count)}</span>
                </span>
              ))}
            </div>
          ) : <p className="text-[13px] text-ink-3">No state breakdown for this window.</p>}
        </article>

        <article className="rounded-card border border-line bg-paper p-5 shadow-card dark:border-white/10 dark:bg-[#0c2435]">
          <h3 className="mb-4 text-[15px] font-bold text-ink dark:text-white">Top event types</h3>
          {topEventTypes.length ? (
            <div className="grid gap-2">
              {topEventTypes.map((row) => (
                <div key={row.name} className="flex items-center gap-3 text-[13px] text-ink-2">
                  <span className="min-w-0 flex-1 truncate">{row.name}</span>
                  <span className="rounded-md px-2 py-0.5 text-[11px] font-bold" style={{ background: `${COLORS[row.severity] || COLORS.Unknown}22`, color: COLORS[row.severity] || COLORS.Unknown }}>{row.severity || "—"}</span>
                  <b className="tabular text-ink dark:text-white">{fmt(row.count)}</b>
                </div>
              ))}
            </div>
          ) : <p className="text-[13px] text-ink-3">No event type data for this window.</p>}
        </article>
      </section>

      {/* Device telemetry */}
      <section className="overflow-hidden rounded-card border border-line bg-paper shadow-card dark:border-white/10 dark:bg-[#0c2435]">
        <div className="flex flex-wrap items-center gap-3 border-b border-line px-5 py-4 dark:border-white/10">
          <div>
            <h3 className="text-[15px] font-bold text-ink dark:text-white">Top alerting devices</h3>
            <span className="text-[12.5px] text-ink-3">{rows.length} devices · counts reflect API response</span>
          </div>
          <div className="ml-auto flex flex-wrap items-center gap-2">
            {/* 5 / 10 / 20 top-devices tabs — backend always returns 20, sliced here */}
            <div className="inline-flex rounded-lg border border-line bg-paper-3 p-1 dark:border-white/10 dark:bg-white/5" role="group" aria-label="Number of top devices">
              {[5, 10, 20].map((limit) => (
                <button
                  key={limit}
                  type="button"
                  onClick={() => setDeviceLimit(limit)}
                  aria-pressed={deviceLimit === limit}
                  className={`rounded-md px-2.5 py-1 text-[12.5px] font-semibold transition-colors ${
                    deviceLimit === limit
                      ? "bg-paper text-brand shadow-sm dark:bg-brand/25 dark:text-white"
                      : "text-ink-3 hover:text-ink-2"
                  }`}
                >
                  {limit}
                </button>
              ))}
            </div>
            <div className="relative">
              <FaSearch className="pointer-events-none absolute top-1/2 left-3 -translate-y-1/2 text-ink-3" />
              <input
                ref={searchRef}
                placeholder="Search devices  ( / )"
                value={search}
                onChange={(event) => setSearch(event.target.value)}
                aria-label="Search devices"
                className="w-56 rounded-lg border border-line-strong bg-paper py-2 pr-3 pl-9 text-[13px] text-ink outline-none transition-colors focus:border-brand focus:ring-2 focus:ring-brand/20 dark:border-white/15 dark:bg-white/5 dark:text-white"
              />
            </div>
            <button
              onClick={exportCsv}
              className="inline-flex items-center gap-2 rounded-lg border border-line-strong bg-paper px-3 py-2 text-[13px] font-semibold text-ink-2 transition-colors hover:border-brand hover:text-brand dark:border-white/15 dark:bg-white/5"
            >
              <FaDownload /> Export CSV
            </button>
          </div>
        </div>
        <DeviceTable
          rows={rows}
          fields={deviceFieldKeys}
          loading={loadingMetrics}
          onSelect={setSelectedDevice}
          sort={sort}
          toggleSort={toggleSort}
        />
      </section>

      <DeviceDrawer
        device={selectedDevice}
        fields={deviceFieldKeys}
        events={selectedDevice
          ? recentByDevice.get(String(selectedDevice.device_id))
            || recentByDevice.get(String(selectedDevice.device_name))
            || []
          : []}
        onClose={() => setSelectedDevice(null)}
      />
    </div>
  );
}
