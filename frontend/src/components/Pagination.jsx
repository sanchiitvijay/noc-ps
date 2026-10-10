import { FaChevronLeft, FaChevronRight } from "react-icons/fa";

/**
 * Sliding-window pagination shared by every page (Alerts, Sites, Tickets,
 * Admin). Shows up to `windowSize` page numbers around the current page, with
 * ellipses for the gaps, plus prev/next buttons and a "Page X of Y" label.
 *
 * Props:
 *   page          current page (1-indexed)
 *   totalPages    total number of pages
 *   onPageChange  (nextPage) => void
 *   disabled      disables all buttons while data is loading
 *   windowSize    max page buttons to show (default 10, like the alerts console)
 *   className     optional wrapper class overrides
 */
export function buildPageWindow(page, totalPages, maxButtons = 10) {
  const pages = Math.max(1, Math.ceil(Number(totalPages) || 1));
  const range = new Set(
    [1, pages, page - 2, page - 1, page, page + 1, page + 2].filter(
      (p) => p >= 1 && p <= pages,
    ),
  );
  const ordered = [...range].sort((a, b) => a - b);
  if (ordered.length <= maxButtons) return ordered;

  // Cap the number of buttons while always keeping the current page.
  const keep = new Set([page]);
  for (let step = 1; keep.size < maxButtons - 2; step += 1) {
    if (page - step >= 1) keep.add(page - step);
    if (keep.size < maxButtons - 2 && page + step <= pages) keep.add(page + step);
  }
  const remaining = maxButtons - keep.size;
  const edges = remaining === 2 ? [1, pages] : remaining === 1 ? [1] : [];
  return [...new Set([...edges, ...keep])].sort((a, b) => a - b);
}

export default function Pagination({
  page,
  totalPages,
  onPageChange,
  disabled = false,
  windowSize = 10,
  className = "flex flex-wrap items-center justify-center gap-1.5 border-t border-line px-4 py-3 dark:border-white/10",
}) {
  const pages = Math.max(1, Math.ceil(Number(totalPages) || 1));
  if (pages <= 1) {
    return (
      <div className={`justify-center px-4 py-3 text-center text-[12.5px] text-ink-3 ${className}`}>
        Page 1 of 1
      </div>
    );
  }

  const numbers = buildPageWindow(page, pages, windowSize);
  const rendered = [];
  let previous = 0;
  numbers.forEach((n) => {
    if (previous && n - previous > 1) {
      rendered.push(
        <span key={`gap-${n}`} className="px-1 text-ink-3" aria-hidden="true">
          …
        </span>,
      );
    }
    rendered.push(
      <button
        key={n}
        type="button"
        aria-current={n === page ? "page" : undefined}
        disabled={disabled || n === page}
        onClick={() => onPageChange(n)}
        className={`h-9 min-w-9 rounded-lg border px-2 text-[13px] font-semibold transition-colors ${
          n === page
            ? "border-brand bg-brand text-white"
            : "border-line bg-paper text-ink-2 hover:border-brand hover:text-brand dark:border-white/15 dark:bg-white/5"
        } disabled:opacity-40 disabled:cursor-not-allowed`}
      >
        {n}
      </button>,
    );
    previous = n;
  });

  return (
    <div className={className}>
      <button
        type="button"
        disabled={disabled || page <= 1}
        onClick={() => onPageChange(page - 1)}
        className="inline-grid h-9 w-9 place-items-center rounded-lg border border-line bg-paper text-ink-2 transition-colors hover:border-brand hover:text-brand disabled:opacity-40 disabled:cursor-not-allowed dark:border-white/15 dark:bg-white/5"
        aria-label="Previous page"
      >
        <FaChevronLeft />
      </button>
      {rendered}
      <button
        type="button"
        disabled={disabled || page >= pages}
        onClick={() => onPageChange(page + 1)}
        className="inline-grid h-9 w-9 place-items-center rounded-lg border border-line bg-paper text-ink-2 transition-colors hover:border-brand hover:text-brand disabled:opacity-40 disabled:cursor-not-allowed dark:border-white/15 dark:bg-white/5"
        aria-label="Next page"
      >
        <FaChevronRight />
      </button>
      <span className="ml-2 px-1 text-[13px] text-ink-3">
        Page <b className="text-ink-2">{page}</b> of {pages}
      </span>
    </div>
  );
}
