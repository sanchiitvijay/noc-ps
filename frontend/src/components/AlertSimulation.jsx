import { useEffect, useState } from 'react';
import { getSimulatedLogs } from '../services/api';

export default function AlertSimulation({ onEvents }) {
  const [events, setEvents] = useState([]);
  const [visibleCount, setVisibleCount] = useState(0);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const streaming = visibleCount < events.length;

  useEffect(() => {
    onEvents(events.slice(0, visibleCount));
  }, [events, visibleCount, onEvents]);

  useEffect(() => {
    if (!streaming) return undefined;
    const timer = window.setTimeout(() => setVisibleCount((count) => count + 1), 450);
    return () => window.clearTimeout(timer);
  }, [streaming, visibleCount]);

  const trigger = async () => {
    if (busy || streaming) return;
    setBusy(true);
    setError('');
    setEvents([]);
    setVisibleCount(0);

    try {
      const batch = await getSimulatedLogs({ count: 10, synthetic_ratio: 0 });
      setEvents(batch);
      setVisibleCount(0);
      if (!batch.length) setError('The simulation endpoint returned no events. Try again.');
    } catch (requestError) {
      setError(`Could not load simulated events: ${requestError.message}. Try again.`);
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="c alert-simulation-panel" aria-label="Live event simulation">
      <div className="alert-simulation-heading">
        <div>
          <h3>Live event simulation</h3>
          <p className="mu">Fetch a randomized event batch from the backend and stream it into this console.</p>
        </div>
        <button type="button" onClick={trigger} disabled={busy || streaming}>
          {busy ? 'Fetching events…' : streaming ? 'Streaming events…' : events.length ? 'Run simulation again' : 'Trigger simulation'}
        </button>
      </div>

      {error && <p className="alert-simulation-error" role="alert">{error}</p>}
      {events.length > 0 && <div className="alert-simulation-status" role="status" aria-live="polite">
        {streaming ? `Streaming ${visibleCount} of ${events.length} events above the existing logs` : `Stream complete · ${events.length} events added above existing logs`}
      </div>}
    </section>
  );
}
