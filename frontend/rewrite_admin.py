with open("src/pages/Admin.jsx", "w") as f:
    f.write('''import { useEffect, useState } from 'react';
import { getActivityLog, ingestFile, signup } from '../services/api';
import { useStore } from '../store';
import { FaUserPlus, FaTimes, FaUpload, FaSync, FaChevronLeft, FaChevronRight } from 'react-icons/fa';

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

  const loadActivity = (nextPage = page) =>
    getActivityLog({ page: nextPage, page_size: 25 })
      .then((result) => {
        setActivity(Array.isArray(result) ? result : result?.data || result?.items || []);
        setTotal(result?.total || 0);
        setPage(result?.page || nextPage);
      })
      .catch((requestError) => setError(requestError.message));

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
      await signup(signupForm, false);
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
    <div className="flex flex-col space-y-6">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-3xl font-bold text-gray-900 dark:text-gray-100">System Administration</h2>
        <button onClick={() => setShowSignupModal(true)} className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-md shadow-sm transition-colors">
          <FaUserPlus />
          <span>Add User</span>
        </button>
      </div>

      <section className="bg-white dark:bg-gray-800 p-5 border border-gray-200 dark:border-gray-700 rounded-lg shadow-sm flex flex-col hover:border-blue-500 transition-colors">
        <h3 className="text-xs text-gray-500 uppercase tracking-wider mb-4">Ingest Events or Tickets</h3>
        <form onSubmit={upload} className="flex flex-wrap items-center gap-3">
          <input
            type="file"
            accept=".csv,.xlsx"
            required
            onChange={(event) => setFile(event.target.files?.[0] || null)}
            className="block w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded file:border-0 file:text-sm file:font-semibold file:bg-blue-50 file:text-blue-700 hover:file:bg-blue-100 dark:file:bg-gray-700 dark:file:text-gray-300 md:w-auto"
          />
          <button className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-md disabled:opacity-50" disabled={!file || busy}>
            <FaUpload />
            {busy ? 'Uploading...' : 'Upload file'}
          </button>
        </form>
        <p className="text-xs text-gray-500 mt-2">Accepted formats: CSV and XLSX.</p>
        {message && <div className="mt-3 text-green-600 font-medium" role="status">{message}</div>}
        {error && <div className="mt-3 text-red-600 font-medium" role="alert">{error}</div>}
      </section>

      <section className="bg-white dark:bg-gray-800 p-5 border border-gray-200 dark:border-gray-700 rounded-lg shadow-sm flex flex-col hover:border-blue-500 transition-colors">
        <div className="flex items-center justify-between mb-4 pb-3 border-b border-gray-200 dark:border-gray-700">
          <h3 className="text-lg font-bold text-gray-900 dark:text-gray-100">Activity Log</h3>
          <button onClick={() => loadActivity(1)} className="flex items-center gap-1.5 px-3 py-1.5 bg-gray-100 hover:bg-gray-200 dark:bg-gray-700 dark:hover:bg-gray-600 text-gray-700 dark:text-gray-200 rounded text-sm transition-colors">
            <FaSync className="text-xs" /> Refresh
          </button>
        </div>
        
        {error && <div className="mb-4 text-red-600 font-medium" role="alert">{error}</div>}
        
        <div className="flex flex-col space-y-2">
          {activity.length ? activity.map((item, index) => (
            <div className="flex items-center justify-between py-2 border-b border-gray-100 dark:border-gray-700/50 last:border-0" key={item.id || `${item.timestamp}-${index}`}>
              <span className="flex-1 text-sm text-gray-800 dark:text-gray-200">
                <strong className="font-semibold">{item.username || item.user_id || 'User'}</strong>
                <span className="mx-2 text-gray-400">|</span>
                {item.endpoint_path || item.action || 'Action'}
              </span>
              <span className="text-xs text-gray-500">{item.created_at || item.timestamp || ''}</span>
            </div>
          )) : <span className="text-sm text-gray-500 py-4 text-center">No activity records returned.</span>}
        </div>
        
        <div className="flex flex-wrap items-center justify-end gap-4 mt-6 pt-4 border-t border-gray-200 dark:border-gray-700">
          <button className="flex items-center gap-1 px-3 py-1.5 bg-gray-100 dark:bg-gray-700 rounded text-sm disabled:opacity-40" disabled={page <= 1} onClick={() => loadActivity(page - 1)}>
            <FaChevronLeft className="text-xs" /> Previous
          </button>
          <span className="text-xs text-gray-500 font-medium tracking-wider uppercase">Page {page}  |  {total.toLocaleString()} records</span>
          <button className="flex items-center gap-1 px-3 py-1.5 bg-gray-100 dark:bg-gray-700 rounded text-sm disabled:opacity-40" disabled={page * 25 >= total} onClick={() => loadActivity(page + 1)}>
            Next <FaChevronRight className="text-xs" />
          </button>
        </div>
      </section>

      {showSignupModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm p-4">
          <div className="bg-white dark:bg-gray-800 w-full max-w-md rounded-lg shadow-xl overflow-hidden flex flex-col">
            <div className="flex justify-between items-center p-4 border-b border-gray-200 dark:border-gray-700">
              <h3 className="text-lg font-bold">Add New User</h3>
              <button onClick={() => setShowSignupModal(false)} className="text-gray-500 hover:text-gray-800 dark:hover:text-gray-200"><FaTimes /></button>
            </div>
            <form onSubmit={handleSignup} className="p-4 flex flex-col space-y-4">
              {signupMsg && <div className="p-2 bg-red-100 text-red-700 text-sm rounded">{signupMsg}</div>}
              <div>
                <label className="block text-xs font-semibold uppercase text-gray-500 mb-1">Username</label>
                <input required type="text" value={signupForm.username} onChange={e => setSignupForm({...signupForm, username: e.target.value})} className="w-full px-3 py-2 bg-gray-50 dark:bg-gray-900 border border-gray-300 dark:border-gray-600 rounded" />
              </div>
              <div>
                <label className="block text-xs font-semibold uppercase text-gray-500 mb-1">Email</label>
                <input required type="email" value={signupForm.email} onChange={e => setSignupForm({...signupForm, email: e.target.value})} className="w-full px-3 py-2 bg-gray-50 dark:bg-gray-900 border border-gray-300 dark:border-gray-600 rounded" />
              </div>
              <div>
                <label className="block text-xs font-semibold uppercase text-gray-500 mb-1">Password</label>
                <input required type="password" value={signupForm.password} onChange={e => setSignupForm({...signupForm, password: e.target.value})} className="w-full px-3 py-2 bg-gray-50 dark:bg-gray-900 border border-gray-300 dark:border-gray-600 rounded" />
              </div>
              <div>
                <label className="block text-xs font-semibold uppercase text-gray-500 mb-1">Role</label>
                <select value={signupForm.role} onChange={e => setSignupForm({...signupForm, role: e.target.value})} className="w-full px-3 py-2 bg-gray-50 dark:bg-gray-900 border border-gray-300 dark:border-gray-600 rounded">
                  <option value="ANALYST">Analyst</option>
                  <option value="ADMIN">Admin</option>
                </select>
              </div>
              <div className="mt-2 flex justify-end">
                <button type="submit" disabled={signupBusy} className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded font-medium disabled:opacity-50">
                  {signupBusy ? 'Creating...' : 'Create User'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
''')
