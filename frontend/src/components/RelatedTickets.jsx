import { useState } from 'react';

const TICKET_FIELDS = [
  ['State', 'state'],
  ['Created', 'created_on'],
  ['Updated', 'updated_on'],
  ['Closed', 'closed_at'],
  ['Severity', 'severity'],
  ['Frequency', 'frequency'],
  ['Device type', 'device_type'],
  ['Device name', 'device_name'],
  ['IP address', 'ip_address'],
  ['Device ID', 'device_id'],
  ['Event time', 'event_time'],
  ['Event type', 'event_type_name'],
  ['Event message', 'event_message'],
  ['Event ID', 'last_event_id'],
];

function display(value) {
  return value === null || value === undefined || value === '' ? 'N/A' : String(value);
}

function TicketDate({ value }) {
  if (!value) return 'N/A';
  const text = String(value);
  const match = text.match(/^(\d{2})-(\d{2})-(\d{4})(?:\s+(.*))?$/);
  const date = match ? new Date(`${match[3]}-${match[1]}-${match[2]}T${(match[4] || '00:00:00').replace(' ', 'T')}`) : new Date(value);
  if (Number.isNaN(date.getTime())) return text;
  const seconds = Math.round((date.getTime() - Date.now()) / 1000);
  const units = [['year', 31536000], ['month', 2592000], ['week', 604800], ['day', 86400], ['hour', 3600], ['minute', 60]];
  const [unit, size] = units.find(([, size]) => Math.abs(seconds) >= size) || ['minute', 60];
  const relative = new Intl.RelativeTimeFormat(undefined, { numeric: 'auto' }).format(Math.round(seconds / size), unit);
  return <time title={date.toISOString()}>{relative}</time>;
}

export default function RelatedTickets({ tickets = [], lastEventId }) {
  const [emptyExpanded, setEmptyExpanded] = useState(false);
  if (!tickets.length) {
    return (
      <div className="related-ticket-empty">
        <button type="button" className="related-ticket-toggle" aria-expanded={emptyExpanded} onClick={() => setEmptyExpanded((value) => !value)}>
          <TicketIcon /><span>View details</span><ChevronIcon expanded={emptyExpanded} />
        </button>
        {emptyExpanded && <div className="related-ticket-empty-details">{lastEventId !== null && lastEventId !== undefined && <p>Historical last event ID: <b>{display(lastEventId)}</b></p>}<span className="mu">No related ticket details were returned for this alert.</span></div>}
      </div>
    );
  }

  return (
    <div className="related-ticket-list">
      {tickets.map((ticket, index) => (
        <TicketItem key={ticket.ticket_number || `${ticket.ticket_type || 'ticket'}-${index}`} ticket={ticket} lastEventId={lastEventId} />
      ))}
    </div>
  );
}

function TicketItem({ ticket, lastEventId }) {
  const [expanded, setExpanded] = useState(false);
  return (
    <article className="related-ticket">
      <div className="related-ticket-summary">
        <div className="related-ticket-copy">
          <div className="related-ticket-heading"><b>{display(ticket.ticket_number)}</b><span className="related-ticket-state">{display(ticket.state)}</span></div>
          <span className="related-ticket-short-description">{display(ticket.short_description)}</span>
        </div>
        <button type="button" className="related-ticket-toggle" aria-expanded={expanded} onClick={() => setExpanded((value) => !value)}>
          <TicketIcon /><span>{expanded ? 'Hide details' : 'View details'}</span><ChevronIcon expanded={expanded} />
        </button>
      </div>
      {expanded && (
        <div className="related-ticket-details">
          <div className="related-ticket-header">
            <div><span className="mu">{display(ticket.ticket_type)} TICKET</span><h4>{display(ticket.ticket_number)}</h4></div>
            <span className="related-ticket-state">{display(ticket.state)}</span>
          </div>
          {lastEventId !== null && lastEventId !== undefined && <p className="mu related-ticket-last-event">Historical last event ID: <b>{display(lastEventId)}</b></p>}
          <div className="related-ticket-description">
            <b>{display(ticket.short_description)}</b>
            <p>{display(ticket.description)}</p>
          </div>
          <dl className="related-ticket-fields">
            {TICKET_FIELDS.map(([label, key]) => (
              <div key={key}><dt>{label}</dt><dd>{['created_on', 'updated_on', 'closed_at', 'event_time'].includes(key) ? <TicketDate value={ticket[key]} /> : display(ticket[key])}</dd></div>
            ))}
          </dl>
          <section className="related-ticket-notes"><h5>Work notes</h5><pre>{display(ticket.work_notes)}</pre></section>
        </div>
      )}
    </article>
  );
}

function TicketIcon() {
  return <svg aria-hidden="true" viewBox="0 0 20 20" width="15" height="15" fill="none" stroke="currentColor" strokeWidth="1.6"><path d="M4 3.5h8l4 4v9H4z" /><path d="M12 3.5v4h4M7 11h6M7 14h6" /></svg>;
}

function ChevronIcon({ expanded }) {
  return <svg className={`related-ticket-chevron${expanded ? ' expanded' : ''}`} aria-hidden="true" viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" strokeWidth="1.8"><path d="m4 6 4 4 4-4" /></svg>;
}
