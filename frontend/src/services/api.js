 import { makeDevices, seedAlerts, USERS } from '../mock/data';

const DEFAULT_API_URL = 'http://localhost:8000';
const CONFIGURED_API_URL = (import.meta.env.VITE_API_BASE_URL || DEFAULT_API_URL)
  .replace(/\/health\/?$/, '')
  .replace(/\/$/, '');
// Use Vite's same-origin proxy in development to avoid ngrok/CORS preflight issues.
const BASE_URL = import.meta.env.DEV ? '' : CONFIGURED_API_URL;
const STORAGE_KEY = 'naap.session';
const demoDevices = makeDevices();
const demoAlerts = seedAlerts(demoDevices).map((alert, index) => ({
  ...alert,
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
  });

  return {
    time_window: timeWindow,
    total_events: events.length,
    events_by_severity: eventsBySeverity,
    events_by_category: eventsByCategory,
    top_alerting_devices: [...deviceCounts.values()].sort((a, b) => b.event_count - a.event_count).slice(0, 20),
    events_by_status: {},
    events_trend: [...buckets].sort(([a], [b]) => a.localeCompare(b)).map(([time, count]) => ({ time, count })),
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
      (!query.device_id || String(alert.d.id).includes(String(query.device_id)))
      && (!query.event_type_id || String(alert.event_type_id) === String(query.event_type_id))
      && (!query.severity || alert.sev === query.severity)
      && (!query.search || `${alert.msg} ${alert.d.name}`
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
        severity: 'Warning',
        category: 'connectivity',
      },
      historical_info: { total_incidents_6m: 2, related_tickets: [] },
      preliminary_checks: {
        ping: { host: device.ip, reachable: true, packet_loss_pct: 0 },
        traceroute: { host: device.ip, completed: true },
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

  if (path === '/admin/ingest-excel' && method === 'POST') {
    return { message: 'File accepted for demo ingestion.', job_id: 1 };
  }

  if (path === '/admin/activity-log') {
    return { total: 0, page: Number(query.page || 1), page_size: Number(query.page_size || 25), data: [] };
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
    const message = payload?.message || payload?.detail || `Request failed (${response.status})`;
    const error = new Error(message);
    error.status = response.status;
    error.details = payload?.details;
    throw error;
  }
  return payload;
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
    body: { username, email, password, role },
  });
  const session = mapAuthResponse(response);
  saveSession(session, remember);
  return session;
}

export async function logout() {
  try {
    await request('/auth/logout', {
      method: 'POST',
      body: { refresh_token: readSession()?.refreshToken || null },
    });
  } finally {
    clearSession();
  }
}

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

export const ingestFile = async (file) => {
  const body = new FormData();
  body.append('file', file);
  const response = await request('/admin/ingest-excel', { method: 'POST', body });
  const data = response?.data ?? response;
  return { ...data, job_id: data?.job_id ?? data?.id };
};

export const getActivityLog = async (params = {}) => {
  const response = await request('/admin/activity-log', { query: params });
  const data = response?.data ?? response;
  if (Array.isArray(data)) {
    return {
      data,
      total: response?.total ?? response?.meta?.total ?? data.length,
      page: response?.page ?? response?.meta?.page ?? params.page ?? 1,
    };
  }
  if (!Array.isArray(data?.data)) return data;
  return {
    ...data,
    data: data.data,
    total: data.total ?? data.meta?.total ?? data.data.length,
    page: data.page ?? data.meta?.page ?? params.page ?? 1,
  };
};
