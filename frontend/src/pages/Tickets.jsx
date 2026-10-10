import { useEffect, useState } from "react";
import {
  FaSearch, FaSpinner, FaTimes, FaTicketAlt, FaLink, FaExclamationTriangle,
} from "react-icons/fa";
import { getTicket, getTickets } from "../services/api";
import Pagination from "../components/Pagination";

const PAGE_SIZE = 25;

const KIND_STYLE = {
  INC: "bg-brand text-white",
  RITM: "bg-p3-bg text-p3-ink",
  TASK: "bg-paper-3 text-ink-2",
  CHG: "bg-good-bg text-good",
};

function kindClass(kind) {
  return KIND_STYLE[kind] || "bg-paper-3 text-ink-2";
}

function statePill(state) {
  const value = String(state || "").toLowerCase();
  if (["closed", "resolved", "complete"].some((word) => value.includes(word))) return "bg-good-bg text-good";
  if (["open", "new", "active", "pending", "in progress"].some((word) => value.includes(word))) return "bg-p2-bg text-p2-ink";
  return "bg-paper-3 text-ink-2";
}

function display(value) {
  return value === null || value === undefined || value === "" ? "—" : String(value);
}

function TicketDrawer({ number, onClose }) {
  const [detail, setDetail] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!number) return undefined;
    let cancelled = false;
    setLoading(true);
    setError("");
    setDetail(null);
    getTicket(number)
      .then((result) => { if (!cancelled) setDetail(result); })
      .catch((err) => { if (!cancelled) setError(err.message); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [number]);

  useEffect(() => {
    const onKeyDown = (event) => { if (event.key === "Escape") onClose(); };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [onClose]);

  if (!number) return null;
  const ticket = detail?.ticket || {};
  const links = detail?.links || [];

  return (
    <div
      className="animate-fade fixed inset-0 z-50 flex justify-end bg-[rgba(2,20,33,0.48)] backdrop-blur-[3px]"
      onMouseDown={(event) => { if (event.target === event.currentTarget) onClose(); }}
    >
      <aside className="animate-rise flex h-full w-full max-w-2xl flex-col overflow-hidden border-l border-line bg-paper shadow-pop dark:border-white/10 dark:bg-[#0c2435]">
        <header className="flex items-start gap-3 border-b border-line px-5 py-4 dark:border-white/10">
          <span className="grid h-11 w-11 flex-none place-items-center rounded-xl bg-brand-tint text-brand dark:bg-brand/20 dark:text-brand-hi">
            <FaTicketAlt className="text-lg" />
          </span>
          <div className="min-w-0 flex-1">
            <span className="text-[11px] font-semibold tracking-wider text-ink-3 uppercase">
              {display(ticket.ticket_type)} ticket
            </span>
            <h2 className="truncate font-mono text-[17px] font-bold text-ink dark:text-white">{number}</h2>
          </div>
          <button
            onClick={onClose}
            aria-label="Close ticket details"
            className="grid h-9 w-9 flex-none place-items-center rounded-lg border border-line text-ink-3 transition-colors hover:border-brand hover:text-brand dark:border-white/15"
          >
            <FaTimes />
          </button>
        </header>

        <div className="flex-1 space-y-6 overflow-y-auto px-5 py-5">
          {loading && <div className="flex items-center gap-2 text-[13.5px] text-ink-3"><FaSpinner className="animate-spin text-brand" /> Loading ticket…</div>}
          {error && <div role="alert" className="rounded-lg border border-p1/25 bg-p1-bg px-3 py-2 text-[13px] text-p1-ink">{error}</div>}

          {detail && (
            <>
              <section>
                <div className="mb-3 flex flex-wrap items-center gap-2">
                  <span className={`rounded-md px-2 py-0.5 text-[11px] font-bold ${kindClass(ticket.ticket_type)}`}>{display(ticket.ticket_type)}</span>
                  <span className={`rounded-full px-2.5 py-0.5 text-[11.5px] font-semibold ${statePill(ticket.state)}`}>{display(ticket.state)}</span>
                </div>
                <h3 className="text-[15px] font-bold text-ink dark:text-white">{display(ticket.short_description)}</h3>
                <p className="mt-1 text-[13.5px] text-ink-2">{display(ticket.description)}</p>
              </section>

              <section>
                <h4 className="mb-2 text-[11px] font-semibold tracking-wider text-ink-3 uppercase">Details</h4>
                <dl className="grid grid-cols-1 gap-x-6 gap-y-1.5 text-[13.5px] sm:grid-cols-2">
                  {[
                    ["Assignment group", ticket.assignment_group],
                    ["Created", ticket.created_on],
                    ["Updated", ticket.updated_on],
                    ["Closed", ticket.closed_at],
                    ["Site codes", (ticket.extracted_site_codes || []).join(", ")],
                    ["IP addresses", (ticket.extracted_ips || []).join(", ")],
                    ["Device names", (ticket.extracted_device_names || []).join(", ")],
                  ].map(([label, value]) => (
                    <div key={label} className="flex gap-2 border-b border-line/60 py-1 dark:border-white/5">
                      <dt className="w-32 shrink-0 text-ink-3">{label}</dt>
                      <dd className="min-w-0 break-words text-ink-2">{display(value)}</dd>
                    </div>
                  ))}
                </dl>
              </section>

              <section>
                <h4 className="mb-2 text-[11px] font-semibold tracking-wider text-ink-3 uppercase">Linked devices ({links.length})</h4>
                <div className="grid gap-2">
                  {links.map((link, index) => (
                    <div key={`${link.device_id}-${index}`} className="flex items-center gap-3 rounded-lg border border-line bg-paper-2 px-3 py-2 dark:border-white/10 dark:bg-white/5">
                      <FaLink className="text-ink-3" />
                      <div className="min-w-0">
                        <b className="block truncate text-[13px] text-ink dark:text-white">{display(link.device_name)}</b>
                        <span className="text-[12px] text-ink-3">
                          {[link.site_label, link.role, `${link.kind}: ${link.value}`].filter(Boolean).join(" · ")}
                        </span>
                      </div>
                      {link.confidence != null && (
                        <span className="ml-auto rounded-full bg-brand-tint px-2 py-0.5 text-[11px] font-semibold text-brand dark:bg-brand/20 dark:text-brand-hi">
                          {Math.round(Number(link.confidence) * 100)}%
                        </span>
                      )}
                    </div>
                  ))}
                  {!links.length && <p className="text-[13px] text-ink-3">No linked devices for this ticket.</p>}
                </div>
              </section>

              <section>
                <h4 className="mb-2 text-[11px] font-semibold tracking-wider text-ink-3 uppercase">Work notes</h4>
                <pre className="max-h-52 overflow-auto whitespace-pre-wrap rounded-lg border border-line bg-paper-2 p-3 font-mono text-[12px] text-ink-2 dark:border-white/10 dark:bg-white/5">
                  {display(ticket.work_notes)}
                </pre>
              </section>
            </>
          )}
        </div>
      </aside>
    </div>
  );
}

export default function Tickets() {
  const [q, setQ] = useState("");
  const [kind, setKind] = useState("");
  const [status, setStatus] = useState("");
  const [linked, setLinked] = useState("");
  const [page, setPage] = useState(1);
  const [result, setResult] = useState({ data: [], total: 0, total_pages: 1, kinds: [], statuses: [] });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [selected, setSelected] = useState(null);

  const load = (nextPage = page, overrides = {}) => {
    const params = { page: nextPage, page_size: PAGE_SIZE, q, kind, status, linked, ...overrides };
    setLoading(true);
    setError("");
    getTickets(params)
      .then((res) => { setResult(res); setPage(res.page || nextPage); })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  };

  useEffect(() => { load(1); /* eslint-disable-next-line react-hooks/exhaustive-deps */ }, []);

  const submit = (event) => {
    event.preventDefault();
    load(1, { q, kind, status, linked });
  };

  const fieldClass = "rounded-lg border border-line-strong bg-paper px-3 py-2 text-[13px] text-ink outline-none transition-colors focus:border-brand focus:ring-2 focus:ring-brand/20 dark:border-white/15 dark:bg-white/5 dark:text-white";

  return (
    <div className="grid gap-5">
      <form onSubmit={submit} className="rounded-card border border-line bg-paper p-5 shadow-card dark:border-white/10 dark:bg-[#0c2435]">
        <div className="flex flex-wrap items-center gap-3">
          <div className="relative min-w-[220px] flex-1">
            <FaSearch className="pointer-events-none absolute top-1/2 left-3 -translate-y-1/2 text-ink-3" />
            <input
              value={q}
              onChange={(event) => setQ(event.target.value)}
              placeholder="Search by number or description"
              className="w-full rounded-lg border border-line-strong bg-paper py-2 pr-3 pl-9 text-[13.5px] text-ink outline-none transition-colors focus:border-brand focus:ring-2 focus:ring-brand/20 dark:border-white/15 dark:bg-white/5 dark:text-white"
            />
          </div>
          <select value={kind} onChange={(event) => setKind(event.target.value)} className={fieldClass} aria-label="Ticket type">
            <option value="">All types</option>
            {result.kinds.map((row) => <option key={row.kind} value={row.kind}>{row.kind} ({row.n})</option>)}
          </select>
          <select value={status} onChange={(event) => setStatus(event.target.value)} className={fieldClass} aria-label="Status">
            <option value="">All states</option>
            {result.statuses.map((row) => <option key={row.state} value={row.state}>{row.state} ({row.n})</option>)}
          </select>
          <select value={linked} onChange={(event) => setLinked(event.target.value)} className={fieldClass} aria-label="Linked">
            <option value="">Linked: any</option>
            <option value="yes">Linked only</option>
            <option value="no">Unlinked only</option>
          </select>
          <button
            type="submit"
            disabled={loading}
            className="inline-flex items-center gap-2 rounded-lg bg-brand px-4 py-2 text-[13.5px] font-semibold text-white shadow-sm transition-colors hover:bg-brand-hi disabled:opacity-60"
          >
            {loading ? <FaSpinner className="animate-spin" /> : <FaSearch />} Search
          </button>
          <span className="ml-auto text-[13px] text-ink-3"><b className="text-ink-2">{result.total.toLocaleString()}</b> tickets</span>
        </div>

        {error && (
          <div role="alert" className="mt-3 flex items-center gap-2 rounded-lg border border-p1/25 bg-p1-bg px-3 py-2 text-[13px] text-p1-ink">
            <FaExclamationTriangle /> {error}
          </div>
        )}
      </form>

      <div className="grid gap-3">
        {loading && !result.data.length
          ? Array.from({ length: 6 }, (_, index) => <div key={index} className="skeleton h-20 rounded-card" />)
          : result.data.map((ticket) => (
            <button
              type="button"
              key={ticket.ticket_id}
              onClick={() => setSelected(ticket.ticket_number)}
              className="flex flex-wrap items-center gap-3 rounded-card border border-line bg-paper px-5 py-4 text-left shadow-card transition-transform hover:-translate-y-0.5 hover:shadow-lg dark:border-white/10 dark:bg-[#0c2435]"
            >
              <span className={`grid h-10 w-14 flex-none place-items-center rounded-lg text-[11.5px] font-extrabold ${kindClass(ticket.ticket_type)}`}>
                {ticket.ticket_type}
              </span>
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2">
                  <b className="font-mono text-[13px] text-brand dark:text-brand-hi">{ticket.ticket_number}</b>
                  <span className={`rounded-full px-2 py-0.5 text-[11px] font-semibold ${statePill(ticket.state)}`}>{ticket.state}</span>
                </div>
                <p className="mt-1 line-clamp-1 text-[13.5px] text-ink-2">{ticket.short_description}</p>
              </div>
              <div className="ml-auto flex flex-col items-end text-[12px] text-ink-3">
                <span className="tabular">{ticket.created_on || "—"}</span>
                <span className="inline-flex items-center gap-1.5">
                  <FaLink /> {ticket.links} link{ticket.links === 1 ? "" : "s"}
                  {ticket.best_link != null && ` · ${Math.round(Number(ticket.best_link) * 100)}%`}
                </span>
              </div>
            </button>
          ))}

        {!loading && !result.data.length && (
          <div className="rounded-card border border-line bg-paper px-6 py-16 text-center text-[13.5px] text-ink-3 shadow-card dark:border-white/10 dark:bg-[#0c2435]">
            No tickets match the current filters.
          </div>
        )}
      </div>

      {result.total > PAGE_SIZE && (
        <Pagination
          page={page}
          totalPages={Math.max(1, Math.ceil(result.total / PAGE_SIZE))}
          disabled={loading}
          onPageChange={(next) => load(next)}
          className="justify-center"
        />
      )}

      <TicketDrawer number={selected} onClose={() => setSelected(null)} />
    </div>
  );
}
