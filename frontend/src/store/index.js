import { create } from 'zustand';
import {
  clearSession,
  getLogs,
  getMetrics,
  logout as apiLogout,
  restore,
} from '../services/api';

const initialMe = restore();
const ACKNOWLEDGED_DEVICES_KEY = 'naap.acknowledged-devices';
let dashboardRequestId = 0;

function restoreAcknowledgedDevices() {
  try {
    return JSON.parse(localStorage.getItem(ACKNOWLEDGED_DEVICES_KEY) || '[]');
  } catch {
    return [];
  }
}

function normalizeLog(log) {
  const parsedTimestamp = Date.parse(log.event_time);
  let timestamp = parsedTimestamp;
  if (Number.isNaN(timestamp)) {
    const timeOnly = String(log.event_time || '').match(/^(\d{2}):(\d{2}):(\d{2})(?:\.(\d+))?$/);
    if (timeOnly) {
      const eventDate = new Date();
      eventDate.setHours(Number(timeOnly[1]), Number(timeOnly[2]), Number(timeOnly[3]), Number((timeOnly[4] || '').padEnd(3, '0').slice(0, 3) || 0));
      timestamp = eventDate.getTime();
    }
  }

  return {
    ...log,
    id: log.event_id,
    t: Number.isNaN(timestamp) ? Date.now() : timestamp,
    d: {
      id: log.device_id,
      name: log.device_name || `Device ${log.device_id}`,
      ip: log.ip_address || '',
      site: log.site || '',
      reg: log.region || '',
    },
    // Keep the backend's ticket priority label (for example, P1) intact instead
    // of replacing it with a friendly severity bucket such as Critical.
    sev: String(log.priority ?? log.severity ?? log.severity_level ?? 'Unknown'),
    msg: log.message || log.event_type_name || 'Network event',
    st: log.state || 'Open',
    who: log.assigned_to || 'N/A',
    event_type_id: log.event_type_id,
  };
}

function normalizeLogs(result, defaultPageSize) {
  return {
    alerts: (result?.data || []).map(normalizeLog),
    logTotal: result?.total || 0,
    logPage: result?.page || 1,
    logPageSize: result?.page_size || defaultPageSize,
  };
}

export const useStore = create((set) => ({
  me: initialMe,
  acknowledgedDeviceIds: restoreAcknowledgedDevices(),
  metrics: null,
  alerts: [],
  logTotal: 0,
  logPage: 1,
  logPageSize: 50,
  loadingMetrics: false,
  loadingLogs: false,
  error: '',
  toast: '',

  setMe: (me) => set({ me }),
  acknowledgeDevice: (deviceId) => set((state) => {
    const acknowledgedDeviceIds = [...new Set([...state.acknowledgedDeviceIds, String(deviceId)])];
    localStorage.setItem(ACKNOWLEDGED_DEVICES_KEY, JSON.stringify(acknowledgedDeviceIds));
    return { acknowledgedDeviceIds };
  }),
  reopenDevice: (deviceId) => set((state) => {
    const acknowledgedDeviceIds = state.acknowledgedDeviceIds.filter((id) => id !== String(deviceId));
    localStorage.setItem(ACKNOWLEDGED_DEVICES_KEY, JSON.stringify(acknowledgedDeviceIds));
    return { acknowledgedDeviceIds };
  }),

  logout: async () => {
    dashboardRequestId += 1;
    const pendingLogout = apiLogout();
    set({ me: null, metrics: null, alerts: [], error: '' });

    try {
      await pendingLogout;
    } catch {
      clearSession();
    }
  },

  say: (toast) => {
    set({ toast });
    setTimeout(() => set({ toast: '' }), 2500);
  },

  loadDashboard: (params = {}) => {
    const requestId = ++dashboardRequestId;
    set({ loadingMetrics: true, error: '' });
    return getMetrics(params).then((metrics) => {
      if (requestId === dashboardRequestId) set({ metrics, loadingMetrics: false });
      return metrics;
    }).catch((error) => {
      if (requestId === dashboardRequestId) set({ loadingMetrics: false, error: error.message });
      throw error;
    });
  },

  loadLogs: async (params = {}) => {
    set({ loadingLogs: true, error: '' });

    try {
      const result = await getLogs({ page: 1, page_size: 50, ...params });
      set({
        ...normalizeLogs(result, 50),
        loadingLogs: false,
      });
    } catch (error) {
      set({ loadingLogs: false, error: error.message });
      throw error;
    }
  },
}));

export const active = (alerts) => alerts.filter((alert) => alert.st !== 'Resolved');
