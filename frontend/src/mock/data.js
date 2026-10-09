export const SITES = [
  ['Atlanta', 'South'],
  ['Boston', 'East'],
  ['Denver', 'West'],
  ['Dallas', 'South'],
  ['Newark', 'East'],
  ['Seattle', 'West'],
  ['Phoenix', 'West'],
  ['Miami', 'South'],
];

export const MSG = [
  'Link down',
  'High latency',
  'Packet loss',
  'CPU spike',
  'BGP flap',
  'Port errors',
];

export const R = (a, b) => a + Math.floor(Math.random() * (b - a));
export const pick = (items) => items[R(0, items.length)];
export const sd = (id, k) => ((id * 9301 + k * 49297) % 233280) / 233280;

export const makeDevices = () =>
  Array.from({ length: 24 }, (_, index) => {
    const [site, region] = SITES[index % SITES.length];

    return {
      id: `DEV-${1000 + index}`,
      name: `SW-${site.slice(0, 3).toUpperCase()}-${String(index + 1).padStart(2, '0')}`,
      ip: `10.${R(1, 200)}.${R(1, 250)}.${R(1, 250)}`,
      site,
      reg: region,
    };
  });

let nextAlertId = 100;

export const makeAlert = (devices) => ({
  id: ++nextAlertId,
  t: Date.now(),
  d: pick(devices),
  sev: Math.random() < 0.2 ? 'Critical' : Math.random() < 0.6 ? 'Warning' : 'Info',
  msg: pick(MSG),
  st: 'Open',
  who: 'N/A',
});

export const seedAlerts = (devices) =>
  Array.from({ length: 24 }, (_, index) => ({
    ...makeAlert(devices),
    t: Date.now() - index * 6e5,
    st: index > 16 ? 'Resolved' : 'Open',
  }));

export const USERS = {
  'admin@networkops.com': { p: 'Admin@123', role: 'ADMIN', name: 'Admin User' },
  'analyst@networkops.com': { p: 'User@123', role: 'ANALYST', name: 'NOC Analyst' },
};
