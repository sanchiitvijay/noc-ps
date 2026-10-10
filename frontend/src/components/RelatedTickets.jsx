import { useState } from "react";
import { FaTicketAlt, FaChevronDown, FaChevronUp } from "react-icons/fa";

const TICKET_FIELDS = [
  ["State", "state"],
  ["Created", "created_on"],
  ["Updated", "updated_on"],
  ["Closed", "closed_at"],
  ["Severity", "severity"],
  ["Frequency", "frequency"],
  ["Device type", "device_type"],
  ["Device name", "device_name"],
  ["IP address", "ip_address"],
  ["Device ID", "device_id"],
  ["Event time", "event_time"],
  ["Event type", "event_type_name"],
  ["Event message", "event_message"],
  ["Event ID", "last_event_id"],
];

const DATE_KEYS = ["created_on", "updated_on", "closed_at", "event_time"];

function display(value) {
  return value === null || value === undefined || value === "" ? "N/A" : String(value);
}

function ticketStateStyle(state) {
  const value = String(state || "").toLowerCase();
  if (["closed", "resolved", "complete", "completed"].some((word) => value.includes(word))) {
    return "bg-good-bg text-good";
  }
  if (["open", "new", "active", "on hold", "pending"].some((word) => value.includes(word))) {
    return "bg-p2-bg text-p2-ink";
  }
  return "bg-paper-3 text-ink-2";
}

function TicketDate({ value }) {
  if (!value) return "N/A";
  const text = String(value);
  const match = text.match(/^(\d{2})-(\d{2})-(\d{4})(?:\s+(.*))?$/);
  const date = match
    ? new Date(`${match[3]}-${match[1]}-${match[2]}T${(match[4] || "00:00:00").replace(" ", "T")}`)
    : new Date(value);
  if (Number.isNaN(date.getTime())) return text;
  const seconds = Math.round((date.getTime() - Date.now()) / 1000);
  const units = [
    ["year", 31536000],
    ["month", 2592000],
    ["week", 604800],
    ["day", 86400],
    ["hour", 3600],
    ["minute", 60],
  ];
  const [unit, size] = units.find(([, size]) => Math.abs(seconds) >= size) || ["minute", 60];
  const relative = new Intl.RelativeTimeFormat(undefined, { numeric: "auto" }).format(
    Math.round(seconds / size),
    unit,
  );
  return (
    <time title={date.toISOString()} className="text-ink-2">
      {relative}
    </time>
  );
}

export default function RelatedTickets({ tickets = [], lastEventId }) {
  const [emptyExpanded, setEmptyExpanded] = useState(false);

  if (!tickets.length) {
    return (
      <div className="overflow-hidden rounded-xl border border-line bg-paper-2 dark:border-white/10 dark:bg-white/5">
        <button
          type="button"
          aria-expanded={emptyExpanded}
          onClick={() => setEmptyExpanded((value) => !value)}
          className="flex w-full items-center gap-2 px-3 py-2.5 text-left text-[13px] font-semibold text-ink-2 transition-colors hover:bg-paper-3 dark:hover:bg-white/5"
        >
          <FaTicketAlt className="text-ink-3" />
          <span>View details</span>
          <span className="ml-auto text-ink-3">
            {emptyExpanded ? <FaChevronUp /> : <FaChevronDown />}
          </span>
        </button>
        {emptyExpanded && (
          <div className="border-t border-line px-3 py-2.5 text-[13px] text-ink-3 dark:border-white/10">
            {lastEventId !== null && lastEventId !== undefined && (
              <p className="mb-1">
                Historical last event ID: <b className="text-ink-2">{display(lastEventId)}</b>
              </p>
            )}
            <span>No related ticket details were returned for this alert.</span>
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="grid gap-2">
      {tickets.map((ticket, index) => (
        <TicketItem
          key={ticket.ticket_number || `${ticket.ticket_type || "ticket"}-${index}`}
          ticket={ticket}
          lastEventId={lastEventId}
        />
      ))}
    </div>
  );
}

function TicketItem({ ticket, lastEventId }) {
  const [expanded, setExpanded] = useState(false);
  return (
    <article className="overflow-hidden rounded-xl border border-line bg-paper shadow-card dark:border-white/10 dark:bg-white/5">
      <div className="flex flex-wrap items-center gap-3 px-3.5 py-2.5">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <b className="font-mono text-[13px] text-brand dark:text-brand-hi">{display(ticket.ticket_number)}</b>
            <span className={`rounded-full px-2 py-0.5 text-[11px] font-bold ${ticketStateStyle(ticket.state)}`}>
              {display(ticket.state)}
            </span>
          </div>
          <span className="line-clamp-1 text-[13px] text-ink-2">{display(ticket.short_description)}</span>
        </div>
        <button
          type="button"
          aria-expanded={expanded}
          onClick={() => setExpanded((value) => !value)}
          className="inline-flex items-center gap-2 rounded-lg border border-line-strong px-2.5 py-1.5 text-[12.5px] font-semibold text-ink-2 transition-colors hover:border-brand hover:text-brand dark:border-white/15"
        >
          <FaTicketAlt className="text-ink-3" />
          <span>{expanded ? "Hide details" : "View details"}</span>
          {expanded ? <FaChevronUp /> : <FaChevronDown />}
        </button>
      </div>

      {expanded && (
        <div className="animate-fade border-t border-dashed border-line px-3.5 py-3 dark:border-white/10">
          <div className="mb-2 flex items-center gap-3">
            <div>
              <span className="text-[11px] font-semibold uppercase tracking-wider text-ink-3">
                {display(ticket.ticket_type)} ticket
              </span>
              <h4 className="font-mono text-[14px] font-bold text-ink dark:text-white">
                {display(ticket.ticket_number)}
              </h4>
            </div>
            <span className={`ml-auto rounded-full px-2 py-0.5 text-[11px] font-bold ${ticketStateStyle(ticket.state)}`}>
              {display(ticket.state)}
            </span>
          </div>

          {lastEventId !== null && lastEventId !== undefined && (
            <p className="mb-2 text-[12.5px] text-ink-3">
              Historical last event ID: <b className="text-ink-2">{display(lastEventId)}</b>
            </p>
          )}

          <div className="mb-3 rounded-lg border-l-[3px] border-brand bg-paper-2 px-3 py-2 dark:bg-white/5">
            <b className="text-[13.5px] text-ink dark:text-white">{display(ticket.short_description)}</b>
            <p className="mt-1 text-[13px] text-ink-2">{display(ticket.description)}</p>
          </div>

          <dl className="grid grid-cols-1 gap-x-6 gap-y-1.5 text-[13px] sm:grid-cols-2">
            {TICKET_FIELDS.map(([label, key]) => (
              <div key={key} className="flex gap-2 border-b border-line/60 py-1 dark:border-white/5">
                <dt className="w-28 shrink-0 text-ink-3">{label}</dt>
                <dd className="min-w-0 break-words text-ink-2">
                  {DATE_KEYS.includes(key) ? <TicketDate value={ticket[key]} /> : display(ticket[key])}
                </dd>
              </div>
            ))}
          </dl>

          <h5 className="mt-3 mb-1.5 text-[11px] font-semibold uppercase tracking-wider text-ink-3">Work notes</h5>
          <pre className="max-h-52 overflow-auto whitespace-pre-wrap rounded-lg border border-line bg-paper-2 p-3 font-mono text-[12px] text-ink-2 dark:border-white/10 dark:bg-white/5">
            {display(ticket.work_notes)}
          </pre>
        </div>
      )}
    </article>
  );
}
