import { useEffect, useState } from 'react';
import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom';
import { active, useStore } from '../store';
import Logo from '../components/Logo';

const NAV = [
  ['/dashboard', 'Executive Dashboard', 'Ferguson Network Operations', 'dashboard'],
  ['/alerts', 'Alerts Console', 'Alert Investigation', 'alerts'],
  ['/admin', 'Admin Panel', 'System Administration', 'admin'],
];

function NavIcon({ name }) {
  const common = {
    width: 18,
    height: 18,
    viewBox: '0 0 24 24',
    fill: 'none',
    stroke: 'currentColor',
    strokeWidth: 1.8,
    strokeLinecap: 'round',
    strokeLinejoin: 'round',
    'aria-hidden': true,
  };

  if (name === 'dashboard') {
    return <svg {...common}><rect x="3" y="3" width="8" height="8" rx="1" /><rect x="13" y="3" width="8" height="5" rx="1" /><rect x="13" y="10" width="8" height="11" rx="1" /><rect x="3" y="13" width="8" height="8" rx="1" /></svg>;
  }
  if (name === 'alerts') {
    return <svg {...common}><path d="M18 9a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9" /><path d="M10 21h4" /></svg>;
  }
  return <svg {...common}><circle cx="12" cy="12" r="3" /><path d="m19.4 15 .1.1 1.4 1.1-1.4 2.4-1.7-.6a8 8 0 0 1-1.5.9L16 21h-3l-.4-2.1a8 8 0 0 1-1.6-.9l-1.7.6-1.4-2.4 1.5-1.1a7 7 0 0 1 0-1.8L7.9 12l1.4-2.4 1.7.6a8 8 0 0 1 1.6-.9L13 7h3l.3 2.1a8 8 0 0 1 1.5.9l1.7-.6 1.4 2.4-1.4 1.1a7 7 0 0 1-.1 2.1Z" transform="translate(-1 -2)" /></svg>;
}

export default function AppLayout() {
  const {
    me,
    alerts,
    logout,
    toast,
    setMe,
    acknowledgedDeviceIds,
  } = useStore();
  const navigate = useNavigate();
  const location = useLocation();
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [isDark, setIsDark] = useState(() => document.documentElement.dataset.theme === 'dark');

  const toggleTheme = () => {
    const nextIsDark = !isDark;
    document.documentElement.dataset.theme = nextIsDark ? 'dark' : 'light';
    setIsDark(nextIsDark);
  };

  useEffect(() => {
    const closeProfileMenu = (event) => {
      const menu = document.querySelector('.pm');
      if (menu && !menu.contains(event.target)) {
        menu.removeAttribute('open');
      }
    };

    const handleUnauthorized = () => {
      setMe(null);
      navigate('/login', { replace: true });
    };

    document.addEventListener('click', closeProfileMenu);
    window.addEventListener('naap:unauthorized', handleUnauthorized);

    return () => {
      document.removeEventListener('click', closeProfileMenu);
      window.removeEventListener('naap:unauthorized', handleUnauthorized);
    };
  }, [navigate, setMe]);

  const items = me.role === 'ADMIN'
    ? NAV
    : NAV.filter(([path]) => ['/dashboard', '/alerts'].includes(path));
  const isAlertDetail = /^\/alerts\/event\/[^/]+/.test(location.pathname);
  const currentPage = NAV.find(([path]) => path === location.pathname) || (isAlertDetail ? null : NAV[0]);
  const priorityOneSeverity = alerts.some((alert) => alert.sev === 'P1') ? 'P1' : 'Critical';
  const criticalDeviceIds = [...new Set(active(alerts)
    .filter((alert) => alert.sev === priorityOneSeverity)
    .map((alert) => String(alert.d.id)))];
  const openCriticalDeviceCount = criticalDeviceIds
    .filter((deviceId) => !acknowledgedDeviceIds.includes(deviceId)).length;

  const [topSearch, setTopSearch] = useState('');

  const handleTopSearch = (event) => {
    event.preventDefault();
    const query = topSearch.trim();
    if (!query) return;
    
    // Check if numeric (event_id)
    if (/^\d+$/.test(query)) {
      navigate(`/alerts?event_id=${encodeURIComponent(query)}`);
    } else {
      navigate(`/alerts?search=${encodeURIComponent(query)}`);
    }
    setTopSearch(''); // clear after search
  };

  return (
    <>
      <header>
        <div className="lg"><Logo /></div>
        
        <form className="header-search-form" onSubmit={handleTopSearch}>
          <input
            className="sr header-search-input"
            placeholder="Search alerts, devices..."
            value={topSearch}
            onChange={(event) => setTopSearch(event.target.value)}
          />
          {topSearch && (
            <button
              type="button"
              className="header-search-clear"
              onClick={() => setTopSearch('')}
              aria-label="Clear search"
            >
              <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><path d="M18 6 6 18M6 6l12 12"/></svg>
            </button>
          )}
        </form>

        <span style={{ flex: 1 }} />
        <button
          aria-label={`${openCriticalDeviceCount} unacknowledged ${priorityOneSeverity} devices`}
          title={`Unacknowledged ${priorityOneSeverity} devices`}
          onClick={() => navigate(`/alerts?severity=${encodeURIComponent(priorityOneSeverity)}&acknowledged=false`)}
        >
          <svg aria-hidden="true" viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="1.8">
            <path d="M18 9a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9" />
            <path d="M10 21h4" />
          </svg>
          <span>{openCriticalDeviceCount}</span>
        </button>
        <button
          className={`theme-cycle${isDark ? ' is-dark' : ''}`}
          type="button"
          onClick={toggleTheme}
          aria-label={`Switch to ${isDark ? 'light' : 'dark'} theme`}
          aria-pressed={isDark}
          title={`Switch to ${isDark ? 'light' : 'dark'} theme`}
        >
          <span className="theme-cycle-sun" />
          <span className="theme-cycle-moon" />
          <i className="theme-cycle-star theme-cycle-star-one" />
          <i className="theme-cycle-star theme-cycle-star-two" />
        </button>
        <details className="pm">
          <summary className="av">
            {me.name.split(' ').map((word) => word[0]).join('')}
          </summary>
          <div className="pd">
            <b>{me.name} | {me.role === 'ADMIN' ? 'Admin' : 'NOC Analyst'}</b>
            <button
              onClick={() => {
                logout();
                navigate('/login');
              }}
            >
              Sign out
            </button>
          </div>
        </details>
      </header>

      <div className={`shell${sidebarCollapsed ? ' sidebar-collapsed' : ''}`}>
        <nav>
          <div className="sidebar-heading">
            <span className="sidebar-heading-label">{sidebarCollapsed ? 'OPS' : 'OPERATIONS'}</span>
            <button
              className="sidebar-toggle"
              type="button"
              aria-label={sidebarCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
              title={sidebarCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
              onClick={() => setSidebarCollapsed((collapsed) => !collapsed)}
            >
              <svg aria-hidden="true" viewBox="0 0 24 24" width="17" height="17" fill="none" stroke="currentColor" strokeWidth="2">
                <path d={sidebarCollapsed ? 'm9 18 6-6-6-6' : 'm15 18-6-6 6-6'} />
              </svg>
            </button>
          </div>
          {items.map(([path, label, , icon]) => (
            <NavLink
              key={path}
              to={path}
              title={sidebarCollapsed ? label : undefined}
              className={({ isActive }) => isActive ? 'on' : ''}
            >
              <span className="nav-icon"><NavIcon name={icon} /></span>
              <span className="nav-label">{label}</span>
            </NavLink>
          ))}
        </nav>
        <div className="ct">
          {currentPage && <div className="banner">
            <small>{currentPage[2]}</small>
            <div className="bt"><h2>{currentPage[1]}</h2></div>
          </div>}
          <main><Outlet /></main>
        </div>
      </div>

      <div id="toast" className={toast ? 'on' : ''}>{toast}</div>
    </>
  );
}
