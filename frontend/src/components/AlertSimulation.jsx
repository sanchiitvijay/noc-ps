import { useEffect, useState } from "react";
import { FaBolt, FaSpinner, FaCheckCircle } from "react-icons/fa";
import { getSimulatedLogs } from "../services/api";

export default function AlertSimulation({ onEvents }) {
  const [events, setEvents] = useState([]);
  const [visibleCount, setVisibleCount] = useState(0);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
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
    setError("");
    setEvents([]);
    setVisibleCount(0);

    try {
      const batch = await getSimulatedLogs({ count: 10, synthetic_ratio: 0 });
      setEvents(batch);
      setVisibleCount(0);
      if (!batch.length) setError("The simulation endpoint returned no events. Try again.");
    } catch (requestError) {
      setError(`Could not load simulated events: ${requestError.message}. Try again.`);
    } finally {
      setBusy(false);
    }
  };

  return (
    <section
      aria-label="Live event simulation"
      className="flex flex-wrap items-center gap-4 rounded-card border border-brand-tint-2 bg-linear-to-r from-brand-tint to-paper px-5 py-4 shadow-card dark:border-white/10 dark:from-brand-tint/10 dark:to-transparent"
    >
      <div className="grid h-11 w-11 place-items-center rounded-xl bg-brand text-white shadow-sm">
        <FaBolt className="text-lg" />
      </div>
      <div className="min-w-0 flex-1">
        <h3 className="text-[15px] font-bold text-ink dark:text-white">Live event simulation</h3>
        <p className="text-[13px] text-ink-3">
          Fetch a randomized event batch from the backend and stream it into this console.
        </p>
      </div>

      <button
        type="button"
        onClick={trigger}
        disabled={busy || streaming}
        className="inline-flex items-center gap-2 rounded-lg bg-brand px-4 py-2 text-sm font-semibold text-white shadow-sm transition-colors hover:bg-brand-hi disabled:cursor-not-allowed disabled:opacity-50"
      >
        {busy || streaming ? <FaSpinner className="animate-spin" /> : <FaBolt />}
        {busy ? "Fetching events…" : streaming ? "Streaming events…" : events.length ? "Run simulation again" : "Trigger simulation"}
      </button>

      {error && (
        <p role="alert" className="w-full text-[13px] font-medium text-p1-ink">
          {error}
        </p>
      )}
      {events.length > 0 && !error && (
        <div
          role="status"
          aria-live="polite"
          className="flex w-full items-center gap-2 text-[13px] text-ink-2"
        >
          <FaCheckCircle className={streaming ? "text-brand" : "text-good"} />
          {streaming
            ? `Streaming ${visibleCount} of ${events.length} events above the existing logs`
            : `Stream complete · ${events.length} events added above existing logs`}
        </div>
      )}
    </section>
  );
}
