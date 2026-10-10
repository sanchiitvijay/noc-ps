import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import {
  FaArrowLeft, FaCopy, FaExternalLinkAlt, FaCheck, FaTimes, FaQuestion,
  FaServer, FaNetworkWired, FaHistory, FaTerminal, FaLightbulb, FaSpinner,
  FaExclamationTriangle, FaSave, FaTrashAlt, FaPencilAlt,
} from "react-icons/fa";
import {
  deleteSolutionSummary, getErrorInfo, getSolutionSummary, runDiagnostic, saveSolutionSummary,
} from "../services/api";
import RelatedTickets from "../components/RelatedTickets";
import Tag from "../components/Tag";

function readEvent(eventId) {
  const key = `naap.event.detail.${eventId}`;
  try {
    const saved = sessionStorage.getItem(key);
    if (saved) return JSON.parse(saved);
    if (window.name.startsWith("naap-event:")) {
      const event = JSON.parse(window.name.slice("naap-event:".length));
      window.name = "";
      if (String(event.id) === String(eventId)) {
        sessionStorage.setItem(key, JSON.stringify(event));
        return event;
      }
    }
  } catch {
    window.name = "";
  }
  return null;
}

function normalizeEventId(value) {
  let eventId = value;
  while (eventId && typeof eventId === "object") eventId = eventId.event_id ?? eventId.id;
  if (eventId === null || eventId === undefined || eventId === "") return null;
  const numericEventId = Number(eventId);
  return Number.isSafeInteger(numericEventId) ? numericEventId : null;
}

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

function relativeTime(value) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return { label: "Time unavailable", iso: "" };
  const seconds = Math.round((date.getTime() - Date.now()) / 1000);
  const units = [["year", 31536000], ["month", 2592000], ["week", 604800], ["day", 86400], ["hour", 3600], ["minute", 60]];
  const [unit, size] = units.find(([, size]) => Math.abs(seconds) >= size) || ["minute", 60];
  return {
    label: new Intl.RelativeTimeFormat(undefined, { numeric: "auto" }).format(Math.round(seconds / size), unit),
    iso: date.toISOString(),
  };
}

function parseRecommendedSolution(solution = {}) {
  if (typeof solution === "string") return { steps: [], plainText: solution.trim(), summary: "" };
  const arraySteps = [solution.recommended_steps, solution.steps].find(Array.isArray);
  if (arraySteps?.length) return { steps: arraySteps.map(String), plainText: "", summary: solution.hypothesis || "" };

  const raw = [solution.recommended_solution, solution.recommended_steps, solution.solution, solution.hypothesis]
    .find((value) => typeof value === "string" && value.trim());
  if (!raw) return { steps: [], plainText: "", summary: "" };
  const cleanRaw = raw.replace(/^\s*recommended\s+solution\s*:?\s*/i, "").replace(/\r/g, "");
  const lines = cleanRaw.split(/\n|\s+(?=\d+[.)]\s)/).map((line) => line.trim()).filter(Boolean);
  const numbered = lines.filter((line) => /^\d+[.)]\s+/.test(line)).map((line) => line.replace(/^\d+[.)]\s+/, "").trim()).filter(Boolean);
  if (numbered.length) return { steps: numbered, plainText: "", summary: solution.hypothesis || "" };
  return { steps: [], plainText: raw.trim(), summary: "" };
}

function formatResultLines(result) {
  if (typeof result === "string") return result.split(/\r?\n/);
  return (JSON.stringify(result, null, 2) ?? String(result)).split("\n");
}

function parseTicketDate(value) {
  if (!value) return null;
  const match = String(value).match(/^(\d{2})-(\d{2})-(\d{4})(?:\s+(.*))?$/);
  const date = match
    ? new Date(`${match[3]}-${match[1]}-${match[2]}T${(match[4] || "00:00:00").replace(" ", "T")}`)
    : new Date(value);
  return Number.isNaN(date.getTime()) ? null : date;
}

function WeeklySparkline({ tickets }) {
  const counts = useMemo(() => {
    const buckets = Array(7).fill(0);
    const today = new Date();
    today.setHours(23, 59, 59, 999);
    tickets.forEach((ticket) => {
      const date = parseTicketDate(ticket.created_on || ticket.event_time);
      if (!date) return;
      const daysAgo = Math.floor((today.getTime() - date.getTime()) / 86400000);
      if (daysAgo >= 0 && daysAgo < 7) buckets[6 - daysAgo] += 1;
    });
    return buckets;
  }, [tickets]);
  const max = Math.max(...counts, 1);
  const points = counts.map((count, index) => `${index * 24 + 3},${30 - (count / max) * 24}`).join(" ");
  return (
    <div className="rounded-xl border border-line bg-paper-2 p-4 dark:border-white/10 dark:bg-white/5">
      <div className="mb-2 flex items-center gap-2">
        <b className="text-[13.5px] text-ink dark:text-white">Related incidents</b>
        <span className="ml-auto text-[12px] text-ink-3">Last 7 days</span>
      </div>
      <svg viewBox="0 0 150 34" className="h-10 w-full text-brand" role="img" aria-label={`Weekly related incident counts: ${counts.join(", ")}`}>
        <path d={`M3,32 ${points.split(" ").map((point) => `L${point}`).join(" ")} L147,32 Z`} fill="currentColor" opacity="0.12" />
        <polyline points={points} fill="none" stroke="currentColor" strokeWidth="2" />
        {counts.map((count, index) => (
          <circle key={index} cx={index * 24 + 3} cy={30 - (count / max) * 24} r="2.5" fill="currentColor" />
        ))}
      </svg>
      <span className="text-[11.5px] text-ink-3">From related ticket dates</span>
    </div>
  );
}

function StateChip({ value }) {
  const state = String(value || "").toLowerCase();
  const tone = ["closed", "resolved", "acknowledged", "complete", "completed"].some((word) => state.includes(word))
    ? "bg-good-bg text-good"
    : ["open", "new", "active", "on hold", "pending"].some((word) => state.includes(word))
      ? "bg-p2-bg text-p2-ink"
      : "bg-paper-3 text-ink-2";
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-[12px] font-semibold ${tone}`}>
      <i className="h-1.5 w-1.5 rounded-full bg-current" />
      {value || "Unknown state"}
    </span>
  );
}

function AlertContext({ alert, device, ticketNumber, ticketUrl, opened, onCopyIp }) {
  const rows = [
    ["Device", device.device_name || alert.d.name || "N/A"],
    ["Opened", <time key="t" title={opened.iso || undefined} className="text-ink-2">{opened.label}</time>],
  ];
  return (
    <div aria-label="Alert context" className="grid gap-3">
      <div className="flex flex-wrap items-center gap-2">
        <Tag s={alert.sev || "Unknown"} />
        <StateChip value={alert.st} />
      </div>
      <dl className="grid gap-2 text-[13.5px]">
        {rows.map(([label, value], index) => (
          <div key={index} className="flex gap-2">
            <dt className="w-24 shrink-0 text-ink-3">{label}</dt>
            <dd className="min-w-0 break-words text-ink-2">{value}</dd>
          </div>
        ))}
        <div className="flex gap-2">
          <dt className="w-24 shrink-0 text-ink-3">IP address</dt>
          <dd className="flex min-w-0 items-center gap-2 text-ink-2">
            <span className="break-all">{device.ip_address || alert.d.ip || "IP unavailable"}</span>
            <button
              type="button"
              aria-label="Copy device IP address"
              title="Copy device IP address"
              onClick={onCopyIp}
              className="grid h-6 w-6 place-items-center rounded-md border border-line text-ink-3 transition-colors hover:border-brand hover:text-brand dark:border-white/15"
            >
              <FaCopy className="text-[11px]" />
            </button>
          </dd>
        </div>
        <div className="flex gap-2">
          <dt className="w-24 shrink-0 text-ink-3">Ticket</dt>
          <dd className="min-w-0 break-words text-ink-2">
            {ticketNumber && ticketUrl ? (
              <a href={ticketUrl} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1.5 font-medium text-brand hover:underline">
                {ticketNumber} <FaExternalLinkAlt className="text-[10px]" />
              </a>
            ) : (
              ticketNumber || "Not linked"
            )}
          </dd>
        </div>
      </dl>
    </div>
  );
}

function CheckTile({ kind, value }) {
  const isPing = kind === "ping";
  const failed = isPing ? value?.reachable === false : value?.completed === false;
  const passed = isPing ? value?.reachable === true : value?.completed === true;
  const label = failed ? (isPing ? "Failed" : "Incomplete") : passed ? "Passed" : "Not checked";
  const tone = failed
    ? { box: "border-p1/30 bg-p1-bg", ic: "text-p1" }
    : passed
      ? { box: "border-good/30 bg-good-bg", ic: "text-good" }
      : { box: "border-line bg-paper-2", ic: "text-ink-3" };
  const Icon = failed ? FaTimes : passed ? FaCheck : FaQuestion;
  return (
    <article className={`flex items-center gap-3 rounded-xl border px-4 py-3 dark:bg-white/5 ${tone.box}`}>
      <span className={`grid h-10 w-10 flex-none place-items-center rounded-lg bg-white/70 ${tone.ic} dark:bg-white/10`}>
        <Icon />
      </span>
      <div className="min-w-0">
        <span className="text-[11.5px] font-semibold tracking-wider text-ink-3 uppercase">{isPing ? "Ping" : "Traceroute"}</span>
        <b className="block text-[14px] text-ink dark:text-white">{label}</b>
        <small className="text-[12px] text-ink-3">
          {value
            ? isPing
              ? `${value.packet_loss_pct ?? "—"}% packet loss`
              : value.completed ? "Route completed" : "Route incomplete"
            : "Run a check to see status"}
        </small>
      </div>
    </article>
  );
}

function LoadingSkeleton({ rows = 4 }) {
  return (
    <div className="grid gap-2" role="status" aria-label="Loading event information">
      {Array.from({ length: rows }, (_, index) => <i key={index} className="skeleton block h-5 rounded-md" />)}
    </div>
  );
}

function Panel({ icon, kicker, title, aside, children }) {
  return (
    <section className="rounded-card border border-line bg-paper p-5 shadow-card dark:border-white/10 dark:bg-[#0c2435]">
      <div className="mb-4 flex items-center gap-2">
        {icon && (
          <span className="grid h-8 w-8 place-items-center rounded-lg bg-brand-tint text-brand dark:bg-brand/20 dark:text-brand-hi">
            {icon}
          </span>
        )}
        <div>
          <span className="text-[11px] font-semibold tracking-wider text-ink-3 uppercase">{kicker}</span>
          <h2 className="text-[16px] font-bold text-ink dark:text-white">{title}</h2>
        </div>
        {aside && <div className="ml-auto text-[12.5px] text-ink-3">{aside}</div>}
      </div>
      {children}
    </section>
  );
}

export default function AlertEventDetails() {
  const { eventId } = useParams();
  const [alert] = useState(() => readEvent(eventId));
  const detailEventId = normalizeEventId(alert?.event_id ?? alert?.id ?? eventId);
  const [info, setInfo] = useState(null);
  const [loadingInfo, setLoadingInfo] = useState(detailEventId !== null);
  const [error, setError] = useState("");
  const [retryCount, setRetryCount] = useState(0);
  const [host, setHost] = useState(alert?.d?.ip || "");
  const [busy, setBusy] = useState("");
  const [diagnosticLines, setDiagnosticLines] = useState([]);
  const [diagnosticError, setDiagnosticError] = useState("");
  const [rerunChecks, setRerunChecks] = useState({});
  const [savedSummary, setSavedSummary] = useState(null);
  const [editingSummary, setEditingSummary] = useState(false);
  const [summaryForm, setSummaryForm] = useState({ hypothesis: "", steps: "", confidence: "medium" });
  const [summaryBusy, setSummaryBusy] = useState("");
  const [summaryMsg, setSummaryMsg] = useState("");

  useEffect(() => {
    if (detailEventId === null) {
      setLoadingInfo(false);
      setError("This event is missing its event ID, so related analysis cannot be loaded.");
      return undefined;
    }
    let cancelled = false;
    setLoadingInfo(true);
    setError("");
    getErrorInfo(detailEventId)
      .then((result) => { if (!cancelled) setInfo(result); })
      .catch((requestError) => { if (!cancelled) setError(`Could not load event and ticket information: ${requestError.message}`); })
      .finally(() => { if (!cancelled) setLoadingInfo(false); });
    return () => { cancelled = true; };
  }, [detailEventId, retryCount]);

  // Load any cached solution summary for this event (404 = none saved).
  useEffect(() => {
    if (detailEventId === null) return undefined;
    let cancelled = false;
    getSolutionSummary(detailEventId)
      .then((saved) => { if (!cancelled) setSavedSummary(saved || null); })
      .catch(() => { if (!cancelled) setSavedSummary(null); });
    return () => { cancelled = true; };
  }, [detailEventId, retryCount]);

  if (!alert) {
    return (
      <section className="mx-auto max-w-md rounded-card border border-line bg-paper p-8 text-center shadow-card dark:border-white/10 dark:bg-[#0c2435]">
        <FaExclamationTriangle className="mx-auto mb-3 text-3xl text-warn" />
        <h3 className="text-[18px] font-bold text-ink dark:text-white">Event details unavailable</h3>
        <p className="mt-1.5 text-[13.5px] text-ink-3">Open this page using “View details” in the Alerts Console.</p>
        <Link to="/alerts" className="mt-4 inline-flex items-center gap-2 rounded-lg bg-brand px-4 py-2 text-[13.5px] font-semibold text-white hover:bg-brand-hi">
          <FaArrowLeft /> Return to Alerts Console
        </Link>
      </section>
    );
  }

  const device = info?.device || {};
  const eventType = info?.event_type || {};
  const history = info?.historical_info || {};
  const checks = info?.preliminary_checks || {};
  const recentLogs = history.recent_event_logs || info?.recent_event_logs || [];
  const solution = info?.suggested_solution || {};
  const recommendations = parseRecommendedSolution(solution);
  const ticketNumbers = ticketReferences(alert, info);
  const ticketNumber = ticketNumbers[0];
  const firstRelatedTicket = history.related_tickets?.[0];
  const ticketUrl = alert.ticket_url || alert.itsm_url || alert.ticket?.url || info?.ticket_url || firstRelatedTicket?.url
    || (import.meta.env.VITE_ITSM_BASE_URL && ticketNumber
      ? `${import.meta.env.VITE_ITSM_BASE_URL.replace(/\/$/, "")}/nav_to.do?uri=task.do?sysparm_query=number%3D${encodeURIComponent(ticketNumber)}`
      : "");
  const pingResult = rerunChecks.ping || checks.ping;
  const routeResult = rerunChecks.traceroute || checks.traceroute;
  const eventTypeName = eventType.event_type_name || alert.event_type_name || alert.msg || "";
  const dataMismatch = eventTypeName.toLowerCase() === "interface up" && pingResult?.reachable === false;
  const opened = relativeTime(alert.t);
  const absoluteEventId = detailEventId ?? eventId;
  const solutionSource = solution.generated_by === "no_ticket_llm"
    ? "LLM gave this response"
    : solution.generated_by === "rule-based"
      ? "Rule-based fallback"
      : solution.generated_by === "gemini"
        ? "Gemini analysis"
        : solution.generated_by || "";

  const run = async (kind) => {
    if (!host.trim()) {
      setDiagnosticError("Enter a device IP address or hostname, then retry the check.");
      return;
    }
    setBusy(kind);
    setDiagnosticError("");
    setDiagnosticLines([`$ ${kind} ${host.trim()}`, "Connecting to diagnostics service…"]);
    try {
      const result = await runDiagnostic(kind, { host: host.trim(), ...(kind === "ping" ? { count: 4 } : {}) });
      const lines = formatResultLines(result);
      setDiagnosticLines([]);
      for (const line of lines) {
        setDiagnosticLines((current) => [...current, line]);
        await new Promise((resolve) => window.setTimeout(resolve, 24));
      }
      if (kind === "ping" || kind === "traceroute") setRerunChecks((current) => ({ ...current, [kind]: result }));
    } catch (requestError) {
      const message = `The ${kind} request failed: ${requestError.message}. Check the host and retry.`;
      setDiagnosticError(message);
      setDiagnosticLines((current) => [...current, `ERROR: ${message}`]);
    } finally {
      setBusy("");
    }
  };

  const copyIp = async () => {
    try {
      await navigator.clipboard.writeText(device.ip_address || alert.d.ip || "");
    } catch {
      setDiagnosticError("Could not copy the IP address. Select and copy it manually.");
    }
  };

  const openSummaryEditor = () => {
    setSummaryForm({
      hypothesis: savedSummary?.hypothesis || recommendations.summary || "",
      steps: (savedSummary?.recommended_steps || recommendations.steps || []).join("\n"),
      confidence: savedSummary?.confidence || solution.confidence || "medium",
    });
    setSummaryMsg("");
    setEditingSummary(true);
  };

  const persistSummary = async () => {
    if (detailEventId === null) return;
    const steps = summaryForm.steps.split("\n").map((step) => step.trim()).filter(Boolean);
    if (!summaryForm.hypothesis.trim() || !steps.length) {
      setSummaryMsg("A hypothesis and at least one step are required.");
      return;
    }
    setSummaryBusy("save");
    setSummaryMsg("");
    try {
      const saved = await saveSolutionSummary({
        event_id: detailEventId,
        hypothesis: summaryForm.hypothesis.trim(),
        recommended_steps: steps,
        confidence: summaryForm.confidence,
        generated_by: "analyst",
      });
      setSavedSummary(saved || null);
      setEditingSummary(false);
      setSummaryMsg("Summary saved.");
    } catch (requestError) {
      setSummaryMsg(requestError.message);
    } finally {
      setSummaryBusy("");
    }
  };

  const removeSummary = async () => {
    if (detailEventId === null) return;
    setSummaryBusy("delete");
    setSummaryMsg("");
    try {
      await deleteSolutionSummary(detailEventId);
      setSavedSummary(null);
      setSummaryMsg("Saved summary deleted.");
    } catch (requestError) {
      setSummaryMsg(requestError.message);
    } finally {
      setSummaryBusy("");
    }
  };

  const record = [
    ["Device", device.device_name || alert.d.name || "N/A"],
    ["Device ID", alert.d.id ?? device.device_id ?? "N/A"],
    ["Node ID", device.node_id],
    ["IP address", device.ip_address || alert.d.ip || "N/A"],
    ["Site code", device.site_code],
    ["Site", device.site_name],
    ["Device type", device.machine_type],
    ["Vendor", device.vendor],
    ["Location", device.location],
    ["Device created", device.created_at],
    ["Event type ID", eventType.event_type_id],
    ["Event type", eventTypeName || "N/A"],
    ["Event severity", eventType.severity],
    ["Category", eventType.category || alert.category || "N/A"],
    ["Message", alert.msg || "N/A"],
    ["Event time", opened.label],
  ].filter(([, value]) => value !== null && value !== undefined && value !== "");

  return (
    <div className="grid gap-5" aria-label="Alert details">
      <div className="flex flex-wrap items-center gap-3">
        <Link
          to="/alerts"
          className="inline-flex items-center gap-2 rounded-lg border border-line bg-paper px-3 py-2 text-[13px] font-semibold text-ink-2 transition-colors hover:border-brand hover:text-brand dark:border-white/15 dark:bg-white/5"
        >
          <FaArrowLeft /> Back to Alerts Console
        </Link>
        <span className="ml-auto text-[13px] text-ink-3">
          Event <b className="font-mono text-ink-2">{absoluteEventId}</b>
        </span>
      </div>

      {error && (
        <div role="alert" className="flex flex-wrap items-center gap-3 rounded-lg border border-p1/25 bg-p1-bg px-4 py-3 text-[13.5px] text-p1-ink">
          <FaExclamationTriangle />
          <div className="min-w-0 flex-1">
            <b className="block">Event details could not be loaded</b>
            <span>{error}</span>
          </div>
          {detailEventId !== null ? (
            <button
              type="button"
              onClick={() => setRetryCount((count) => count + 1)}
              disabled={loadingInfo}
              className="inline-flex items-center gap-2 rounded-lg bg-p1 px-3 py-1.5 text-[13px] font-semibold text-white disabled:opacity-60"
            >
              {loadingInfo ? <FaSpinner className="animate-spin" /> : null}
              {loadingInfo ? "Retrying…" : "Retry"}
            </button>
          ) : (
            <Link to="/alerts" className="rounded-lg bg-p1 px-3 py-1.5 text-[13px] font-semibold text-white">Back to Alerts</Link>
          )}
        </div>
      )}

      {dataMismatch && (
        <div role="status" className="flex items-center gap-3 rounded-lg border border-warn/30 bg-warn-bg px-4 py-3 text-[13.5px] text-warn">
          <FaExclamationTriangle />
          <div>
            <b className="block">Data mismatch detected</b>
            <span>The event says Interface Up, but the latest ping check failed.</span>
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 gap-5 xl:grid-cols-[minmax(0,1.6fr)_minmax(0,1fr)]">
        <div className="grid gap-5">
          <Panel icon={<FaNetworkWired />} kicker="Preliminary" title="Preliminary checks">
            <div className="grid gap-4">
              <AlertContext alert={alert} device={device} ticketNumber={ticketNumber} ticketUrl={ticketUrl} opened={opened} onCopyIp={copyIp} />
              {loadingInfo ? (
                <LoadingSkeleton rows={2} />
              ) : (
                <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                  <CheckTile kind="ping" value={pingResult} />
                  <CheckTile kind="traceroute" value={routeResult} />
                </div>
              )}
              {!loadingInfo && checks.nslookup && (
                <div className="rounded-xl border border-line bg-paper-2 px-4 py-3 text-[13px] dark:border-white/10 dark:bg-white/5">
                  <b className="text-ink dark:text-white">DNS lookup</b>
                  <span className="mt-0.5 block text-ink-2">
                    {checks.nslookup.reverse_lookup || checks.nslookup.addresses?.join(", ") || "No DNS result returned"}
                  </span>
                  {checks.nslookup.error && <small className="text-p1-ink">{checks.nslookup.error}</small>}
                </div>
              )}
            </div>
          </Panel>

          <Panel icon={<FaServer />} kicker="Record" title="Device and event">
            {loadingInfo ? (
              <LoadingSkeleton rows={6} />
            ) : (
              <dl className="grid grid-cols-1 gap-x-6 gap-y-1.5 text-[13.5px] sm:grid-cols-2">
                {record.map(([label, value]) => (
                  <div key={label} className="flex gap-2 border-b border-line/60 py-1 dark:border-white/5">
                    <dt className="w-32 shrink-0 text-ink-3">{label}</dt>
                    <dd className="min-w-0 break-words text-ink-2">{value}</dd>
                  </div>
                ))}
              </dl>
            )}
          </Panel>

          <Panel
            icon={<FaHistory />}
            kicker="Event history"
            title="Recent error logs"
            aside={loadingInfo ? "Loading" : `${recentLogs.length} returned`}
          >
            {loadingInfo ? (
              <LoadingSkeleton rows={3} />
            ) : recentLogs.length ? (
              <div className="grid gap-2.5">
                {recentLogs.map((log, index) => (
                  <article key={log.event_id || `${log.event_time}-${index}`} className="rounded-xl border border-line bg-paper-2 px-4 py-3 dark:border-white/10 dark:bg-white/5">
                    <div className="flex flex-wrap items-center gap-3 text-[13px]">
                      <b className="font-mono text-ink dark:text-white">Event {log.event_id ?? "N/A"}</b>
                      <time className="text-ink-3">{log.event_time || "Time unavailable"}</time>
                      <span className="ml-auto rounded-full bg-paper-3 px-2 py-0.5 text-[11.5px] font-semibold text-ink-2 dark:bg-white/10">
                        {log.current_status === null || log.current_status === undefined
                          ? "Status unavailable"
                          : Number(log.current_status) === 0 ? "Down (0)" : Number(log.current_status) === 1 ? "Up (1)" : `Status ${log.current_status}`}
                      </span>
                    </div>
                    <p className="mt-1.5 text-[13px] text-ink-2">{log.message || "No event message returned."}</p>
                    {log.raw_detail && (
                      <pre className="mt-2 max-h-40 overflow-auto whitespace-pre-wrap rounded-lg border border-line bg-paper p-2.5 font-mono text-[11.5px] text-ink-2 dark:border-white/10 dark:bg-transparent">{log.raw_detail}</pre>
                    )}
                  </article>
                ))}
              </div>
            ) : (
              <p className="text-[13px] text-ink-3">No recent error logs were returned for this device and event type.</p>
            )}
          </Panel>

          <Panel
            icon={<FaHistory />}
            kicker="History"
            title="Related incidents"
            aside={
              <span>
                <b className="text-ink-2">{loadingInfo ? "—" : history.total_incidents_6m ?? "0"}</b> occurrences · 6 months
              </span>
            }
          >
            {loadingInfo ? (
              <LoadingSkeleton rows={3} />
            ) : (
              <div className="grid gap-4">
                <WeeklySparkline tickets={history.related_tickets || []} />
                <RelatedTickets tickets={history.related_tickets || []} lastEventId={history.last_event_id} />
                {!history.related_tickets?.length && (
                  <p className="text-[13px] text-ink-3">
                    The event history reports {history.total_incidents_6m ?? 0} occurrences, but the API returned no related ticket records for this alert.
                  </p>
                )}
              </div>
            )}
          </Panel>
        </div>

        {/* Right rail */}
        <div className="grid gap-5 self-start">
          <Panel
            icon={<FaLightbulb />}
            kicker="Remediation"
            title="Recommended steps"
            aside={solutionSource && !loadingInfo ? <span className="rounded-full bg-brand-tint px-2.5 py-0.5 text-[11.5px] font-semibold text-brand dark:bg-brand/20 dark:text-brand-hi">{solutionSource}</span> : null}
          >
            {loadingInfo ? (
              <LoadingSkeleton rows={4} />
            ) : error ? (
              <p className="text-[13px] text-ink-3">Recommendations failed to load. Use Retry above to request them again.</p>
            ) : recommendations.steps.length || recommendations.plainText || recommendations.summary ? (
              <div className="grid gap-3">
                {recommendations.summary && (
                  <p className="rounded-xl border border-brand-tint-2 bg-brand-tint px-4 py-3 text-[14px] font-medium text-ink dark:border-brand/30 dark:bg-brand/15 dark:text-white">
                    {recommendations.summary}
                  </p>
                )}
                {recommendations.steps.length > 0 && (
                  <ol className="grid gap-2">
                    {recommendations.steps.map((step, index) => (
                      <li key={index} className="flex gap-3 rounded-lg border border-line bg-paper px-3 py-2.5 text-[13.5px] text-ink-2 dark:border-white/10 dark:bg-white/5">
                        <span className="grid h-6 w-6 flex-none place-items-center rounded-full bg-brand-tint text-[12px] font-bold text-brand dark:bg-brand/25 dark:text-brand-hi">
                          {index + 1}
                        </span>
                        {step}
                      </li>
                    ))}
                  </ol>
                )}
                {recommendations.plainText && (
                  <p className="whitespace-pre-wrap text-[13.5px] text-ink-2">{recommendations.plainText}</p>
                )}
              </div>
            ) : (
              <p className="text-[13px] text-ink-3">No recommended solution was returned for this event. Retry to request the latest solution.</p>
            )}

            {/* Analyst-owned cached summary (POST/DELETE /solution-summaries) */}
            <div className="mt-4 border-t border-dashed border-line pt-4 dark:border-white/10">
              <div className="flex flex-wrap items-center gap-2">
                <h4 className="text-[11px] font-semibold tracking-wider text-ink-3 uppercase">Saved summary</h4>
                {savedSummary ? (
                  <span className="rounded-full bg-good-bg px-2.5 py-0.5 text-[11.5px] font-semibold text-good">
                    Cached{savedSummary.generated_by ? ` · ${savedSummary.generated_by}` : ""}
                  </span>
                ) : (
                  <span className="rounded-full bg-paper-3 px-2.5 py-0.5 text-[11.5px] font-semibold text-ink-3 dark:bg-white/10">
                    Not saved
                  </span>
                )}
                <div className="ml-auto flex gap-2">
                  {!editingSummary && (
                    <button
                      type="button"
                      onClick={openSummaryEditor}
                      className="inline-flex items-center gap-1.5 rounded-lg border border-line-strong bg-paper px-3 py-1.5 text-[12.5px] font-semibold text-ink-2 transition-colors hover:border-brand hover:text-brand dark:border-white/15 dark:bg-white/5"
                    >
                      <FaPencilAlt /> {savedSummary ? "Edit" : "Save summary"}
                    </button>
                  )}
                  {savedSummary && !editingSummary && (
                    <button
                      type="button"
                      onClick={removeSummary}
                      disabled={summaryBusy === "delete"}
                      className="inline-flex items-center gap-1.5 rounded-lg border border-p1/25 bg-p1-bg px-3 py-1.5 text-[12.5px] font-semibold text-p1-ink transition-colors hover:border-p1 disabled:opacity-60"
                    >
                      {summaryBusy === "delete" ? <FaSpinner className="animate-spin" /> : <FaTrashAlt />} Delete
                    </button>
                  )}
                </div>
              </div>

              {editingSummary && (
                <div className="mt-3 grid gap-3 rounded-xl border border-line bg-paper-2 p-3 dark:border-white/10 dark:bg-white/5">
                  <label className="grid gap-1 text-[12.5px] font-semibold text-ink-2">
                    Hypothesis
                    <textarea
                      rows={2}
                      value={summaryForm.hypothesis}
                      onChange={(event) => setSummaryForm({ ...summaryForm, hypothesis: event.target.value })}
                      className="resize-y rounded-lg border border-line-strong bg-paper px-3 py-2 text-[13px] font-normal text-ink outline-none focus:border-brand focus:ring-2 focus:ring-brand/20 dark:border-white/15 dark:bg-white/5 dark:text-white"
                    />
                  </label>
                  <label className="grid gap-1 text-[12.5px] font-semibold text-ink-2">
                    Recommended steps (one per line)
                    <textarea
                      rows={4}
                      value={summaryForm.steps}
                      onChange={(event) => setSummaryForm({ ...summaryForm, steps: event.target.value })}
                      className="resize-y rounded-lg border border-line-strong bg-paper px-3 py-2 font-mono text-[12.5px] font-normal text-ink outline-none focus:border-brand focus:ring-2 focus:ring-brand/20 dark:border-white/15 dark:bg-white/5 dark:text-white"
                    />
                  </label>
                  <label className="grid gap-1 text-[12.5px] font-semibold text-ink-2">
                    Confidence
                    <select
                      value={summaryForm.confidence}
                      onChange={(event) => setSummaryForm({ ...summaryForm, confidence: event.target.value })}
                      className="w-40 rounded-lg border border-line-strong bg-paper px-3 py-2 text-[13px] font-normal text-ink outline-none focus:border-brand dark:border-white/15 dark:bg-white/5 dark:text-white"
                    >
                      <option value="high">High</option>
                      <option value="medium">Medium</option>
                      <option value="low">Low</option>
                    </select>
                  </label>
                  <div className="flex justify-end gap-2">
                    <button
                      type="button"
                      onClick={() => setEditingSummary(false)}
                      className="rounded-lg border border-line-strong bg-paper px-3 py-1.5 text-[12.5px] font-medium text-ink-2 transition-colors hover:bg-paper-3 dark:border-white/15 dark:bg-white/5"
                    >
                      Cancel
                    </button>
                    <button
                      type="button"
                      onClick={persistSummary}
                      disabled={summaryBusy === "save"}
                      className="inline-flex items-center gap-1.5 rounded-lg bg-brand px-3 py-1.5 text-[12.5px] font-semibold text-white transition-colors hover:bg-brand-hi disabled:opacity-60"
                    >
                      {summaryBusy === "save" ? <FaSpinner className="animate-spin" /> : <FaSave />} Save
                    </button>
                  </div>
                </div>
              )}
              {summaryMsg && <p className="mt-2 text-[12.5px] text-ink-3">{summaryMsg}</p>}
            </div>
          </Panel>

          <Panel icon={<FaTerminal />} kicker="Tools" title="Diagnostics">
            <label htmlFor="diagnostic-host" className="mb-1.5 block text-[13px] font-semibold text-ink-2">Target host</label>
            <input
              id="diagnostic-host"
              value={host}
              onChange={(event) => setHost(event.target.value)}
              placeholder="IP address or hostname"
              className="w-full rounded-lg border border-line-strong bg-paper px-3 py-2 text-[13.5px] text-ink outline-none transition-colors focus:border-brand focus:ring-2 focus:ring-brand/20 dark:border-white/15 dark:bg-white/5 dark:text-white"
            />
            <div className="mt-3 flex flex-wrap gap-2">
              {["ping", "traceroute", "nslookup"].map((kind) => (
                <button
                  key={kind}
                  type="button"
                  disabled={!host.trim() || !!busy}
                  onClick={() => run(kind)}
                  className="inline-flex items-center gap-1.5 rounded-lg border border-line-strong bg-paper px-3 py-2 text-[13px] font-semibold text-ink-2 transition-colors hover:border-brand hover:text-brand disabled:cursor-not-allowed disabled:opacity-50 dark:border-white/15 dark:bg-white/5"
                >
                  {busy === kind ? <FaSpinner className="animate-spin" /> : <FaTerminal className="text-[11px]" />}
                  {kind}
                </button>
              ))}
            </div>
            {diagnosticError && <p role="alert" className="mt-2 text-[12.5px] text-p1-ink">{diagnosticError}</p>}
            <div className="mt-3 mb-1.5 flex items-center gap-2 text-[11px] font-semibold tracking-wider text-ink-3 uppercase">
              Output {busy && <FaSpinner className="animate-spin text-brand" />}
            </div>
            <pre aria-live="polite" aria-label="Diagnostic output" className="max-h-64 overflow-auto whitespace-pre-wrap rounded-lg border border-line bg-paper-2 p-3 font-mono text-[12px] text-ink-2 dark:border-white/10 dark:bg-white/5">
              {diagnosticLines.length ? diagnosticLines.join("\n") : "Output will appear here when a check runs."}
            </pre>
          </Panel>
        </div>
      </div>
    </div>
  );
}
