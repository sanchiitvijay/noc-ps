import { useEffect, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { FaUser, FaLock, FaSpinner, FaSignInAlt, FaBolt, FaExclamationTriangle } from "react-icons/fa";
import { useStore } from "../store";
import { login } from "../services/api";
import Logo from "../components/Logo";

const DEMO = { username: "admin@networkops.com", password: "Admin@123" };

export default function Login() {
  const { me, setMe } = useStore();
  const navigate = useNavigate();
  const location = useLocation();

  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [remember, setRemember] = useState(true);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState("");

  useEffect(() => {
    if (me) navigate("/dashboard", { replace: true });
  }, [me, navigate]);

  const redirect = () => navigate(location.state?.from?.pathname || "/dashboard", { replace: true });

  const submit = async (event) => {
    event.preventDefault();
    setError("");
    setBusy("form");
    try {
      const session = await login(username, password, remember, false);
      setMe(session);
      redirect();
    } catch (requestError) {
      if (requestError.message.includes("Demo account")) {
        try {
          const session = await login(username, password, remember, true);
          setMe(session);
          redirect();
        } catch {
          setError(requestError.message);
        }
      } else {
        setError(requestError.message);
      }
    } finally {
      setBusy("");
    }
  };

  const demoLogin = async () => {
    setError("");
    setBusy("demo");
    try {
      const session = await login(DEMO.username, DEMO.password, true, true);
      setMe(session);
      redirect();
    } catch (demoError) {
      setError(demoError.message);
    } finally {
      setBusy("");
    }
  };

  return (
    <div className="grid min-h-screen grid-cols-1 lg:grid-cols-[1.15fr_1fr]">
      {/* Brand panel */}
      <section className="relative hidden overflow-hidden bg-brand p-11 text-white lg:flex lg:flex-col dark:bg-[#00283f]">
        <div
          aria-hidden="true"
          className="pointer-events-none absolute inset-0 opacity-70"
          style={{
            background:
              "radial-gradient(900px 500px at 80% 10%, rgba(124,192,236,.25), transparent 60%), radial-gradient(700px 500px at 0% 110%, rgba(255,255,255,.08), transparent 60%)",
          }}
        />
        <div className="relative flex items-center gap-3">
          <Logo white className="h-8 w-auto" />
          <span className="rounded-md border border-white/25 px-2 py-0.5 text-[11px] font-semibold tracking-wide">
            NOC
          </span>
        </div>

        <div className="relative mt-auto">
          <h1
            className="text-[clamp(56px,7vw,116px)] leading-[0.86] font-black tracking-tight"
            style={{ fontVariationSettings: '"wdth" 125' }}
          >
            NAAP
          </h1>
          <p className="mt-5 max-w-[460px] text-[16px] text-white/80">
            Every alert arrives with its history, its neighbours and a first-response plan. Triage the network in
            one place.
          </p>
        </div>

        <div className="relative mt-10 flex flex-wrap gap-6 text-[13px] text-white/70">
          {["Live event stream", "AI recommendations", "Ticket history"].map((item) => (
            <span key={item} className="inline-flex items-center gap-2">
              <i className="h-1.5 w-1.5 rounded-full bg-[#7cc0ec]" />
              {item}
            </span>
          ))}
        </div>
      </section>

      {/* Form panel */}
      <section className="grid place-items-center bg-paper px-6 py-10 dark:bg-[#0c2435]">
        <form onSubmit={submit} className="grid w-full max-w-[380px] gap-4">
          <div className="mb-1 flex items-center gap-3 lg:hidden">
            <Logo className="h-8 w-auto" />
          </div>

          <div>
            <h2 className="text-[26px] font-bold tracking-tight text-ink dark:text-white">Sign in</h2>
            <p className="mt-1.5 text-[13.5px] text-ink-3">
              Use your NAAP account. Ask an administrator if you need one.
            </p>
          </div>

          {error && (
            <div
              role="alert"
              className="flex items-start gap-2 rounded-lg border border-p1/25 bg-p1-bg px-3 py-2.5 text-[13.5px] text-p1-ink"
            >
              <FaExclamationTriangle className="mt-0.5 flex-none" />
              <span>{error}</span>
            </div>
          )}

          <label className="grid gap-1.5">
            <span className="text-[13px] font-semibold text-ink-2">Username</span>
            <span className="relative">
              <FaUser className="pointer-events-none absolute top-1/2 left-3 -translate-y-1/2 text-ink-3" />
              <input
                type="text"
                autoComplete="username"
                required
                value={username}
                onChange={(event) => setUsername(event.target.value)}
                placeholder="you@example.com"
                className="w-full rounded-lg border border-line-strong bg-paper py-2.5 pr-3 pl-9 text-[14px] text-ink outline-none transition-colors focus:border-brand focus:ring-2 focus:ring-brand/20 dark:border-white/15 dark:bg-white/5 dark:text-white"
              />
            </span>
          </label>

          <label className="grid gap-1.5">
            <span className="text-[13px] font-semibold text-ink-2">Password</span>
            <span className="relative">
              <FaLock className="pointer-events-none absolute top-1/2 left-3 -translate-y-1/2 text-ink-3" />
              <input
                type="password"
                autoComplete="current-password"
                required
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                placeholder="••••••••"
                className="w-full rounded-lg border border-line-strong bg-paper py-2.5 pr-3 pl-9 text-[14px] text-ink outline-none transition-colors focus:border-brand focus:ring-2 focus:ring-brand/20 dark:border-white/15 dark:bg-white/5 dark:text-white"
              />
            </span>
          </label>

          <label className="flex cursor-pointer items-center gap-2 text-[13px] text-ink-2">
            <input
              type="checkbox"
              checked={remember}
              onChange={(event) => setRemember(event.target.checked)}
              className="h-4 w-4 accent-brand"
            />
            Remember me on this device
          </label>

          <button
            type="submit"
            disabled={!!busy}
            className="inline-flex items-center justify-center gap-2 rounded-lg bg-brand py-3 text-[14px] font-semibold text-white shadow-sm transition-colors hover:bg-brand-hi disabled:cursor-not-allowed disabled:opacity-60"
          >
            {busy === "form" ? <FaSpinner className="animate-spin" /> : <FaSignInAlt />}
            {busy === "form" ? "Signing in…" : "Sign in"}
          </button>

          <div className="flex items-center gap-3 text-[12px] text-ink-3">
            <span className="h-px flex-1 bg-line dark:bg-white/10" />
            or
            <span className="h-px flex-1 bg-line dark:bg-white/10" />
          </div>

          <button
            type="button"
            onClick={demoLogin}
            disabled={!!busy}
            title="Sign in with the bundled offline demo account"
            className="inline-flex items-center justify-center gap-2 rounded-lg border border-line-strong bg-paper py-2.5 text-[13.5px] font-semibold text-ink-2 transition-colors hover:border-brand hover:text-brand disabled:cursor-not-allowed disabled:opacity-60 dark:border-white/15 dark:bg-white/5"
          >
            {busy === "demo" ? <FaSpinner className="animate-spin" /> : <FaBolt />}
            Explore the offline demo
          </button>

          <p className="text-center text-[12px] text-ink-3">Ferguson · Network Operations Center</p>
        </form>
      </section>
    </div>
  );
}
