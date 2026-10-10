import re
import os

app_layout_code = """import { useEffect, useState } from 'react';
import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom';
import { active, useStore } from '../store';
import Logo from '../components/Logo';
import { FaServer, FaBell, FaCog, FaSearch, FaMoon, FaSun, FaSignOutAlt, FaBars, FaTimes, FaUserCircle } from 'react-icons/fa';

const NAV = [
  ['/dashboard', 'Executive Dashboard', 'Ferguson Network Operations', 'dashboard'],
  ['/alerts', 'Alerts Console', 'Alert Investigation', 'alerts'],
  ['/admin', 'Admin Panel', 'System Administration', 'admin'],
];

function NavIcon({ name }) {
  if (name === 'dashboard') return <FaServer />;
  if (name === 'alerts') return <FaBell />;
  if (name === 'admin') return <FaCog />;
  return <FaServer />;
}

export default function AppLayout() {
  const { me, alerts, logout, toast, setMe, acknowledgedDeviceIds } = useStore();
  const navigate = useNavigate();
  const location = useLocation();
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [isDark, setIsDark] = useState(() => document.documentElement.dataset.theme === 'dark');
  const [topSearch, setTopSearch] = useState('');
  const [profileOpen, setProfileOpen] = useState(false);

  const toggleTheme = () => {
    const nextIsDark = !isDark;
    document.documentElement.dataset.theme = nextIsDark ? 'dark' : 'light';
    setIsDark(nextIsDark);
    if (nextIsDark) document.documentElement.classList.add('dark');
    else document.documentElement.classList.remove('dark');
  };

  useEffect(() => {
    const handleUnauthorized = () => {
      setMe(null);
      navigate('/login', { replace: true });
    };
    window.addEventListener('naap:unauthorized', handleUnauthorized);
    return () => window.removeEventListener('naap:unauthorized', handleUnauthorized);
  }, [navigate, setMe]);

  const items = me.role === 'ADMIN' ? NAV : NAV.filter(([path]) => ['/dashboard', '/alerts'].includes(path));
  const isAlertDetail = /^\\/alerts\\/event\\/[^/]+/.test(location.pathname);
  const currentPage = NAV.find(([path]) => path === location.pathname) || (isAlertDetail ? null : NAV[0]);
  const priorityOneSeverity = alerts.some((alert) => alert.sev === 'P1') ? 'P1' : 'Critical';
  const criticalDeviceIds = [...new Set(active(alerts)
    .filter((alert) => alert.sev === priorityOneSeverity)
    .map((alert) => String(alert.d.id)))];
  const openCriticalDeviceCount = criticalDeviceIds
    .filter((deviceId) => !acknowledgedDeviceIds.includes(deviceId)).length;

  const handleTopSearch = (event) => {
    event.preventDefault();
    const query = topSearch.trim();
    if (!query) return;
    if (/^\\d+$/.test(query)) {
      navigate(`/alerts?event_id=${encodeURIComponent(query)}`);
    } else {
      navigate(`/alerts?search=${encodeURIComponent(query)}`);
    }
    setTopSearch('');
  };

  return (
    <div className="flex h-screen bg-gray-50 dark:bg-gray-900 text-gray-900 dark:text-gray-100 font-sans">
      <aside className={`flex flex-col bg-slate-800 text-white transition-all duration-300 ${sidebarCollapsed ? 'w-20' : 'w-64'} shadow-xl z-20`}>
        <div className="flex items-center justify-between p-4 border-b border-slate-700">
          {!sidebarCollapsed && (
            <div className="flex items-center gap-3 overflow-hidden whitespace-nowrap">
              <Logo className="w-8 h-8 text-blue-400" />
              <div className="flex flex-col">
                <span className="font-bold tracking-wide">NAAP</span>
                <span className="text-xs text-slate-400">NOC Portal</span>
              </div>
            </div>
          )}
          {sidebarCollapsed && <Logo className="w-8 h-8 text-blue-400 mx-auto" />}
        </div>

        <div className="flex-1 overflow-y-auto py-4">
          <div className="px-4 mb-2 text-xs font-semibold text-slate-400 uppercase tracking-wider">
            {!sidebarCollapsed ? 'Operations' : 'Ops'}
          </div>
          <nav className="space-y-1 px-2">
            {items.map(([path, label, , icon]) => (
              <NavLink
                key={path}
                to={path}
                title={sidebarCollapsed ? label : undefined}
                className={({ isActive }) => `flex items-center gap-3 px-3 py-2 rounded-md transition-colors ${isActive ? 'bg-blue-600 text-white' : 'text-slate-300 hover:bg-slate-700 hover:text-white'}`}
              >
                <NavIcon name={icon} />
                {!sidebarCollapsed && <span className="font-medium whitespace-nowrap">{label}</span>}
              </NavLink>
            ))}
          </nav>
        </div>

        <div className="p-4 border-t border-slate-700 flex items-center justify-center">
          <button
            onClick={() => setSidebarCollapsed(!sidebarCollapsed)}
            className="p-2 rounded hover:bg-slate-700 text-slate-400 hover:text-white transition-colors"
          >
            {sidebarCollapsed ? <FaBars /> : <FaTimes />}
          </button>
        </div>
      </aside>

      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        <header className="bg-white dark:bg-gray-800 shadow-sm border-b border-gray-200 dark:border-gray-700 z-10 flex items-center justify-between px-6 py-3">
          <div className="flex flex-col">
            {currentPage && (
              <>
                <span className="text-xs text-gray-500 dark:text-gray-400 font-medium uppercase">{currentPage[2]}</span>
                <h1 className="text-xl font-bold text-gray-800 dark:text-white">{currentPage[1]}</h1>
              </>
            )}
          </div>

          <div className="flex items-center gap-4">
            <form onSubmit={handleTopSearch} className="relative hidden md:block">
              <FaSearch className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
              <input
                type="text"
                placeholder="Search alerts, devices..."
                value={topSearch}
                onChange={(e) => setTopSearch(e.target.value)}
                className="pl-10 pr-4 py-2 bg-gray-100 dark:bg-gray-700 border-none rounded-full text-sm focus:ring-2 focus:ring-blue-500 w-64 transition-all"
              />
            </form>

            <button
              className={`relative p-2 rounded-full hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors ${openCriticalDeviceCount > 0 ? 'text-red-500' : 'text-gray-500'}`}
              onClick={() => navigate(`/alerts?severity=${encodeURIComponent(priorityOneSeverity)}&acknowledged=false`)}
            >
              <FaBell className="text-xl" />
              {openCriticalDeviceCount > 0 && (
                <span className="absolute top-0 right-0 inline-flex items-center justify-center px-2 py-1 text-xs font-bold leading-none text-white transform translate-x-1/4 -translate-y-1/4 bg-red-600 rounded-full">{openCriticalDeviceCount}</span>
              )}
            </button>

            <button
              onClick={toggleTheme}
              className="p-2 rounded-full hover:bg-gray-100 dark:hover:bg-gray-700 text-gray-500 dark:text-gray-400 transition-colors"
            >
              {isDark ? <FaSun className="text-xl" /> : <FaMoon className="text-xl" />}
            </button>

            <div className="relative">
              <button
                onClick={() => setProfileOpen(!profileOpen)}
                className="flex items-center gap-2 p-1 pr-2 rounded-full border border-gray-200 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors"
              >
                <div className="w-8 h-8 rounded-full bg-blue-500 text-white flex items-center justify-center font-bold">
                  {me.name.charAt(0)}
                </div>
              </button>

              {profileOpen && (
                <div className="absolute right-0 mt-2 w-48 bg-white dark:bg-gray-800 rounded-md shadow-lg py-1 border border-gray-200 dark:border-gray-700">
                  <div className="px-4 py-3 border-b border-gray-200 dark:border-gray-700">
                    <p className="text-sm font-medium text-gray-900 dark:text-white">{me.name}</p>
                    <p className="text-xs text-gray-500 dark:text-gray-400 truncate">{me.role === 'ADMIN' ? 'Administrator' : 'Analyst'}</p>
                  </div>
                  <button
                    onClick={() => {
                      setProfileOpen(false);
                      logout();
                      navigate('/login');
                    }}
                    className="w-full text-left px-4 py-2 text-sm text-red-600 hover:bg-gray-100 dark:hover:bg-gray-700 flex items-center gap-2"
                  >
                    <FaSignOutAlt /> Sign out
                  </button>
                </div>
              )}
            </div>
          </div>
        </header>

        <main className="flex-1 overflow-y-auto p-6 bg-gray-50 dark:bg-gray-900">
          <Outlet />
        </main>
      </div>
      {toast && (
        <div className="fixed bottom-4 right-4 bg-gray-800 text-white px-4 py-3 rounded shadow-lg z-50 animate-bounce">
          {toast}
        </div>
      )}
    </div>
  );
}
"""

with open('frontend/src/layouts/AppLayout.jsx', 'w') as f:
    f.write(app_layout_code)

admin_code = """import { useEffect, useState } from 'react';
import { getActivityLog, ingestFile, createUser } from '../services/api';
import { useStore } from '../store';
import { FaUserPlus, FaTimes, FaUpload, FaSync, FaChevronLeft, FaChevronRight, FaHistory, FaFileExcel } from 'react-icons/fa';

export default function Admin() {
  const say = useStore((state) => state.say);
  const [file, setFile] = useState(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('');
  const [activity, setActivity] = useState([]);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [error, setError] = useState('');
  
  const [showSignupModal, setShowSignupModal] = useState(false);
  const [signupForm, setSignupForm] = useState({ username: '', email: '', password: '', role: 'ANALYST' });
  const [signupBusy, setSignupBusy] = useState(false);
  const [signupMsg, setSignupMsg] = useState('');

  const loadActivity = (nextPage = page) => {
    getActivityLog({ page: nextPage, page_size: 15 })
      .then((result) => {
        setActivity(Array.isArray(result) ? result : result?.data || result?.items || []);
        setTotal(result?.total || 0);
        setPage(result?.page || nextPage);
      })
      .catch((requestError) => setError(requestError.message));
  };

  useEffect(() => {
    loadActivity(1);
  }, []);

  const upload = async (event) => {
    event.preventDefault();
    if (!file) return;

    const form = event.currentTarget;
    setBusy(true);
    setError('');
    setMessage('');

    try {
      const result = await ingestFile(file);
      const acceptedMessage = result?.message || 'File accepted for ingestion.';
      const jobId = result?.job_id ? ` Job ID: ${result.job_id}` : '';
      setMessage(`${acceptedMessage}${jobId}`);
      say('File accepted for ingestion');
      setFile(null);
      form.reset();
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setBusy(false);
    }
  };
  
  const handleSignup = async (e) => {
    e.preventDefault();
    setSignupBusy(true);
    setSignupMsg('');
    try {
      await createUser(signupForm);
      say(`User ${signupForm.username} created successfully!`);
      setShowSignupModal(false);
      setSignupForm({ username: '', email: '', password: '', role: 'ANALYST' });
    } catch (err) {
      setSignupMsg(err.message);
    } finally {
      setSignupBusy(false);
    }
  };

  return (
    <div className="space-y-6 max-w-6xl mx-auto">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold text-gray-800 dark:text-white">Administration Configuration</h2>
        <button
          onClick={() => setShowSignupModal(true)}
          className="flex items-center gap-2 bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-md font-medium transition-colors shadow-sm"
        >
          <FaUserPlus />
          <span>Add New User</span>
        </button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-1 space-y-6">
          <div className="bg-white dark:bg-gray-800 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700 overflow-hidden">
            <div className="px-5 py-4 border-b border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800/50">
              <h3 className="font-semibold text-gray-800 dark:text-white flex items-center gap-2">
                <FaFileExcel className="text-green-600" /> Data Ingestion
              </h3>
            </div>
            <div className="p-5">
              <form onSubmit={upload} className="space-y-4">
                <div className="border-2 border-dashed border-gray-300 dark:border-gray-600 rounded-md p-4 text-center">
                  <input
                    type="file"
                    accept=".csv,.xlsx"
                    required
                    onChange={(event) => setFile(event.target.files?.[0] || null)}
                    className="block w-full text-sm text-gray-500 dark:text-gray-400 file:mr-4 file:py-2 file:px-4 file:rounded-md file:border-0 file:text-sm file:font-semibold file:bg-blue-50 file:text-blue-700 hover:file:bg-blue-100 cursor-pointer"
                  />
                  <p className="mt-2 text-xs text-gray-500">Accepted formats: CSV and XLSX</p>
                </div>
                <button
                  disabled={!file || busy}
                  className={`w-full flex items-center justify-center gap-2 py-2 px-4 border border-transparent rounded-md shadow-sm text-sm font-medium text-white ${
                    !file || busy ? 'bg-blue-400 cursor-not-allowed' : 'bg-blue-600 hover:bg-blue-700'
                  } transition-colors`}
                >
                  <FaUpload />
                  {busy ? 'Uploading...' : 'Upload File'}
                </button>
              </form>
              
              {message && (
                <div className="mt-4 p-3 bg-green-50 dark:bg-green-900/30 text-green-700 dark:text-green-400 rounded-md text-sm">
                  {message}
                </div>
              )}
              {error && (
                <div className="mt-4 p-3 bg-red-50 dark:bg-red-900/30 text-red-700 dark:text-red-400 rounded-md text-sm">
                  {error}
                </div>
              )}
            </div>
          </div>
        </div>

        <div className="lg:col-span-2">
          <div className="bg-white dark:bg-gray-800 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700 overflow-hidden flex flex-col h-full">
            <div className="px-5 py-4 border-b border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800/50 flex justify-between items-center">
              <h3 className="font-semibold text-gray-800 dark:text-white flex items-center gap-2">
                <FaHistory className="text-gray-500" /> System Activity Log
              </h3>
              <button
                onClick={() => loadActivity(1)}
                className="text-sm flex items-center gap-1 text-gray-500 hover:text-blue-600 transition-colors"
              >
                <FaSync className={busy ? 'animate-spin' : ''} /> Refresh
              </button>
            </div>
            
            <div className="flex-1 p-0 overflow-x-auto">
              {error && <div className="m-4 p-3 bg-red-50 text-red-700 rounded-md text-sm">{error}</div>}
              
              <table className="min-w-full divide-y divide-gray-200 dark:divide-gray-700">
                <thead className="bg-gray-50 dark:bg-gray-900/50">
                  <tr>
                    <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">User</th>
                    <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Action</th>
                    <th scope="col" className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Time</th>
                  </tr>
                </thead>
                <tbody className="bg-white dark:bg-gray-800 divide-y divide-gray-200 dark:divide-gray-700">
                  {activity.length > 0 ? (
                    activity.map((item, index) => (
                      <tr key={item.id || `${item.timestamp}-${index}`} className="hover:bg-gray-50 dark:hover:bg-gray-700/50 transition-colors">
                        <td className="px-6 py-3 whitespace-nowrap text-sm font-medium text-gray-900 dark:text-white">
                          {item.username || item.user_id || 'System'}
                        </td>
                        <td className="px-6 py-3 whitespace-nowrap text-sm text-gray-500 dark:text-gray-300">
                          {item.endpoint_path || item.action || 'Action'}
                        </td>
                        <td className="px-6 py-3 whitespace-nowrap text-sm text-gray-500 dark:text-gray-400 text-right">
                          {new Date(item.created_at || item.timestamp).toLocaleString()}
                        </td>
                      </tr>
                    ))
                  ) : (
                    <tr>
                      <td colSpan="3" className="px-6 py-10 text-center text-sm text-gray-500">
                        No activity records found.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
            
            <div className="px-5 py-3 border-t border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800/50 flex items-center justify-between">
              <span className="text-sm text-gray-700 dark:text-gray-300">
                Page {page} <span className="text-gray-400 mx-1">|</span> {total.toLocaleString()} total records
              </span>
              <div className="flex gap-2">
                <button
                  disabled={page <= 1}
                  onClick={() => loadActivity(page - 1)}
                  className={`p-1.5 rounded-md border ${page <= 1 ? 'border-gray-200 text-gray-400 cursor-not-allowed' : 'border-gray-300 text-gray-700 hover:bg-gray-100'} bg-white dark:bg-gray-700 dark:border-gray-600 dark:text-gray-200 transition-colors`}
                >
                  <FaChevronLeft />
                </button>
                <button
                  disabled={page * 15 >= total}
                  onClick={() => loadActivity(page + 1)}
                  className={`p-1.5 rounded-md border ${page * 15 >= total ? 'border-gray-200 text-gray-400 cursor-not-allowed' : 'border-gray-300 text-gray-700 hover:bg-gray-100'} bg-white dark:bg-gray-700 dark:border-gray-600 dark:text-gray-200 transition-colors`}
                >
                  <FaChevronRight />
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>

      {showSignupModal && (
        <div className="fixed inset-0 z-50 overflow-y-auto">
          <div className="flex items-end justify-center min-h-screen pt-4 px-4 pb-20 text-center sm:block sm:p-0">
            <div className="fixed inset-0 transition-opacity" aria-hidden="true">
              <div className="absolute inset-0 bg-gray-500 dark:bg-gray-900 opacity-75 backdrop-blur-sm" onClick={() => setShowSignupModal(false)}></div>
            </div>
            <span className="hidden sm:inline-block sm:align-middle sm:h-screen" aria-hidden="true">&#8203;</span>
            <div className="inline-block align-bottom bg-white dark:bg-gray-800 rounded-lg text-left overflow-hidden shadow-xl transform transition-all sm:my-8 sm:align-middle sm:max-w-md w-full border border-gray-200 dark:border-gray-700">
              <div className="px-6 py-4 border-b border-gray-200 dark:border-gray-700 flex justify-between items-center">
                <h3 className="text-lg leading-6 font-medium text-gray-900 dark:text-white flex items-center gap-2">
                  <FaUserPlus className="text-blue-500" /> Create System User
                </h3>
                <button
                  onClick={() => setShowSignupModal(false)}
                  className="text-gray-400 hover:text-gray-500 focus:outline-none transition-colors"
                >
                  <FaTimes />
                </button>
              </div>
              <form onSubmit={handleSignup}>
                <div className="px-6 py-5 space-y-4">
                  {signupMsg && (
                    <div className="p-3 bg-red-50 text-red-700 rounded-md text-sm border border-red-200">
                      {signupMsg}
                    </div>
                  )}
                  <div>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Username</label>
                    <input
                      required
                      type="text"
                      value={signupForm.username}
                      onChange={e => setSignupForm({...signupForm, username: e.target.value})}
                      className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500 sm:text-sm dark:bg-gray-700 dark:text-white"
                      placeholder="e.g. jdoe"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Email Address</label>
                    <input
                      required
                      type="email"
                      value={signupForm.email}
                      onChange={e => setSignupForm({...signupForm, email: e.target.value})}
                      className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500 sm:text-sm dark:bg-gray-700 dark:text-white"
                      placeholder="user@example.com"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Password</label>
                    <input
                      required
                      type="password"
                      value={signupForm.password}
                      onChange={e => setSignupForm({...signupForm, password: e.target.value})}
                      className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500 sm:text-sm dark:bg-gray-700 dark:text-white"
                      placeholder="••••••••"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">System Role</label>
                    <select
                      value={signupForm.role}
                      onChange={e => setSignupForm({...signupForm, role: e.target.value})}
                      className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500 sm:text-sm dark:bg-gray-700 dark:text-white bg-white"
                    >
                      <option value="ANALYST">Analyst (Read-only)</option>
                      <option value="ADMIN">Administrator</option>
                    </select>
                  </div>
                </div>
                <div className="px-6 py-4 bg-gray-50 dark:bg-gray-900/50 border-t border-gray-200 dark:border-gray-700 flex justify-end gap-3">
                  <button
                    type="button"
                    onClick={() => setShowSignupModal(false)}
                    className="px-4 py-2 border border-gray-300 shadow-sm text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 focus:outline-none transition-colors dark:bg-gray-800 dark:text-gray-300 dark:border-gray-600 dark:hover:bg-gray-700"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={signupBusy}
                    className="px-4 py-2 border border-transparent shadow-sm text-sm font-medium rounded-md text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:bg-blue-400 transition-colors"
                  >
                    {signupBusy ? 'Creating...' : 'Create Account'}
                  </button>
                </div>
              </form>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
"""

with open('frontend/src/pages/Admin.jsx', 'w') as f:
    f.write(admin_code)

print("Rewritten Admin and AppLayout")
