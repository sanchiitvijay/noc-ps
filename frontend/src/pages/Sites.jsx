import { useEffect, useMemo, useState } from "react";
import {
  FaSearch, FaSpinner, FaTimes, FaMapMarkerAlt, FaBell,
  FaExclamationTriangle, FaTicketAlt, FaServer,
} from "react-icons/fa";
import { getSite, getSites } from "../services/api";
import Pagination from "../components/Pagination";

const PAGE_SIZE = 24;

/* US tilegram layout (column, row) on a 12×8 grid — same shape as the
   nocturne reference console. States absent from the API stay grey. */
const TILES = {
  AK: [0, 0], ME: [11, 0], VT: [10, 1], NH: [11, 1], WA: [1, 2], ID: [2, 2],
  MT: [3, 2], ND: [4, 2], MN: [5, 2], IL: [6, 2], WI: [7, 2], MI: [8, 2],
  NY: [9, 2], RI: [10, 2], MA: [11, 2],
  OR: [1, 3], NV: [2, 3], WY: [3, 3], SD: [4, 3], IA: [5, 3], IN: [6, 3],
  OH: [7, 3], PA: [8, 3], NJ: [9, 3], CT: [10, 3],
  CA: [1, 4], UT: [2, 4], CO: [3, 4], NE: [4, 4], MO: [5, 4], KY: [6, 4],
  WV: [7, 4], VA: [8, 4], MD: [9, 4], DE: [10, 4],
  AZ: [2, 5], NM: [3, 5], KS: [4, 5], AR: [5, 5], TN: [6, 5], NC: [7, 5],
  SC: [8, 5], DC: [9, 5],
  OK: [4, 6], LA: [5, 6], MS: [6, 6], AL: [7, 6], GA: [8, 6],
  HI: [0, 7], TX: [4, 7], FL: [9, 7],
};

const SEQ_LIGHT = ["#eef3f7", "#cfe0ec", "#9dc0da", "#5f95bd", "#1f6a9c", "#00446a", "#002a42"];
const SEQ_DARK = ["#0f2a3d", "#13395a", "#1a4e7a", "#23679e", "#3584c0", "#5fa8dc", "#a6d2f0"];

function useIsDarkTheme() {
  const [dark, setDark] = useState(() => document.documentElement.classList.contains("dark"));
  useEffect(() => {
    const observer = new MutationObserver(() => setDark(document.documentElement.classList.contains("dark")));
    observer.observe(document.documentElement, { attributes: true, attributeFilter: ["class"] });
    return () => observer.disconnect();
  }, []);
  return dark;
}

function Tilegram({ states, activeState, onPick }) {
  const dark = useIsDarkTheme();
  const tiles = useMemo(() => {
    const byState = Object.fromEntries(states.map((s) => [s.state, s]));
    const max = Math.max(...states.map((s) => s.alerts || 0), 1);
    const cells = Array.from({ length: 8 * 12 }, () => null);
    Object.entries(TILES).forEach(([code, [col, row]]) => cells[row * 12 + col] = code);
    return { byState, max, cells };
  }, [states]);

  return (
    <div className="grid grid-cols-12 gap-1" role="group" aria-label="Sites by state heatmap">
      {tiles.cells.map((code, index) => {
        if (!code) return <div key={index} aria-hidden="true" />;
        const data = tiles.byState[code];
        const value = data?.alerts || 0;
        const step = value ? 1 + Math.min(5, Math.floor(Math.sqrt(value / tiles.max) * 6)) : 0;
        const palette = dark ? SEQ_DARK : SEQ_LIGHT;
        const lightText = step >= 4;
        const active = activeState === code;
        return (
          <button
            key={code}
            type="button"
            disabled={!value}
            onClick={() => onPick(code)}
            title={value
              ? `${code}: ${value} alerts · ${data.p1 || 0} critical · ${data.sites || 0} sites`
              : `${code}: no sites`}
            aria-pressed={active}
            className={`grid aspect-square place-items-center rounded-md text-[10px] font-bold transition-transform dark-text-none ${
              value ? "cursor-pointer hover:z-10 hover:scale-115 hover:shadow-md" : "cursor-default"
            } ${active ? "outline-2 outline-offset-1 outline-brand" : ""}`}
            style={{
              background: step ? palette[step] : dark ? "#0f2a3d40" : "#eef3f7aa",
              color: lightText ? "#fff" : step ? (dark ? "#e8f0f6" : "#0e2232") : "#77787b",
              fontSize: "10px",
            }}
          >
            {code}
          </button>
        );
      })}
    </div>
  );
}

function SiteDrawer({ code, onClose }) {
  const [detail, setDetail] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!code) return undefined;
    let cancelled = false;
    setLoading(true);
    setError("");
    setDetail(null);
    getSite(code)
      .then((result) => { if (!cancelled) setDetail(result); })
      .catch((err) => { if (!cancelled) setError(err.message); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [code]);

  useEffect(() => {
    const onKeyDown = (event) => { if (event.key === "Escape") onClose(); };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [onClose]);

  if (!code) return null;
  const site = detail?.site || {};
  const deviceRows = detail?.devices || [];
  const recent = detail?.recent || [];
  const byCategory = detail?.by_category || [];
  const tickets = detail?.tickets || [];
  const catMax = Math.max(1, ...byCategory.map((row) => Number(row.n) || 0));

  return (
    <div
      className="animate-fade fixed inset-0 z-50 flex justify-end bg-[rgba(2,20,33,0.48)] backdrop-blur-[3px]"
      onMouseDown={(event) => { if (event.target === event.currentTarget) onClose(); }}
    >
      <aside className="animate-rise flex h-full w-full max-w-2xl flex-col overflow-hidden border-l border-line bg-paper shadow-pop dark:border-white/10 dark:bg-[#0c2435]">
        <header className="flex items-start gap-3 border-b border-line px-5 py-4 dark:border-white/10">
          <span className="grid h-11 w-11 flex-none place-items-center rounded-xl bg-brand-tint text-brand dark:bg-brand/20 dark:text-brand-hi">
            <FaMapMarkerAlt className="text-lg" />
          </span>
          <div className="min-w-0 flex-1">
            <span className="text-[11px] font-semibold tracking-wider text-ink-3 uppercase">Site details</span>
            <h2 className="truncate font-mono text-[17px] font-bold text-ink dark:text-white">
              {site.label || site.city || code}
            </h2>
            <p className="text-[12.5px] text-ink-3">
              {[site.code, site.city, site.state].filter(Boolean).join(" · ")}
            </p>
          </div>
          <button
            onClick={onClose}
            aria-label="Close site details"
            className="grid h-9 w-9 flex-none place-items-center rounded-lg border border-line text-ink-3 transition-colors hover:border-brand hover:text-brand dark:border-white/15"
          >
            <FaTimes />
          </button>
        </header>

        <div className="flex-1 space-y-6 overflow-y-auto px-5 py-5">
          {loading && (
            <div className="grid gap-2" role="status" aria-label="Loading site details">
              {Array.from({ length: 5 }, (_, index) => <i key={index} className="skeleton block h-5 rounded-md" />)}
            </div>
          )}
          {error && (
            <div role="alert" className="rounded-lg border border-p1/25 bg-p1-bg px-3 py-2 text-[13px] text-p1-ink">{error}</div>
          )}

          {detail && (
            <>
              <section>
                <h3 className="mb-3 text-[14px] font-bold text-ink dark:text-white">Devices ({deviceRows.length})</h3>
                <div className="overflow-x-auto rounded-xl border border-line dark:border-white/10">
                  <table className="w-full border-collapse text-[13px]">
                    <thead>
                      <tr className="bg-paper-2 dark:bg-white/5">
                        {["Device", "ID", "Type", "IP", "Events"].map((h) => (
                          <th key={h} className="border-b border-line px-3 py-2 text-left text-[11px] font-semibold tracking-wider text-ink-3 uppercase dark:border-white/10">{h}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-line dark:divide-white/10">
                      {deviceRows.map((device) => (
                        <tr key={device.device_id}>
                          <td className="px-3 py-2 text-ink-2">{device.device_name}</td>
                          <td className="px-3 py-2 font-mono text-ink-3">{device.device_id}</td>
                          <td className="px-3 py-2 text-ink-2">{device.machine_type || "—"}</td>
                          <td className="px-3 py-2 font-mono text-ink-3">{device.ip_address || "—"}</td>
                          <td className="px-3 py-2 tabular font-semibold text-ink dark:text-white">{device.event_count}</td>
                        </tr>
                      ))}
                      {!deviceRows.length && (
                        <tr><td colSpan={5} className="px-3 py-6 text-center text-ink-3">No devices at this site.</td></tr>
                      )}
                    </tbody>
                  </table>
                </div>
              </section>

              <section>
                <h3 className="mb-3 text-[14px] font-bold text-ink dark:text-white">Alerts by category</h3>
                {byCategory.length ? (
                  <div className="grid gap-2.5">
                    {byCategory.map((row) => (
                      <div key={row.category} className="grid grid-cols-[minmax(90px,150px)_1fr_auto] items-center gap-3 text-[13px]">
                        <span className="truncate text-ink-2 capitalize">{row.category || "other"}</span>
                        <span className="h-2.5 overflow-hidden rounded-full bg-paper-3 dark:bg-white/10">
                          <i className="block h-full rounded-full bg-brand transition-[width] duration-700" style={{ width: `${(Number(row.n) / catMax) * 100}%` }} />
                        </span>
                        <b className="tabular min-w-10 text-right text-ink dark:text-white">{row.n}</b>
                      </div>
                    ))}
                  </div>
                ) : <p className="text-[13px] text-ink-3">No category breakdown returned.</p>}
              </section>

              <section>
                <h3 className="mb-3 text-[14px] font-bold text-ink dark:text-white">Recent alerts ({recent.length})</h3>
                <div className="grid gap-2">
                  {recent.map((alert, index) => (
                    <div key={alert.id ?? index} className="flex items-start gap-3 rounded-lg border border-line bg-paper-2 px-3 py-2 dark:border-white/10 dark:bg-white/5">
                      <span className="mt-0.5 rounded-md bg-paper-3 px-2 py-0.5 text-[11px] font-bold text-ink-2 dark:bg-white/10">{alert.severity || "—"}</span>
                      <div className="min-w-0">
                        <b className="block text-[13px] text-ink dark:text-white">{alert.name || alert.message}</b>
                        <span className="text-[12px] text-ink-3">{alert.device_name} · {alert.ts || "time n/a"}</span>
                      </div>
                    </div>
                  ))}
                  {!recent.length && <p className="text-[13px] text-ink-3">No recent alerts.</p>}
                </div>
              </section>

              {tickets.length > 0 && (
                <section>
                  <h3 className="mb-3 text-[14px] font-bold text-ink dark:text-white">Related tickets ({tickets.length})</h3>
                  <div className="grid gap-2">
                    {tickets.map((ticket) => (
                      <div key={ticket.number} className="flex items-center gap-3 rounded-lg border border-line bg-paper-2 px-3 py-2 text-[13px] dark:border-white/10 dark:bg-white/5">
                        <FaTicketAlt className="text-ink-3" />
                        <b className="font-mono text-brand dark:text-brand-hi">{ticket.number}</b>
                        <span className="truncate text-ink-2">{ticket.short_description}</span>
                        <span className="ml-auto rounded-full bg-paper-3 px-2 py-0.5 text-[11px] font-semibold text-ink-2 dark:bg-white/10">{ticket.state}</span>
                      </div>
                    ))}
                  </div>
                </section>
              )}
            </>
          )}
        </div>
      </aside>
    </div>
  );
}

export default function Sites() {
  const [query, setQuery] = useState("");
  const [stateFilter, setStateFilter] = useState("");
  const [page, setPage] = useState(1);
  const [result, setResult] = useState({ data: [], total: 0, total_pages: 1, states: [] });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [selectedCode, setSelectedCode] = useState(null);

  const load = (nextPage = 1, overrides = {}) => {
    const params = { page: nextPage, page_size: PAGE_SIZE, q: query, state: stateFilter, ...overrides };
    setLoading(true);
    setError("");
    getSites(params)
      .then((res) => {
        setResult(res);
        setPage(res.page || nextPage);
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  };

  useEffect(() => { load(1); /* eslint-disable-next-line react-hooks/exhaustive-deps */ }, []);

  // Live search — debounce like the reference console.
  useEffect(() => {
    const timer = window.setTimeout(() => {
      if (query !== undefined) load(1, { q: query, state: stateFilter });
    }, 300);
    return () => window.clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [query]);

  const totals = result.states.reduce(
    (acc, s) => ({
      sites: acc.sites + (s.sites || 0),
      alerts: acc.alerts + (s.alerts || 0),
      p1: acc.p1 + (s.p1 || 0),
    }),
    { sites: 0, alerts: 0, p1: 0 },
  );

  const busiest = [...result.states].sort((a, b) => (b.alerts || 0) - (a.alerts || 0)).slice(0, 10);

  const pickState = (state) => {
    const next = stateFilter === state ? "" : state;
    setStateFilter(next);
    load(1, { state: next });
  };

  return (
    <div className="grid gap-5">
      <div className="grid grid-cols-1 gap-5 lg:grid-cols-12">
        {/* Tilegram panel */}
        <section className="rounded-card border border-line bg-paper p-5 shadow-card lg:col-span-5 dark:border-white/10 dark:bg-[#0c2435]">
          <header className="mb-4">
            <h2 className="text-[15px] font-bold text-ink dark:text-white">Sites by state</h2>
            <p className="text-[12.5px] text-ink-3">Select a state to list its sites. Darker tiles carry more actionable alerts.</p>
          </header>
          <Tilegram states={result.states} activeState={stateFilter} onPick={pickState} />
        </section>

        {/* Search + chips + totals */}
        <section className="rounded-card self-start border border-line bg-paper p-5 shadow-card lg:col-span-7 dark:border-white/10 dark:bg-[#0c2435]">
          <div className="relative min-w-[220px]">
            <FaSearch className="pointer-events-none absolute top-1/2 left-3 -translate-y-1/2 text-ink-3" />
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Site code, city or address…"
              aria-label="Search sites"
              className="w-full rounded-lg border border-line-strong bg-paper py-2 pr-9 pl-9 text-[13.5px] text-ink outline-none transition-colors focus:border-brand focus:ring-2 focus:ring-brand/20 dark:border-white/15 dark:bg-white/5 dark:text-white"
            />
            {query && (
              <button
                type="button"
                aria-label="Clear search"
                onClick={() => setQuery("")}
                className="absolute top-1/2 right-2 -translate-y-1/2 rounded p-1 text-ink-3 transition-colors hover:text-ink"
              >
                <FaTimes />
              </button>
            )}
          </div>

          {busiest.length > 0 && (
            <div className="mt-4 flex flex-wrap items-center gap-2">
              <span className="text-[11px] font-semibold tracking-wider text-ink-3 uppercase">Busiest</span>
              {busiest.map((row) => (
                <button
                  type="button"
                  key={row.state}
                  onClick={() => pickState(row.state)}
                  aria-pressed={stateFilter === row.state}
                  className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-[12.5px] font-medium transition-colors ${
                    stateFilter === row.state
                      ? "border-brand bg-brand-tint text-brand dark:bg-brand/20 dark:text-brand-hi"
                      : "border-line bg-paper-2 text-ink-2 hover:border-brand hover:text-brand dark:border-white/10 dark:bg-white/5"
                  }`}
                >
                  {row.state}
                  <b className="rounded-full bg-white/60 px-1.5 text-[11px] dark:bg-white/10">
                    {(row.alerts ?? 0) >= 10000 ? new Intl.NumberFormat(undefined, { notation: "compact", maximumFractionDigits: 1 }).format(row.alerts) : (row.alerts ?? 0).toLocaleString()}
                  </b>
                </button>
              ))}
              {stateFilter && (
                <button
                  type="button"
                  onClick={() => { setStateFilter(""); load(1, { state: "" }); }}
                  className="inline-flex items-center gap-1 rounded-full border border-line bg-paper-2 px-3 py-1 text-[12.5px] text-ink-3 hover:text-p1 dark:border-white/10 dark:bg-white/5"
                >
                  Clear {stateFilter} <FaTimes />
                </button>
              )}
            </div>
          )}

          {result.states.length > 0 && (
            <div className="mt-4 grid grid-cols-2 gap-2.5 sm:grid-cols-4">
              {[
                [totals.sites, "Sites with a state"],
                [result.states.length, "States covered"],
                [totals.alerts, "Actionable alerts"],
                [totals.p1, "Critical"],
              ].map(([value, label]) => (
                <div key={label} className="rounded-xl border border-line bg-paper-2 px-3.5 py-2.5 dark:border-white/10 dark:bg-white/5">
                  <b className="tabular block text-[22px] leading-tight font-extrabold text-ink dark:text-white">
                    {value.toLocaleString()}
                  </b>
                  <span className="text-[12px] text-ink-3">{label}</span>
                </div>
              ))}
            </div>
          )}
        </section>
      </div>

      <div className="flex items-baseline gap-3 text-[13.5px]">
        <span><b>{result.total.toLocaleString()}</b> sites{stateFilter ? ` in ${stateFilter}` : ""}</span>
        <span className="text-ink-3">Sorted by actionable alerts.</span>
        {loading && <FaSpinner className="animate-spin text-brand" aria-label="Loading" />}
        {error && (
          <span role="alert" className="ml-auto flex items-center gap-2 rounded-lg border border-p1/25 bg-p1-bg px-3 py-1.5 text-[13px] text-p1-ink">
            <FaExclamationTriangle /> {error}
          </span>
        )}
      </div>

      {loading && !result.data.length ? (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {Array.from({ length: 6 }, (_, index) => <div key={index} className="skeleton h-36 rounded-card" />)}
        </div>
      ) : result.data.length ? (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {result.data.map((site) => {
            const critPct = Math.round((100 * (site.p1 || 0)) / (site.alerts || 1));
            return (
              <button
                type="button"
                key={site.code}
                onClick={() => setSelectedCode(site.code)}
                className="group grid gap-2.5 rounded-card border border-line bg-paper p-4 text-left shadow-card transition-transform hover:-translate-y-0.5 hover:shadow-lg dark:border-white/10 dark:bg-[#0c2435]"
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="text-[26px] leading-none font-extrabold tracking-tight text-brand dark:text-brand-hi">{site.code}</span>
                  <span className="inline-flex items-center gap-1.5 rounded-full bg-paper-2 px-2.5 py-1 text-[11.5px] font-semibold text-ink-2 dark:bg-white/10">
                    <FaServer /> {site.devices} device{site.devices === 1 ? "" : "s"}
                  </span>
                </div>
                <div>
                  <div className="text-[14.5px] font-semibold text-ink dark:text-white">{site.label || "Unlabelled site"}</div>
                  <div className="min-h-[1.4em] text-[12.5px] text-ink-3">{site.address?.trim() && /[A-Za-z]{3,}/.test(site.address) ? site.address : ""}</div>
                </div>
                {/* severity segbar: critical share vs. the rest */}
                <div
                  className="flex h-4 gap-0.5 overflow-hidden rounded-md"
                  title={`${critPct}% critical`}
                >
                  <i
                    className="block h-full min-w-[2px] rounded-l-sm bg-p1 transition-[flex-grow] duration-700"
                    style={{ flexGrow: site.p1 || 0 }}
                  />
                  <i
                    className="block h-full min-w-[2px] rounded-r-sm bg-brand-tint-2 dark:bg-brand/40 transition-[flex-grow] duration-700"
                    style={{ flexGrow: Math.max((site.alerts || 0) - (site.p1 || 0), 0) }}
                  />
                </div>
                <div className="flex items-center gap-2 text-[12.5px]">
                  <span className="inline-flex items-center gap-1.5 rounded-md border border-line bg-paper-2 px-2 py-0.5 text-ink-2 dark:border-white/10 dark:bg-white/5">
                    <FaBell /> {(site.alerts || 0).toLocaleString()} alerts
                  </span>
                  {site.p1 > 0 && (
                    <span className="inline-flex items-center gap-1.5 rounded-md bg-p1-bg px-2 py-0.5 font-semibold text-p1-ink">
                      <FaExclamationTriangle /> {(site.p1 || 0).toLocaleString()} critical
                    </span>
                  )}
                  {site.tickets > 0 && (
                    <span className="inline-flex items-center gap-1.5 rounded-md bg-brand-tint px-2 py-0.5 font-medium text-brand dark:bg-brand/20 dark:text-brand-hi">
                      <FaTicketAlt /> {site.tickets}
                    </span>
                  )}
                </div>
              </button>
            );
          })}
        </div>
      ) : (
        <div className="rounded-card border border-line bg-paper px-6 py-16 text-center text-[13.5px] text-ink-3 shadow-card dark:border-white/10 dark:bg-[#0c2435]">
          No sites match. Site codes come from device names during import.
        </div>
      )}

      {result.total > PAGE_SIZE && (
        <Pagination
          page={page}
          totalPages={Math.max(1, Math.ceil(result.total / PAGE_SIZE))}
          disabled={loading}
          onPageChange={(next) => load(next)}
          className="justify-center"
        />
      )}

      <SiteDrawer code={selectedCode} onClose={() => setSelectedCode(null)} />
    </div>
  );
}
