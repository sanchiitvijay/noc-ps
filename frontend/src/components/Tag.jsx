const STYLES = {
  Critical: "bg-p1-bg text-p1-ink",
  Warning: "bg-p2-bg text-p2-ink",
  Info: "bg-brand-tint text-brand",
  Unknown: "bg-paper-3 text-ink-3",
  P1: "bg-p1-bg text-p1-ink",
  P2: "bg-p2-bg text-p2-ink",
  P3: "bg-p3-bg text-p3-ink",
  P4: "bg-p4-bg text-p4-ink",
  Healthy: "bg-good-bg text-good",
};

/** Compact severity / status pill with a colour swatch. */
export default function Tag({ s }) {
  const style = STYLES[s] || STYLES.Unknown;
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-md px-2 py-0.5 text-[11.5px] font-bold uppercase tracking-wide ${style}`}
    >
      <i className="h-2 w-2 rounded-sm bg-current" aria-hidden="true" />
      {s || "Unknown"}
    </span>
  );
}
