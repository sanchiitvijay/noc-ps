with open("src/pages/Login.jsx", "w") as f:
    f.write('''import { useEffect, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { useStore } from '../store';
import { login, signup } from '../services/api';
import Logo from '../components/Logo';

export default function Login() {
  const { me, setMe } = useStore();
  const navigate = useNavigate();
  const location = useLocation();

  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [remember, setRemember] = useState(true);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (me) navigate('/dashboard', { replace: true });
  }, [me, navigate]);

  const submit = async (event) => {
    event.preventDefault();
    setError('');
    setBusy(true);

    try {
      const session = await login(username, password, remember, false);
      setMe(session);
      navigate(location.state?.from?.pathname || '/dashboard', { replace: true });
    } catch (requestError) {
      if (requestError.message.includes("Demo account")) {
        try {
          const session = await login(username, password, remember, true);
          setMe(session);
          navigate(location.state?.from?.pathname || '/dashboard', { replace: true });
        } catch (e) {
          setError(requestError.message);
        }
      } else {
        setError(requestError.message);
      }
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="flex flex-col items-center justify-center min-h-screen bg-gray-50 dark:bg-gray-900 p-4">
      <div className="w-full max-w-sm bg-white dark:bg-gray-800 p-8 rounded-lg shadow-md border border-gray-200 dark:border-gray-700">
        <div className="flex justify-center mb-8">
          <Logo />
        </div>
        <h2 className="text-2xl font-bold text-center text-gray-900 dark:text-gray-100 mb-6">Sign in to NAAP</h2>
        <form onSubmit={submit} className="flex flex-col space-y-4">
          {error && <div className="p-3 bg-red-100 text-red-700 text-sm rounded">{error}</div>}
          
          <div className="flex flex-col">
            <label className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-1" htmlFor="username">Username</label>
            <input
              id="username"
              type="text"
              autoComplete="username"
              required
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              className="px-3 py-2 border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-900 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
          
          <div className="flex flex-col">
            <label className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-1" htmlFor="password">Password</label>
            <input
              id="password"
              type="password"
              autoComplete="current-password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="px-3 py-2 border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-900 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
          
          <div className="flex items-center gap-2">
            <input
              id="remember"
              type="checkbox"
              checked={remember}
              onChange={(e) => setRemember(e.target.checked)}
              className="w-4 h-4 text-blue-600"
            />
            <label className="text-sm text-gray-700 dark:text-gray-300" htmlFor="remember">Remember me</label>
          </div>
          
          <button
            type="submit"
            disabled={busy}
            className="w-full py-2 px-4 bg-blue-600 hover:bg-blue-700 text-white font-semibold rounded-md transition-colors disabled:opacity-50"
          >
            {busy ? 'Signing in...' : 'Sign in'}
          </button>
        </form>
      </div>
    </div>
  );
}
''')
