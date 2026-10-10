import { SITES, makeDevices, seedAlerts, USERS } from '../mock/data';
import { clearCache } from './cache';

const DEFAULT_API_URL = 'http://localhost:8000';
const CONFIGURED_API_URL = (import.meta.env.VITE_API_BASE_URL || DEFAULT_API_URL)
  .replace(/\/health\/?$/, '')
  .replace(/\/$/, '');
// Use Vite's same-origin proxy in development to avoid ngrok/CORS preflight issues.
// In dev the SPA is served from the origin, so API calls are namespaced under
// /api and rewritten by the Vite proxy (see vite.config.js). That keeps
// /admin, /sites and /tickets available as frontend routes while still
// reaching every backend endpoint. Production uses an absolute API origin.
const BASE_URL = import.meta.env.DEV ? '/api' : CONFIGURED_API_URL;
const STORAGE_KEY = 'naap.session';
const demoDevices = makeDevices();
// The backend's event_type_lookup severities are P1–P4. Keep demo rows on the
// same scale so severity filters, KPI totals and the priority badge agree with
// what the live API returns.
const DEMO_SEVERITY = { Critical: 'P1', Warning: 'P2', Info: 'P3', Unknown: 'P4' };
const demoAlerts = seedAlerts(demoDevices).map((alert, index) => ({
  ...alert,
  sev: DEMO_SEVERITY[alert.sev] || alert.sev || 'P4',
  event_type_id: index % 6 + 1,
  event_type_name: alert.msg,
}));

function buildDemoMetrics(timeWindow = 'all') {
  const now = Date.now();
  const windowMs = { '24h': 24 * 60 * 60 * 1000, '7d': 7 * 24 * 60 * 60 * 1000, '30d': 30 * 24 * 60 * 60 * 1000 }[timeWindow];
  const events = demoAlerts.filter((event) => !windowMs || event.t >= now - windowMs);
  const bucketMs = timeWindow === '24h' ? 60 * 60 * 1000 : timeWindow === 'all' ? 7 * 24 * 60 * 60 * 1000 : 24 * 60 * 60 * 1000;
  const buckets = new Map();
  const severityNames = { Critical: 'P1', Warning: 'P2', Info: 'P3', Unknown: 'P4' };
  const eventsBySeverity = {};
  const eventsByCategory = {};
  const deviceCounts = new Map();
  const siteCounts = new Map();
  const stateCounts = new Map();
  const typeCounts = new Map();

  events.forEach((event) => {
    const bucketStart = Math.floor(event.t / bucketMs) * bucketMs;
    const bucketDate = new Date(bucketStart);
    const time = timeWindow === '24h'
      ? `${bucketDate.toISOString().slice(0, 13).replace('T', ' ')}:00:00`
      : bucketDate.toISOString().slice(0, 10);
    buckets.set(time, (buckets.get(time) || 0) + 1);
    const severity = severityNames[event.sev] || event.sev || 'Unknown';
    eventsBySeverity[severity] = (eventsBySeverity[severity] || 0) + 1;
    eventsByCategory[event.category || 'other'] = (eventsByCategory[event.category || 'other'] || 0) + 1;
    const device = event.d;
    deviceCounts.set(device.id, { device_id: device.id, device_name: device.name, event_count: (deviceCounts.get(device.id)?.event_count || 0) + 1 });

    const siteName = device.site || 'Unknown site';
    siteCounts.set(siteName, (siteCounts.get(siteName) || 0) + 1);
    const stateName = device.reg || 'Unknown';
    stateCounts.set(stateName, (stateCounts.get(stateName) || 0) + 1);
    const typeKey = `${event.event_type_name}|${severity}`;
    typeCounts.set(typeKey, (typeCounts.get(typeKey) || 0) + 1);
  });

  return {
    time_window: timeWindow,
    total_events: events.length,
    events_by_severity: eventsBySeverity,
    events_by_category: eventsByCategory,
    alert_volume: events.length,
    top_alerting_devices: [...deviceCounts.values()].sort((a, b) => b.event_count - a.event_count).slice(0, 20),
    events_by_status: {},
    events_trend: [...buckets].sort(([a], [b]) => a.localeCompare(b)).map(([time, count]) => ({ time, count })),
    busiest_sites: [...siteCounts]
      .map(([site_name, count]) => ({ site_name, site_code: site_name.slice(0, 3).toUpperCase(), count }))
      .sort((a, b) => b.count - a.count)
      .slice(0, 10),
    alerts_by_state: [...stateCounts]
      .map(([state, count]) => ({ state, count }))
      .sort((a, b) => b.count - a.count),
    top_event_types: [...typeCounts]
      .map(([key, count]) => {
        const [name, severity] = key.split('|');
        return { name, severity, count };
      })
      .sort((a, b) => b.count - a.count)
      .slice(0, 10),
  };
}

function demoRequest(path, { method = 'GET', body, query = {} } = {}) {
  if (path === '/auth/logout') {
    return null;
  }

  if (path === '/get-metrics') {
    return buildDemoMetrics(query.time_window || 'all');
  }

  if (path === '/get-logs') {
    const filtered = demoAlerts.filter((alert) => (
      (!query.device_id || String(alert.d.id).includes(String(query.device_id))
        || String(alert.d.name || "").toLowerCase().includes(String(query.device_id).toLowerCase()))
      && (!query.ip_address || String(alert.d.ip || "").includes(String(query.ip_address)))
      && (!query.event_id || String(alert.id) === String(query.event_id))
      && (!query.event_type_id || String(alert.event_type_id) === String(query.event_type_id))
      && (!query.severity || alert.sev === query.severity)
      && (!query.search || `${alert.msg} ${alert.event_type_name || ""} ${alert.d.name} ${alert.d.ip || ""}`
        .toLowerCase()
        .includes(String(query.search).toLowerCase()))
    ));
    const page = Number(query.page || 1);
    const pageSize = Number(query.page_size || 50);
    const pageAlerts = filtered.slice((page - 1) * pageSize, page * pageSize);

    return {
      total: filtered.length,
      page,
      page_size: pageSize,
      data: pageAlerts.map((alert) => ({
        event_id: alert.id,
        event_time: new Date(alert.t).toISOString(),
        event_type_id: alert.event_type_id,
        event_type_name: alert.event_type_name,
        severity: alert.sev,
        message: alert.msg,
        device_id: alert.d.id,
        device_name: alert.d.name,
        ip_address: alert.d.ip,
        site_code: null,
        category: alert.category || null,
        current_status: null,
        raw_detail: null,
      })),
    };
  }

  if (path === '/simulate/logs') {
    const count = Math.max(1, Math.min(50, Number(query.count || 10)));
    const shuffled = [...demoAlerts].sort(() => Math.random() - 0.5).slice(0, count);
    return { success: true, data: shuffled.map((alert) => ({
      event_id: alert.id,
      event_time: new Date(alert.t).toISOString(),
      event_type_id: alert.event_type_id,
      event_type_name: alert.event_type_name,
      severity: alert.sev,
      category: alert.category,
      message: alert.msg,
      device_id: alert.d.id,
      device_name: alert.d.name,
      ip_address: alert.d.ip,
      simulated: true,
    })), meta: { total_returned: shuffled.length, real_count: 0, synthetic_count: shuffled.length } };
  }

  if (path === '/error-info') {
    const event = demoAlerts.find((item) => String(item.id) === String(query.event_id));
    const device = demoDevices.find((item) => String(item.id) === String(event?.d.id))
      || demoDevices[0];

    return {
      device: {
        device_id: device.id,
        device_name: device.name,
        ip_address: device.ip,
        machine_type: 'Network switch',
      },
      event_type: {
        event_type_name: 'Node Down',
        severity: 'P2',
        category: 'connectivity',
      },
      historical_info: {
        total_incidents_6m: 2,
        last_event_id: demoAlerts[0]?.id ?? null,
        related_tickets: [
          {
            ticket_number: 'INC0010001',
            ticket_type: 'INC',
            state: 'Closed',
            created_on: new Date(Date.now() - 2 * 864e5).toISOString(),
            updated_on: new Date(Date.now() - 864e5).toISOString(),
            closed_at: null,
            short_description: 'Node down on core switch',
            description: 'Core switch stopped responding to ICMP checks.',
            work_notes: 'Escalated to the network team; uplink replaced.',
            severity: 'P2',
            frequency: 3,
            device_type: 'Switch',
            device_name: device.name,
            ip_address: device.ip,
            device_id: device.id,
            event_time: new Date(event?.t ?? Date.now()).toISOString(),
            event_type_name: 'Node Down',
            event_message: event?.msg || 'Node Down',
            last_event_id: demoAlerts[0]?.id ?? null,
          },
        ],
        recent_event_logs: demoAlerts.slice(0, 4).map((item) => ({
          event_id: item.id,
          event_time: new Date(item.t).toISOString(),
          event_type_name: item.event_type_name,
          message: item.msg,
          current_status: null,
          raw_detail: null,
        })),
      },
      preliminary_checks: {
        ping: { host: device.ip, reachable: true, packet_loss_pct: 0 },
        traceroute: { host: device.ip, completed: true },
        nslookup: { host: device.ip, addresses: [device.ip], reverse_lookup: 'demo-network.local' },
      },
      suggested_solution: {
        generated_by: 'demo',
        confidence: 'medium',
        hypothesis: 'Intermittent connectivity issue detected in demo data.',
        recommended_steps: [
          'Review device event history.',
          'Check interface counters.',
          'Re-run diagnostics after remediation.',
        ],
      },
    };
  }

  if (path.startsWith('/internal/')) {
    const host = body?.host || '127.0.0.1';

    if (path.endsWith('/ping')) {
      return { host, reachable: true, packet_loss_pct: 0, avg_rtt_ms: 12 };
    }
    if (path.endsWith('/traceroute')) {
      return { host, hops: [{ hop: 1, address: host, rtt_ms: 12 }], completed: true };
    }

    return { host, addresses: [host], reverse_lookup: 'demo-network.local' };
  }

  if (path === '/auth/signup') {
    if (method !== 'POST') return null;
    return {
      success: true,
      message: 'Account created successfully',
      data: {
        user: {
          id: Math.floor(Date.now() % 100000),
          username: String(body?.username || 'user').toLowerCase(),
          email: body?.email || '',
          role: String(body?.role || 'analyst').toLowerCase(),
          is_active: 1,
          created_at: new Date().toISOString(),
        },
        tokens: null,
      },
    };
  }

  if (path === '/auth/me') {
    const session = readSession() || {};
    return {
      success: true,
      message: 'OK',
      data: {
        id: session.sub ?? 'demo',
        username: session.username || 'demo',
        email: session.username || 'demo@networkops.com',
        role: session.role || 'ANALYST',
        is_active: true,
        created_at: null,
      },
    };
  }

  if (path === '/sites') {
    const states = [
      { state: 'East', sites: 2, alerts: 6, p1: 1 },
      { state: 'West', sites: 3, alerts: 9, p1: 2 },
      { state: 'South', sites: 2, alerts: 5, p1: 0 },
    ];
    const data = SITES.map(([label, state], index) => ({
      code: `SITE-${100 + index}`,
      label,
      city: label,
      state,
      address: `${label} Data Center`,
      devices: 3,
      alerts: 4 + index,
      p1: index % 3,
      tickets: index % 4,
      last_event: new Date(Date.now() - index * 3600e3).toISOString(),
    })).filter((site) => (!query.q || site.label.toLowerCase().includes(String(query.q).toLowerCase()))
    && (!query.state || site.state === query.state));

    return {
      success: true,
      message: 'OK',
      data,
      meta: { total: data.length, page: Number(query.page || 1), page_size: Number(query.page_size || 50), total_pages: 1 },
      states,
    };
  }

  if (path.startsWith('/sites/')) {
    const code = decodeURIComponent(path.replace('/sites/', ''));
    const siteIndex = SITES.findIndex((_, index) => `SITE-${100 + index}` === code);
    const site = SITES[siteIndex >= 0 ? siteIndex : 0];
    return {
      success: true,
      message: 'OK',
      data: {
        site: { code, label: site[0], city: site[0], state: site[1], address: `${site[0]} Data Center` },
        devices: demoDevices.slice(0, 5).map((device) => ({ device_id: device.id, device_name: device.name, machine_type: 'Switch', ip_address: device.ip, event_count: 3 })),
        by_category: [{ category: 'connectivity', n: 5 }, { category: 'performance', n: 3 }],
        by_day: [{ day: new Date().toISOString().slice(0, 10), n: 4, p1: 1 }],
        tickets: [],
        recent: demoAlerts.slice(0, 5).map((alert) => ({ id: alert.id, ts: new Date(alert.t).toISOString(), name: alert.msg, severity: alert.sev, category: alert.category, device_name: alert.d.name, status: 1, message: alert.msg })),
      },
    };
  }

  if (path === '/tickets') {
    const kinds = [{ kind: 'INC', n: 3 }, { kind: 'RITM', n: 2 }];
    const statuses = [{ state: 'Open', n: 3 }, { state: 'Closed', n: 2 }];
    const data = demoAlerts.slice(0, 6).map((alert, index) => ({
      ticket_id: index + 1,
      ticket_number: `INC00${1000 + index}`,
      ticket_type: index % 2 ? 'RITM' : 'INC',
      state: index % 2 ? 'Open' : 'Closed',
      assignment_group: 'NOC',
      created_on: new Date(alert.t).toISOString(),
      closed_at: null,
      short_description: alert.msg,
      links: 1,
      best_link: 0.82,
    }));
    return {
      success: true,
      message: 'OK',
      data,
      meta: { total: data.length, page: Number(query.page || 1), page_size: Number(query.page_size || 50), total_pages: 1 },
      kinds,
      statuses,
    };
  }

  if (path.startsWith('/tickets/')) {
    const number = decodeURIComponent(path.replace('/tickets/', ''));
    return {
      success: true,
      message: 'OK',
      data: {
        ticket: {
          ticket_id: 1, ticket_number: number, ticket_type: 'INC', state: 'Open',
          short_description: 'Node down on core switch', description: 'Demo ticket description.',
          work_notes: 'Engineer dispatched.', created_on: new Date().toISOString(), closed_at: null,
          extracted_site_codes: [], extracted_ips: [], extracted_device_names: [],
        },
        links: [],
      },
    };
  }

  if (path === '/solution-summaries') {
    if (method === 'POST') {
      return { success: true, message: 'Solution summary saved', data: { event_id: body?.event_id, ...body } };
    }
    return { success: true, message: 'OK', data: [] };
  }

  if (path.startsWith('/solution-summaries/')) {
    if (method === 'DELETE') return { success: true, message: 'deleted', data: null };
    return { success: true, message: 'OK', data: null };
  }

  if (['/admin/ingest-excel', '/admin/ingest/error-csv', '/admin/ingest/ticket-csv'].includes(path) && method === 'POST') {
    return {
      success: true,
      message: 'File accepted. Job 1 is queued for processing.',
      data: { id: 1, filename: 'demo.csv', status: 'queued', rows_processed: 0, triggered_by: 'demo' },
    };
  }

  if (path === '/admin/ingest-jobs') {
    return { success: true, message: 'OK', data: [], meta: { total: 0, page: 1, page_size: 50, total_pages: 1 } };
  }

  if (path.startsWith('/admin/ingest-excel/')) {
    return {
      success: true,
      message: 'OK',
      data: { id: Number(path.split('/').pop()), filename: 'demo.csv', status: 'succeeded', rows_processed: 120, progress: 100, stage: 'complete' },
    };
  }

  if (path === '/admin/activity-log') {
    if (method === 'POST') return { success: true, message: 'Activity log entry created', data: { id: 1 } };
    return { success: true, message: 'OK', data: [], meta: { total: 0, page: Number(query.page || 1), page_size: Number(query.page_size || 25), total_pages: 1 } };
  }

  throw new Error(`Endpoint ${path} is unavailable in offline demo mode.`);
}

function readSession() {
  try {
    return JSON.parse(localStorage.getItem(STORAGE_KEY) || sessionStorage.getItem(STORAGE_KEY) || 'null');
  } catch {
    return null;
  }
}

function saveSession(session, remember) {
  clearSession();
  const storage = remember ? localStorage : sessionStorage;
  storage.setItem(STORAGE_KEY, JSON.stringify(session));
}

export function restore() {
  return readSession();
}

export function clearSession() {
  localStorage.removeItem(STORAGE_KEY);
  sessionStorage.removeItem(STORAGE_KEY);
}

async function request(path, { method = 'GET', body, auth = true, query } = {}) {
  if (auth && readSession()?.isDemo) {
    return demoRequest(path, { method, body, query });
  }

  const url = new URL(`${BASE_URL}${path}`, window.location.origin);
  Object.entries(query || {}).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== '') url.searchParams.set(key, value);
  });
  const headers = new Headers({ Accept: 'application/json' });

  if (body != null && !(body instanceof FormData)) {
    const contentType = body instanceof URLSearchParams
      ? 'application/x-www-form-urlencoded'
      : 'application/json';
    headers.set('Content-Type', contentType);
  }

  if (auth) {
    const token = readSession()?.accessToken;
    if (token) headers.set('Authorization', `Bearer ${token}`);
  }

  const requestBody = body == null || body instanceof FormData || body instanceof URLSearchParams
    ? body
    : JSON.stringify(body);
  let response;

  try {
    response = await fetch(url, {
      method,
      headers,
      body: requestBody ?? undefined,
    });
  } catch {
    throw new Error(
      `Cannot reach the API at ${CONFIGURED_API_URL}. Check that the backend is running and VITE_API_BASE_URL is correct.`,
    );
  }

  const responseText = response.status === 204 ? '' : await response.text();
  let payload = null;
  if (responseText) {
    try {
      payload = JSON.parse(responseText);
    } catch {
      // Keep plain-text proxy/server errors visible instead of replacing them
      // with a generic HTTP status message.
      payload = { message: responseText.slice(0, 1000) };
    }
  }

  if (response.status === 401 && auth) {
    clearSession();
    window.dispatchEvent(new Event('naap:unauthorized'));
  }

  if (!response.ok || payload?.success === false) {
    const raw = payload?.message || payload?.detail || `Request failed (${response.status})`;
    const base = typeof raw === 'string' ? raw : `Request failed (${response.status})`;
    // FastAPI validation failures arrive as details.validation_errors — surface
    // the field and reason instead of a bare "Request validation failed".
    const validation = Array.isArray(payload?.details?.validation_errors)
      ? payload.details.validation_errors.map((entry) => {
          const field = (entry.loc || []).slice(1).join('.') || entry.type || 'field';
          return `${field}: ${entry.msg}`;
        })
      : [];
    const message = validation.length ? `${base} — ${validation.join('; ')}` : base;
    const error = new Error(message);
    error.status = response.status;
    error.details = payload?.details;
    throw error;
  }
  return payload;
}

// The backend validates role against lowercase 'admin' | 'analyst' and rejects
// anything else with a 422, so normalise before the request leaves the client.
function normalizeRole(role) {
  return String(role || '').toLowerCase() === 'admin' ? 'admin' : 'analyst';
}

function mapUser(user, tokens) {
  const role = String(user?.role || '').toUpperCase();
  return {
    sub: String(user?.id ?? user?.username ?? user?.email ?? ''),
    username: user?.username || user?.email || '',
    name: user?.full_name || user?.username || user?.email || 'User',
    role: role === 'ADMIN' ? 'ADMIN' : 'ANALYST',
    accessToken: tokens?.access_token,
    refreshToken: tokens?.refresh_token,
  };
}

function mapAuthResponse(response) {
  const data = response?.data ?? response;
  return mapUser(data?.user, data?.tokens ?? data);
}

export async function login(username, password, remember, useDemo = false) {
  const key = username.trim().toLowerCase();
  if (useDemo) {
    const localAccount = key === 'admin' && password === 'admin123'
      ? { username: 'admin', name: 'Demo Admin', role: 'ADMIN' }
      : USERS[key]?.p === password
        ? { username: key, name: USERS[key].name, role: USERS[key].role }
        : null;
    if (!localAccount) throw new Error('Select an offline demo account to use demo login.');
    const session = {
      sub: localAccount.username,
      username: localAccount.username,
      name: localAccount.name,
      role: localAccount.role,
      accessToken: null,
      refreshToken: null,
      isDemo: true,
    };
    saveSession(session, remember);
    return session;
  }

  const response = await request('/auth/login', {
    method: 'POST',
    body: { username, password },
    auth: false,
  });
  const session = mapAuthResponse(response);
  saveSession(session, remember);
  return session;
}

export async function signup({ username, email, password, role = 'analyst' }, remember = true) {
  const response = await request('/auth/signup', {
    method: 'POST',
    auth: false,
    body: { username, email, password, role: normalizeRole(role) },
  });
  const session = mapAuthResponse(response);
  saveSession(session, remember);
  return session;
}

export async function createUser({ username, email, password, role = 'analyst' }) {
  const response = await request('/auth/signup', {
    method: 'POST',
    auth: true,
    body: { username, email, password, role: normalizeRole(role) },
  });
  return mapAuthResponse(response);
}

export async function logout() {
  try {
    await request('/auth/logout', {
      method: 'POST',
      body: { refresh_token: readSession()?.refreshToken || null },
    });
  } finally {
    clearSession();
    clearCache();
  }
}


// Response caching lives in the store (src/services/cache.js). Keep getMetrics
// and getLogs as pure transport + shape normalisation.
export const getMetrics = async (params = {}) => {
  const response = await request('/get-metrics', { query: params });
  return response?.data ?? response;
};

export const getLogs = async (params = {}) => {
  const response = await request('/get-logs', { query: params });
  const data = response?.data ?? response;
  if (Array.isArray(data)) {
    return {
      data,
      total: response?.total ?? response?.meta?.total ?? data.length,
      page: response?.page ?? response?.meta?.page ?? params.page ?? 1,
      page_size: response?.page_size ?? response?.meta?.page_size ?? params.page_size ?? data.length,
    };
  }
  if (!Array.isArray(data?.data)) return data;
  return {
    ...data,
    data: data.data,
    total: data.total ?? data.meta?.total ?? data.meta?.total_returned ?? data.data.length,
    page: data.page ?? data.meta?.page ?? params.page ?? 1,
    page_size: data.page_size ?? data.meta?.page_size ?? params.page_size ?? data.data.length,
  };
};

export const getSimulatedLogs = async (params = {}) => {
  const response = await request('/simulate/logs', { query: params });
  const data = response?.data ?? response;
  return Array.isArray(data) ? data : Array.isArray(data?.data) ? data.data : [];
};

export const getErrorInfo = async (eventOrId) => {
  let eventId = eventOrId;
  while (eventId && typeof eventId === 'object') {
    eventId = eventId.event_id ?? eventId.id;
  }
  const numericEventId = Number(eventId);
  if (!Number.isSafeInteger(numericEventId)) {
    throw new Error('Cannot load event details because the selected event has no valid event ID.');
  }
  const response = await request('/error-info', { query: { event_id: numericEventId } });
  return response?.data ?? response;
};

export const runDiagnostic = async (kind, body) => {
  const response = await request(`/internal/${kind}`, { method: 'POST', body });
  return response?.data ?? response;
};

// ---------------------------------------------------------------------------
// Auth
// ---------------------------------------------------------------------------

export const getMe = async () => {
  const response = await request('/auth/me');
  return response?.data ?? response;
};

// ---------------------------------------------------------------------------
// List envelope helper
// ---------------------------------------------------------------------------

// Backend list endpoints return { success, data: [...], meta: {...}, <extras> }.
// Normalise that into a single { data, total, page, page_size, total_pages } shape.
function unwrapList(response, params = {}, extras = []) {
  const data = Array.isArray(response?.data) ? response.data : response?.data?.data ?? [];
  const meta = response?.meta || response?.data?.meta || {};
  const out = {
    data,
    total: meta.total ?? response?.total ?? data.length,
    page: meta.page ?? params.page ?? 1,
    page_size: meta.page_size ?? params.page_size ?? 50,
    total_pages: meta.total_pages ?? 1,
  };
  extras.forEach((key) => {
    const value = response?.[key] ?? response?.data?.[key];
    out[key] = Array.isArray(value) ? value : [];
  });
  return out;
}

// ---------------------------------------------------------------------------
// Sites  — GET /sites, GET /sites/{code}
// ---------------------------------------------------------------------------

export const getSites = async (params = {}) => {
  const response = await request('/sites', { query: params });
  return unwrapList(response, params, ['states']);
};

export const getSite = async (code) => {
  const response = await request(`/sites/${encodeURIComponent(code)}`);
  return response?.data ?? response;
};

// ---------------------------------------------------------------------------
// Tickets — GET /tickets, GET /tickets/{number}
// ---------------------------------------------------------------------------

export const getTickets = async (params = {}) => {
  const response = await request('/tickets', { query: params });
  return unwrapList(response, params, ['kinds', 'statuses']);
};

export const getTicket = async (number) => {
  const response = await request(`/tickets/${encodeURIComponent(number)}`);
  return response?.data ?? response;
};

// ---------------------------------------------------------------------------
// Solution summaries — /solution-summaries
// ---------------------------------------------------------------------------

export const getSolutionSummaries = async (params = {}) => {
  const response = await request('/solution-summaries', { query: params });
  return Array.isArray(response?.data) ? response.data : [];
};

export const getSolutionSummary = async (eventId) => {
  const response = await request(`/solution-summaries/${encodeURIComponent(eventId)}`);
  return response?.data ?? response;
};

export const saveSolutionSummary = async (body) => {
  const response = await request('/solution-summaries', { method: 'POST', body });
  return response?.data ?? response;
};

export const deleteSolutionSummary = async (eventId) => {
  await request(`/solution-summaries/${encodeURIComponent(eventId)}`, { method: 'DELETE' });
  return true;
};

// ---------------------------------------------------------------------------
// Admin
// ---------------------------------------------------------------------------

export const getActivityLog = async (params = {}) => {
  const response = await request('/admin/activity-log', { query: params });
  return unwrapList(response, params);
};

export const createActivityLog = async (body) => {
  const response = await request('/admin/activity-log', { method: 'POST', body });
  return response?.data ?? response;
};

// kind: 'excel' (auto-detect, primary), 'error', or 'ticket'.
export const ingestDataFile = async (file, kind = 'excel') => {
  const path = kind === 'error'
    ? '/admin/ingest/error-csv'
    : kind === 'ticket'
      ? '/admin/ingest/ticket-csv'
      : '/admin/ingest-excel';
  const body = new FormData();
  body.append('file', file);
  const response = await request(path, { method: 'POST', body });
  const data = response?.data ?? response;
  return { ...data, job_id: data?.id, message: response?.message ?? data?.message };
};

// Backwards-compatible alias — auto-detecting Excel/CSV upload.
export const ingestFile = (file) => ingestDataFile(file, 'excel');

export const getIngestJob = async (jobId) => {
  const response = await request(`/admin/ingest-excel/${encodeURIComponent(jobId)}`);
  return response?.data ?? response;
};

export const getIngestJobs = async (params = {}) => {
  const response = await request('/admin/ingest-jobs', { query: { page_size: 50, ...params } });
  return unwrapList(response, { page_size: 50, ...params });
};
