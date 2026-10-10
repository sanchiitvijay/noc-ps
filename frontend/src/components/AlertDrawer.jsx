import { useEffect, useState } from "react";
import {
  FaTimes, FaNetworkWired, FaHistory, FaStethoscope, FaLightbulb,
  FaPlay, FaSpinner,
} from "react-icons/fa";
import { getErrorInfo, runDiagnostic } from "../services/api";
import Tag from "./Tag";
import RelatedTickets from "./RelatedTickets";

const DIAGNOSTICS = ["ping", "traceroute", "nslookup"];

function ticketReferences(event, info) {
  const references = [
    event?.ticket_number, event?.ticket_no, event?.ritm_number, event?.ritm_no,
    typeof event?.ritm === "object" ? event.ritm.number : event?.ritm, event?.request_number,
    event?.request_item_number, event?.ticket?.number, event?.ticket?.ticket_number,
    info?.ticket_number, info?.ticket_no, info?.ritm_number, info?.ritm_no,
    typeof info?.ritm === "object" ? info.ritm.number : info?.ritm, info?.request_number,
    ...(info?.historical_info?.related_tickets || []).map((ticket) => ticket.ticket_number),
  ];
  return [...new Set(references.filter(Boolean).map(String))];
}

function SectionHeader({ icon, title, aside }) {
  return (
    <div className="mb-3 flex items-center gap-2">
      <span className="grid h-7 w-7 place-items-center rounded-lg bg-brand-tint text-brand dark:bg-brand/20 dark:text-brand-hi">
        {icon}
      </span>
      <h3 className="text-[14px] font-bold text-ink dark:text-white">{title}</h3>
      {aside}
    </div>
  );
}

export default function AlertDrawer({ a, onClose }) {
  const [info, setInfo] = useState(null);
  const [loadingInfo, setLoadingInfo] = useState(false);
  const [error, setError] = useState("");
  const [diagnostic, setDiagnostic] = useState(null);
  const [busy, setBusy] = useState("");
  const [host, setHost] = useState("");

  useEffect(() => {
    const eventId = a?.event_id ?? a?.id;
    const hasEventId =
      eventId !== null && eventId !== undefined && eventId !== "" && Number.isSafeInteger(Number(eventId));

    setInfo(null);
    setLoadingInfo(hasEventId);
    setError("");
    setDiagnostic(null);
    setHost(a?.d.ip || "");

    if (!hasEventId) return undefined;

    let cancelled = false;
    getErrorInfo(eventId)
      .then((result) => { if (!cancelled) setInfo(result); })
      .catch((requestError) => { if (!cancelled) setError(requestError.message); })
      .finally(() => { if (!cancelled) setLoadingInfo(false); });
    return () => { cancelled = true; };
  }, [a]);

  useEffect(() => {
    if (!a) return undefined;
    const onKeyDown = (event) => { if (event.key === "Escape") onClose?.(); };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [a, onClose]);

  if (!a) return null;

  const data = info || {};
  const checks = data.preliminary_checks || {};
  const solution = data.suggested_solution || {};
  const ticketNumbers = ticketReferences(a, data);

  const run = async (kind) => {
    setBusy(kind);
    setError("");
    try {
      const body = { host: host.trim(), ...(kind === "ping" ? { count: 4 } : {}) };
      const result = await runDiagnostic(kind, body);
      setDiagnostic({ kind, result });
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setBusy("");
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex justify-end bg-[rgba(2,20,33,0.48)] backdrop-blur-[3px] animate-fade"
      onMouseDown={(event) => { if (event.target === event.currentTarget) onClose?.(); }}
    >
      <aside
        id="dr"
        aria-label={`Details for ${a.d?.name || "alert"}`}
        className="flex h-full w-full max-w-2xl flex-col overflow-hidden border-l border-line bg-paper shadow-pop animate-rise dark:border-white/10 dark:bg-[#0c2435]"
      >
        <header className="flex items-start gap-3 border-b border-line px-5 py-4 dark:border-white/10">
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-2">
              <Tag s={a.sev} />
              <span className="rounded-full bg-paper-3 px-2 py-0.5 text-[11px] font-semibold text-ink-2 dark:bg-white/10">
                {a.st || "Open"}
              </span>
            </div>
            <h2 className="mt-1.5 truncate font-mono text-[17px] font-bold text-ink dark:text-white">
              {a.d?.name || "Unknown device"}
            </h2>
            <p className="line-clamp-2 text-[13px] text-ink-2">{a.msg}</p>
          </div>
          <button
            onClick={onClose}
            aria-label="Close details"
            className="grid h-9 w-9 flex-none place-items-center rounded-lg border border-line text-ink-3 transition-colors hover:border-brand hover:text-brand dark:border-white/15"
          >
            <FaTimes />
          </button>
        </header>

        <div className="flex-1 space-y-6 overflow-y-auto px-5 py-5">
          {error && (
            <div role="alert" className="rounded-lg border border-p1/30 bg-p1-bg px-3 py-2 text-[13px] text-p1-ink">
              {error}
            </div>
          )}

          <section>
            <SectionHeader icon={<FaNetworkWired />} title="Device and event context" />
            <dl className="grid grid-cols-1 gap-x-6 gap-y-1.5 text-[13.5px] sm:grid-cols-2">
              {[
                ["Device", data.device?.device_name || a.d?.name],
                ["IP", data.device?.ip_address || a.d?.ip || "N/A"],
                ["Event", data.event_type?.event_type_name || a.event_type_name || a.msg],
                ["Category", data.event_type?.category || "N/A"],
                ["RITM / Ticket", ticketNumbers.length ? ticketNumbers.join(", ") : "Not linked"],
              ].map(([label, value]) => (
                <div key={label} className="flex gap-2 border-b border-line/60 py-1 dark:border-white/5">
                  <dt className="w-28 shrink-0 text-ink-3">{label}</dt>
                  <dd className="min-w-0 break-words text-ink-2">{value || "N/A"}</dd>
                </div>
              ))}
            </dl>
            {(a.event_id ?? a.id) === null || (a.event_id ?? a.id) === undefined || (a.event_id ?? a.id) === "" ? (
              <p className="mt-2 text-[12.5px] text-ink-3">
                This event has no event ID, so its error details cannot be loaded.
              </p>
            ) : null}
          </section>

          <section>
            <SectionHeader
              icon={<FaHistory />}
              title="Historical incidents"
              aside={
                <span className="ml-auto text-[12.5px] text-ink-3">
                  <b className="text-ink-2">{data.historical_info?.total_incidents_6m ?? "N/A"}</b> incidents · 6 months
                </span>
              }
            />
            <RelatedTickets
              tickets={data.historical_info?.related_tickets || []}
              lastEventId={data.historical_info?.last_event_id}
            />
          </section>

          <section>
            <SectionHeader icon={<FaStethoscope />} title="Preliminary checks" />
            <div className="grid gap-2 sm:grid-cols-2">
              {[
                ["Ping", checks.ping
                  ? `${checks.ping.reachable ? "Reachable" : "Unreachable"} · ${checks.ping.packet_loss_pct}% loss`
                  : "Not loaded", checks.ping ? checks.ping.reachable : null],
                ["Traceroute", checks.traceroute
                  ? checks.traceroute.completed ? "Completed" : "Incomplete"
                  : "Not loaded", checks.traceroute ? checks.traceroute.completed : null],
              ].map(([label, value, ok]) => (
                <div
                  key={label}
                  className="rounded-xl border border-line bg-paper-2 px-3.5 py-3 dark:border-white/10 dark:bg-white/5"
                >
                  <span className="text-[11.5px] font-semibold uppercase tracking-wider text-ink-3">{label}</span>
                  <b className={`block text-[14px] ${ok === false ? "text-p1-ink" : ok === true ? "text-good" : "text-ink-2"}`}>
                    {value}
                  </b>
                </div>
              ))}
            </div>
          </section>

          <section>
            <SectionHeader icon={<FaLightbulb />} title="Recommended solution" />
            {loadingInfo ? (
              <div className="space-y-2" role="status" aria-label="Loading recommended solution">
                <div className="skeleton h-4 w-3/4" />
                <div className="skeleton h-4 w-full" />
                <div className="skeleton h-4 w-5/6" />
              </div>
            ) : solution.hypothesis ? (
              <div>
                <p className="rounded-xl border border-brand-tint-2 bg-brand-tint px-3.5 py-3 text-[14px] font-medium text-ink dark:border-brand/30 dark:bg-brand/15 dark:text-white">
                  {solution.hypothesis}
                </p>
                <ol className="mt-3 grid gap-2">
                  {(solution.recommended_steps || []).map((step, index) => (
                    <li key={step} className="flex gap-3 rounded-lg border border-line bg-paper px-3 py-2 text-[13.5px] text-ink-2 dark:border-white/10 dark:bg-white/5">
                      <span className="grid h-6 w-6 flex-none place-items-center rounded-full bg-brand-tint text-[12px] font-bold text-brand dark:bg-brand/25 dark:text-brand-hi">
                        {index + 1}
                      </span>
                      {step}
                    </li>
                  ))}
                </ol>
                <span className="mt-2 inline-block text-[12px] text-ink-3">
                  Generated by {solution.generated_by || "AI"} · Confidence {solution.confidence || "N/A"}
                </span>
              </div>
            ) : (
              <span className="text-[13px] text-ink-3">Error analysis is not available for this event.</span>
            )}
          </section>

          <section>
            <SectionHeader icon={<FaPlay />} title="Run diagnostics" />
            <div className="flex flex-wrap items-center gap-2">
              <input
                aria-label="Diagnostic host"
                placeholder="IP address or hostname"
                value={host}
                onChange={(event) => setHost(event.target.value)}
                className="min-w-[200px] flex-1 rounded-lg border border-line-strong bg-paper px-3 py-2 text-[13.5px] text-ink outline-none transition-colors focus:border-brand focus:ring-2 focus:ring-brand/20 dark:border-white/15 dark:bg-transparent dark:text-white"
              />
              {DIAGNOSTICS.map((kind) => (
                <button
                  key={kind}
                  disabled={!host.trim() || !!busy}
                  onClick={() => run(kind)}
                  className="inline-flex items-center gap-1.5 rounded-lg border border-line-strong bg-paper px-3 py-2 text-[13px] font-semibold text-ink-2 transition-colors hover:border-brand hover:text-brand disabled:cursor-not-allowed disabled:opacity-50 dark:border-white/15 dark:bg-white/5"
                >
                  {busy === kind ? <FaSpinner className="animate-spin" /> : <FaPlay className="text-[10px]" />}
                  {kind}
                </button>
              ))}
            </div>
            {diagnostic && (
              <pre className="mt-3 max-h-64 overflow-auto whitespace-pre-wrap break-words rounded-lg border border-line bg-paper-2 p-3 font-mono text-[12px] text-ink-2 dark:border-white/10 dark:bg-white/5">
                {JSON.stringify(diagnostic.result, null, 2)}
              </pre>
            )}
          </section>
        </div>
      </aside>
    </div>
  );
}
