import { useEffect, useMemo, useRef, useState } from 'react';
import {
  Area, AreaChart, Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer,
  Tooltip, XAxis, YAxis,
} from 'recharts';
import { active, useStore } from '../store';

const SEVERITIES = ['Critical', 'Warning', 'Info', 'Unknown'];
const COLORS = { Critical: '#D32F2F', Warning: '#F7941D', Info: '#5b83aa', Unknown: '#6B7280', P1: '#D32F2F', P2: '#F7941D', P3: '#5b83aa', P4: '#6B7280' };
const RANGES = [
  { id: '24h', label: '24 hours' },
  { id: '7d', label: '7 days' },
  { id: '30d', label: '30 days' },
  { id: 'all', label: 'All time' },
];
const fmt = (value) => Number(value || 0).toLocaleString();
const formatDeviceValue = (value) => value === null || value === undefined || value === ''
  ? '—'
  : typeof value === 'object' ? JSON.stringify(value) : String(value);
const labelDeviceField = (key) => key.replace(/_/g, ' ').replace(/\b\w/g, (letter) => letter.toUpperCase());

function ChartLoader() {
  return <div className="chart-loader" role="status" aria-label="Loading chart"><span className="chart-loader-orbit"><i /></span><span>Loading insights</span><div className="chart-loader-bars"><i /><i /><i /><i /><i /><i /><i /></div></div>;
}

function formatTrendLabel(value, range) {
  const raw = String(value || '');
  const week = raw.match(/^(\d{4})-(\d{1,2})$/);
  if (range === 'all' && week) return `Week ${Number(week[2])}, ${week[1]}`;
  const date = new Date(raw.replace(' ', 'T'));
  if (Number.isNaN(date.getTime())) return raw;
  return date.toLocaleString(undefined, range === '24h'
    ? { month: 'short', day: 'numeric', hour: 'numeric' }
    : { month: 'short', day: 'numeric' });
}

function DeviceDrawer({ device, fields, events, onClose }) {
  useEffect(() => {
    if (!device) return undefined;
    const onKeyDown = (event) => { if (event.key === 'Escape') onClose(); };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [device, onClose]);
  if (!device) return null;

  return (
    <div className="device-drawer-backdrop" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose(); }}>
      <aside className="device-drawer" aria-label={`Details for ${device.device_name || device.device_id || device.id || 'device'}`}>
        <div className="device-drawer-head">
          <div><span className="mu">DEVICE DETAILS</span><h2>{device.device_name || device.device_id || device.id || 'Device details'}</h2></div>
          <button onClick={onClose} aria-label="Close device details">Close</button>
        </div>
        <div className="device-facts">{fields.map((field) => <div key={field}><span>{labelDeviceField(field)}</span><b>{formatDeviceValue(device[field])}</b></div>)}</div>
        <section className="c"><h3>Recent events</h3>{events.length ? events.map((event) => <div className="drawer-event" key={event.id}><i style={{ background: COLORS[event.sev] || COLORS.Unknown }} /><div><b>{event.msg}</b><span>{new Date(event.t).toLocaleString()} · {event.sev}</span></div></div>) : <p className="mu">No recent events for this device.</p>}</section>
      </aside>
    </div>
  );
}

function BackendDeviceTable({ rows, fields, loading, onSelect, sort, toggleSort }) {
  return (
    <div className="tw">
      <table className="device-table">
        <thead><tr>{fields.map((field) => <th key={field}><button className="sort-button" onClick={() => toggleSort(field)}>{labelDeviceField(field)}{sort.key === field ? (sort.dir === 1 ? ' ↑' : ' ↓') : ''}</button></th>)}</tr></thead>
        <tbody>
          {rows.map((device, index) => <tr key={device.device_id ?? device.id ?? device.device_name ?? index} className="h device-row" tabIndex={0} role="button" onClick={() => onSelect(device)} onKeyDown={(event) => { if (event.key === 'Enter') onSelect(device); }}>
            {fields.map((field) => <td key={field}>{formatDeviceValue(device[field])}</td>)}
          </tr>)}
          {!rows.length && <tr><td colSpan={Math.max(1, fields.length)} className="mu">{loading ? 'Loading devices…' : 'No device records were returned by the metrics API.'}</td></tr>}
        </tbody>
      </table>
    </div>
  );
}

export default function Dashboard() {
  const { metrics, alerts, loadingMetrics, error, loadDashboard } = useStore();
  const [range, setRange] = useState(RANGES[0].id);
  const [selectedSeverities, setSelectedSeverities] = useState(SEVERITIES);
  const [search, setSearch] = useState('');
  const [sort, setSort] = useState({ key: 'event_count', dir: 'desc' });
  const [selectedDevice, setSelectedDevice] = useState(null);
  const searchRef = useRef(null);
  useEffect(() => {
    if (selectedDevice) window.scrollTo({ top: 0, behavior: 'auto' });
  }, [selectedDevice]);
  const rangeInfo = RANGES.find((item) => item.id === range) || RANGES[0];
  const showChartLoader = loadingMetrics;
  const severityTotals = metrics?.events_by_severity || {};
  const severityKeySignature = Object.keys(severityTotals).join('|');
  const severityKeys = useMemo(() => severityKeySignature ? severityKeySignature.split('|') : SEVERITIES, [severityKeySignature]);
  useEffect(() => {
    if (severityKeySignature) setSelectedSeverities(severityKeySignature.split('|'));
  }, [severityKeySignature]);

  useEffect(() => { loadDashboard({ time_window: range }).catch(() => {}); }, [loadDashboard, range]);
  useEffect(() => {
    const keydown = (event) => {
      if (event.key === '/' && !['INPUT', 'TEXTAREA', 'SELECT'].includes(document.activeElement?.tagName)) {
        event.preventDefault(); searchRef.current?.focus();
      }
    };
    window.addEventListener('keydown', keydown);
    return () => window.removeEventListener('keydown', keydown);
  }, []);

  const rangeTotal = Number(metrics?.total_events || 0);
  const filteredSeverityTotals = useMemo(() => Object.fromEntries(severityKeys.map((key) => [key, selectedSeverities.includes(key) ? Number(severityTotals[key] || 0) : 0])), [severityTotals, selectedSeverities, severityKeys]);
  const selectedSeverityTotal = Object.values(filteredSeverityTotals).reduce((sum, value) => sum + value, 0);
  const filteredEvents = severityKeys.length ? selectedSeverityTotal : rangeTotal;
  const priorityOneEvents = filteredSeverityTotals.P1 ?? filteredSeverityTotals.Critical ?? 0;
  const devices = metrics?.top_alerting_devices || [];
  const deviceFieldKeys = useMemo(() => [...new Set(devices.flatMap((device) => Object.keys(device || {})))], [devices]);
  const recentActive = active(alerts);
  const alertingDeviceCount = new Set(recentActive.map((event) => String(event.d.id))).size;
  const categories = metrics?.events_by_category || {};
  const recentByDevice = useMemo(() => {
    const groups = new Map();
    alerts.forEach((event) => {
      const id = String(event.d.id);
      if (!groups.has(id)) groups.set(id, []);
      groups.get(id).push(event);
    });
    return groups;
  }, [alerts]);

  const rows = useMemo(() => devices.map((device) => {
    const events = recentByDevice.get(String(device.device_id)) || [];
    const severityCounts = Object.fromEntries(severityKeys.map((severity) => [severity, events.filter((event) => event.sev === severity).length]));
    return { ...device, device_id: device.device_id ?? device.id ?? device.device_name, severityCounts, events };
  }).filter((device) => !device.events.length || severityKeys.some((severity) => selectedSeverities.includes(severity) && device.severityCounts[severity] > 0))
    .filter((device) => !search || deviceFieldKeys.some((field) => formatDeviceValue(device[field]).toLowerCase().includes(search.toLowerCase())))
    .sort((a, b) => {
      const av = a[sort.key] ?? ''; const bv = b[sort.key] ?? '';
      return (typeof av === 'number' ? av - bv : String(av).localeCompare(String(bv))) * sort.dir;
    }), [devices, deviceFieldKeys, recentByDevice, selectedSeverities, severityKeys, search, sort, alerts.length]);

  const toggleSeverity = (severity) => setSelectedSeverities((current) => {
    if (current.includes(severity) && current.length === 1) return current;
    return current.includes(severity) ? current.filter((item) => item !== severity) : [...current, severity];
  });
  const toggleSort = (key) => setSort((current) => ({ key, dir: current.key === key ? current.dir * -1 : 1 }));
  const exportCsv = () => {
    const content = [deviceFieldKeys, ...rows.map((device) => deviceFieldKeys.map((field) => formatDeviceValue(device[field])))]
      .map((record) => record.map((value) => `"${String(value ?? '').replaceAll('"', '""')}"`).join(',')).join('\r\n');
    const link = document.createElement('a');
    link.href = URL.createObjectURL(new Blob([content], { type: 'text/csv;charset=utf-8' }));
    link.download = `dashboard-devices-${range}.csv`; link.click(); URL.revokeObjectURL(link.href);
    say('Filtered device list exported');
  };

  const trend = (metrics?.events_trend || []).map((point) => ({
    ...point,
    count: Number(point.count || 0),
    label: formatTrendLabel(point.time, range),
  }));
  const trendPeak = Math.max(1, ...trend.map((point) => point.count));
  const severityBars = severityKeys.map((severity) => ({ severity, count: Number(severityTotals[severity] || 0) }));

  return (
    <div className="dashboard-page">
      <section className="severity-filter" aria-label="All-time event totals by severity"><b>Severity {'\u00b7'} {rangeInfo.label}</b>{severityKeys.map((severity) => <button key={severity} className={`severity-chip${selectedSeverities.includes(severity) ? ' selected' : ''}`} onClick={() => toggleSeverity(severity)} aria-pressed={selectedSeverities.includes(severity)}><i style={{ background: COLORS[severity] || COLORS.Unknown }} />{severity}<span>{fmt(severityTotals[severity] || 0)}</span></button>)}</section>
      <section className="dashboard-toolbar">
        <div className="dashboard-toolbar-actions"><div className="range-pills" role="group" aria-label="Time range">{RANGES.map((item) => <button key={item.id} className={range === item.id ? 'on' : ''} onClick={() => setRange(item.id)}>{item.label}</button>)}</div></div>
      </section>
      {error && <div role="alert" className="dashboard-error">{error}</div>}

      <section className="dashboard-stat-grid">
        <article className="c dashboard-stat"><span className="mu">EVENTS {'\u00b7'} {rangeInfo.label.toUpperCase()}</span><strong>{fmt(filteredEvents)}</strong><span className="stat-foot">Filtered event volume</span><div className="stat-sparkline">{trend.map((point, index) => <i key={point.time} style={{ height: `${Math.max(12, (point.count / trendPeak) * 100)}%`, opacity: .4 + ((index + 1) / Math.max(trend.length, 1)) * .5 }} />)}</div></article>
        <article className="c dashboard-stat"><span className="mu">{severityKeys.includes('P1') ? 'P1 EVENTS' : 'CRITICAL EVENTS'}</span><strong>{fmt(priorityOneEvents)}</strong><span className="stat-foot">{selectedSeverities.includes(severityKeys.includes('P1') ? 'P1' : 'Critical') ? 'Included in severity filter' : 'Filtered out'}</span><div className="stat-highlight" style={{ background: COLORS.P1 || COLORS.Critical }} /></article>
        <article className="c dashboard-stat"><span className="mu">DEVICES ALERTING</span><strong>{fmt(alertingDeviceCount || devices.length)}</strong><span className="stat-foot">Recent loaded alerting devices</span><div className="stat-highlight" /></article>
      </section>

      <section className={`g g2 dashboard-charts${showChartLoader ? ' is-loading' : ''}`} aria-busy={showChartLoader}>
        <article className="c"><div className="dashboard-card-heading"><div><h3>Events over time</h3><span className="mu">Timestamped event volume</span></div><span className="chart-total">{fmt(rangeTotal)}</span></div><div className="dashboard-chart"><ResponsiveContainer width="100%" height="100%"><AreaChart data={trend} margin={{ top: 12, right: 8, bottom: 0, left: 2 }}><CartesianGrid stroke="var(--bd)" vertical={false} /><XAxis dataKey="label" tick={{ fill: 'var(--mu)', fontSize: 10 }} axisLine={false} tickLine={false} minTickGap={16} /><YAxis tick={{ fill: 'var(--mu)', fontSize: 10 }} axisLine={false} tickLine={false} allowDecimals={false} tickFormatter={(value) => value >= 1000 ? `${Math.round(value / 1000)}k` : value} /><Tooltip labelFormatter={(label) => label} formatter={(value) => [fmt(value), 'Events']} contentStyle={{ color: 'var(--tx)', background: 'var(--card)', border: '1px solid var(--bd)', borderRadius: 4 }} /><Area type="monotone" dataKey="count" stroke="var(--ferguson-blue)" fill="var(--ferguson-blue)" fillOpacity={.25} /></AreaChart></ResponsiveContainer></div></article>
        <article className="c"><div className="dashboard-card-heading"><div><h3>Events by severity</h3><span className="mu">Severity totals for {rangeInfo.label.toLowerCase()}</span></div></div><div className="dashboard-chart"><ResponsiveContainer width="100%" height="100%"><BarChart data={severityBars} margin={{ top: 12, right: 8, bottom: 0, left: 2 }}><CartesianGrid stroke="var(--bd)" vertical={false} /><XAxis dataKey="severity" tick={{ fill: 'var(--mu)', fontSize: 11 }} axisLine={false} tickLine={false} /><YAxis tick={{ fill: 'var(--mu)', fontSize: 10 }} axisLine={false} tickLine={false} allowDecimals={false} tickFormatter={(value) => value >= 1000 ? `${Math.round(value / 1000)}k` : value} /><Tooltip formatter={(value) => [fmt(value), 'Events']} contentStyle={{ color: 'var(--tx)', background: 'var(--card)', border: '1px solid var(--bd)', borderRadius: 4 }} /><Bar dataKey="count" radius={[4, 4, 0, 0]}>{severityBars.map((entry) => <Cell key={entry.severity} fill={COLORS[entry.severity] || COLORS.Unknown} fillOpacity={selectedSeverities.includes(entry.severity) ? .9 : .25} />)}</Bar></BarChart></ResponsiveContainer></div></article>
      </section>

      <section className="g g2 dashboard-breakdowns">
        <article className="c"><div className="dashboard-card-heading"><div><h3>Events by category</h3></div></div><div className="category-chips">{Object.entries(categories).map(([name, value]) => <span className="category-chip" key={name}>{name}<b>{fmt(value)}</b></span>)}</div></article>
      </section>

      <section className="c dashboard-device-card"><div className="dashboard-table-heading"><div><h3>Top alerting devices</h3><span className="mu">{rows.length} devices &middot; counts reflect API response</span></div><div className="table-actions"><input ref={searchRef} placeholder="Search devices  /" value={search} onChange={(event) => setSearch(event.target.value)} aria-label="Search devices" /><button onClick={exportCsv}>Export CSV</button></div></div><BackendDeviceTable rows={rows} fields={deviceFieldKeys} loading={loadingMetrics} onSelect={setSelectedDevice} sort={sort} toggleSort={toggleSort} /></section>
      <DeviceDrawer device={selectedDevice} fields={deviceFieldKeys} events={selectedDevice ? recentByDevice.get(String(selectedDevice.device_id)) || [] : []} onClose={() => setSelectedDevice(null)} />
    </div>
  );
}
