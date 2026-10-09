import { useState } from 'react';
import { Navigate, useNavigate } from 'react-router-dom';
import Logo from '../components/Logo';
import { login, signup } from '../services/api';
import { useStore } from '../store';
import { landing } from '../routes/Guard';

export default function Login() {
  const [username, setUsername] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [remember, setRemember] = useState(false);
  const [useDemo, setUseDemo] = useState(false);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [creating, setCreating] = useState(false);
  const [isDark, setIsDark] = useState(
    () => document.documentElement.dataset.theme === 'dark',
  );
  const setMe = useStore((state) => state.setMe);
  const me = useStore((state) => state.me);
  const navigate = useNavigate();

  if (me) {
    return <Navigate to={landing(me.role)} replace />;
  }

  const submit = async (event) => {
    event.preventDefault();
    setBusy(true);
    setError('');

    try {
      const session = creating
        ? await signup({ username, email, password, role: 'analyst' }, remember)
        : await login(username, password, remember, useDemo);
      setMe(session);
      navigate(landing(session.role));
    } catch (requestError) {
      const validationMessage = requestError.details?.validation_errors
        ?.map((item) => item.msg)
        .filter(Boolean)
        .join(' ');
      setError(
        validationMessage
          ? `${requestError.message}: ${validationMessage}`
          : requestError.message,
      );
    } finally {
      setBusy(false);
    }
  };

  const toggleTheme = () => {
    const nextIsDark = !isDark;
    document.documentElement.dataset.theme = nextIsDark ? 'dark' : 'light';
    setIsDark(nextIsDark);
  };

  const fillCredentials = (demoUsername, demoPassword, demo = false) => {
    setUsername(demoUsername);
    setPassword(demoPassword);
    setUseDemo(demo);
    setError('');
  };

  const handleCredentialKeyDown = (event, demoUsername, demoPassword) => {
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      fillCredentials(demoUsername, demoPassword, true);
    }
  };

  return (
    <div id="lgn">
      <button
        className="theme-toggle"
        type="button"
        onClick={toggleTheme}
        aria-label={`Switch to ${isDark ? 'light' : 'dark'} theme`}
      >
        <span>{isDark ? 'Light' : 'Dark'} theme</span>
      </button>

      <div className="ls">
        <svg className="net" viewBox="0 0 300 140">
          <g
            stroke="#38BDF8"
            strokeWidth="1.5"
            fill="none"
            strokeDasharray="4 4"
            className="fl"
          >
            <path d="M40 70L110 30L190 80L260 40" />
            <path d="M110 30L130 110L190 80" />
          </g>
          <g fill="#00A3A3">
            {[[40, 70], [110, 30], [190, 80], [260, 40], [130, 110]].map((point, index) => (
              <circle key={index} cx={point[0]} cy={point[1]} r="6" />
            ))}
          </g>
          <g fill="#38BDF8">
            {[[110, 30], [190, 80], [130, 110]].map((point, index) => (
              <circle
                key={index}
                className="pu"
                cx={point[0]}
                cy={point[1]}
                r="5"
                style={{ animationDelay: `${index * 0.5}s` }}
              />
            ))}
          </g>
        </svg>
        <h2>Network Alerts Automation Platform</h2>
        <p>Monitor. Diagnose. Automate. Resolve.</p>
        <ul>
          <li>Real-time Monitoring</li>
          <li>Automated Diagnostics</li>
          <li>AI Root Cause Analysis</li>
          <li>Faster Incident Resolution</li>
        </ul>
      </div>

      <form className="rs" onSubmit={submit}>
        <div className="login-brand">
          <Logo h={28} />
          <span>Network Alerts Automation Platform</span>
        </div>
        <b>{creating ? 'Create account' : 'Sign in'}</b>
        <input
          required
          autoComplete="username"
          placeholder="Username"
          value={username}
          onChange={(event) => { setUsername(event.target.value); setUseDemo(false); }}
        />
        {creating && (
          <input
            required
            type="email"
            autoComplete="email"
            placeholder="Email"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
          />
        )}
        <input
          required
          type="password"
          autoComplete={creating ? 'new-password' : 'current-password'}
          placeholder="Password"
          value={password}
          onChange={(event) => { setPassword(event.target.value); setUseDemo(false); }}
        />
        <label>
          <input
            type="checkbox"
            checked={remember}
            onChange={(event) => setRemember(event.target.checked)}
          />
          Remember me
        </label>
        <div role="alert" style={{ color: '#DC2626', minHeight: 18 }}>{error}</div>
        <button className="p" type="submit" disabled={busy}>
          {busy ? 'Please wait...' : creating ? 'Create account' : 'Sign In'}
        </button>

        {!creating && (
          <>
            <div
              className="dm"
              role="button"
              tabIndex={0}
              onClick={() => fillCredentials('admin', 'admin123', true)}
              onKeyDown={(event) => handleCredentialKeyDown(event, 'admin', 'admin123')}
            >
              <b>Offline demo login</b> admin / admin123{' '}
              <span className="mu">(click to fill; no backend needed)</span>
            </div>
            <div
              className="dm"
              role="button"
              tabIndex={0}
              onClick={() => fillCredentials('analyst@networkops.com', 'User@123', true)}
              onKeyDown={(event) => handleCredentialKeyDown(event, 'analyst@networkops.com', 'User@123')}
            >
              <b>Offline analyst</b> analyst@networkops.com / User@123{' '}
              <span className="mu">(click to fill)</span>
            </div>
          </>
        )}

        <button
          type="button"
          onClick={() => {
            setCreating(!creating);
            setUseDemo(false);
            setError('');
          }}
        >
          {creating ? 'Back to sign in' : 'Create an analyst account'}
        </button>
        <div style={{ fontSize: 12, color: '#667085', textAlign: 'center' }}>
          Version v1.0
        </div>
      </form>
    </div>
  );
}
