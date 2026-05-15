/**
 * CommandPalette — Cmd+K (Mac) / Ctrl+K (Win) command palette.
 *
 * TrainPlex Studio Phase 1 Step 14 — Global Search.
 *
 * What it renders
 * ---------------
 * - Soft-dark overlay (portaled to document.body) so the palette sits on
 *   top of every other surface, including modals.
 * - Centered panel with a single search input + a grouped results list.
 * - Result types are bucketed by `type` (Trainers / Projects /
 *   Submissions / Audit / Tasks) with a sticky group heading.
 * - Below results: a Recent Searches section (when input is empty and
 *   the hook has localStorage entries).
 * - Quick actions row when input is empty — e.g. "Create new project"
 *   navigates to the wizard.
 *
 * Keyboard
 * --------
 * - Cmd+K / Ctrl+K toggles open/close (binding handled by `useCommandPalette`).
 * - Esc closes.
 * - ArrowUp / ArrowDown moves the active row, wrapping at the ends.
 * - Enter activates the active row (navigates to its `url`).
 * - Clicking the overlay (but NOT the panel) closes.
 *
 * Data flow
 * ---------
 * - `searchFn(q, scope)` is injected so the consumer wires it to the
 *   real backend (`GET /api/v1/admin/search`). The component never
 *   imports fetch directly — keeps the UI library framework-agnostic.
 * - Search is debounced 300ms client-side so each keystroke doesn't fire
 *   a fresh API call. The debounce id is cleared on unmount.
 * - `navigate(url)` is injected so the palette can use the host app's
 *   router. Defaults to `window.location.assign` for standalone usage.
 *
 * What this component does NOT do
 * -------------------------------
 * - No real fetch / axios — the consumer wires `searchFn`.
 * - No role check — the consumer wraps `<CommandPalette />` in a
 *   `<RoleGate allow={['admin']} />` (this component happily renders for
 *   any user; gating is the host's concern).
 * - No analytics — same reason; the host can log on `onResultClick`.
 */

import {
  type FormEvent,
  type ReactNode,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { createPortal } from "react-dom";
import styles from "./CommandPalette.module.css";
import {
  RECENT_MAX,
  type UseCommandPaletteResult,
  useCommandPalette,
} from "./useCommandPalette";

/**
 * Result type matches the backend contract from
 * ``core.views_search.AdminGlobalSearchAPI``. Keep in sync — the union of
 * `type` strings must match the backend's hard-coded list.
 */
export type CommandPaletteResultType =
  | "trainer"
  | "project"
  | "submission"
  | "audit"
  | "task";

export interface CommandPaletteResult {
  type: CommandPaletteResultType | string;
  id: number;
  title: string;
  subtitle: string;
  url: string;
}

export type CommandPaletteScope =
  | "all"
  | "trainers"
  | "projects"
  | "submissions"
  | "audit_logs"
  | "tasks";

export interface CommandPaletteQuickAction {
  /** Unique id for the row + key. */
  id: string;
  /** Title rendered in the row. */
  title: string;
  /** Optional subtitle / hint. */
  subtitle?: string;
  /** Callback fired on Enter / click. Receives the host's `navigate` fn. */
  onActivate: (navigate: (url: string) => void) => void;
}

/** i18n strings the host injects so the lib stays locale-agnostic. */
export interface CommandPaletteLabels {
  placeholder: string;
  recent: string;
  quickActions: string;
  noResults: string;
  groupTrainers: string;
  groupProjects: string;
  groupSubmissions: string;
  groupAudit: string;
  groupTasks: string;
  shortcutHint: string;
}

export const DEFAULT_LABELS: CommandPaletteLabels = {
  placeholder: "Search trainers, projects, submissions...",
  recent: "Recent searches",
  quickActions: "Quick actions",
  noResults: "No results found",
  groupTrainers: "Trainers",
  groupProjects: "Projects",
  groupSubmissions: "Submissions",
  groupAudit: "Audit Logs",
  groupTasks: "Tasks",
  shortcutHint: "Press Cmd+K to search anywhere",
};

export interface CommandPaletteProps {
  /** State + recent-history hook output. If omitted, the component
   *  spins up its own instance internally. */
  controller?: UseCommandPaletteResult;
  /** Fetches search results. Receives `(q, scope)`, returns the rows. */
  searchFn: (q: string, scope: CommandPaletteScope) => Promise<CommandPaletteResult[]>;
  /** Host-router navigation. Defaults to `window.location.assign`. */
  navigate?: (url: string) => void;
  /** i18n labels — defaults render English strings. */
  labels?: Partial<CommandPaletteLabels>;
  /** Optional quick-action rows shown when input is empty. */
  quickActions?: CommandPaletteQuickAction[];
  /** Optional test-id override. */
  testId?: string;
  /** Debounce time in ms for the search call. Defaults to 300. */
  debounceMs?: number;
}

const GROUP_ORDER: CommandPaletteResultType[] = [
  "trainer",
  "project",
  "submission",
  "audit",
  "task",
];

function groupLabel(type: CommandPaletteResultType, labels: CommandPaletteLabels): string {
  switch (type) {
    case "trainer":
      return labels.groupTrainers;
    case "project":
      return labels.groupProjects;
    case "submission":
      return labels.groupSubmissions;
    case "audit":
      return labels.groupAudit;
    case "task":
      return labels.groupTasks;
    default:
      return type;
  }
}

export function CommandPalette({
  controller,
  searchFn,
  navigate,
  labels: labelsProp,
  quickActions,
  testId = "command-palette",
  debounceMs = 300,
}: CommandPaletteProps) {
  // Resolve labels (caller can override any subset).
  const labels = useMemo<CommandPaletteLabels>(
    () => ({ ...DEFAULT_LABELS, ...(labelsProp ?? {}) }),
    [labelsProp],
  );

  // Default navigate falls back to a hard navigation. Hosts using React
  // Router pass their `history.push` here.
  const navigateImpl = useCallback(
    (url: string) => {
      if (navigate) return navigate(url);
      window.location.assign(url);
    },
    [navigate],
  );

  // If the caller didn't supply a controller we own one — needed so the
  // component is usable standalone in tests.
  // NOTE: React hook rules — both branches always create a hook below;
  // we run the hook unconditionally and use `controller ?? hookResult`.
  const hookResult = useCommandPalette(controller === undefined);
  const ctl = controller ?? hookResult;

  const { isOpen, close, recent, pushRecent } = ctl;

  // ---- internal state ----
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<CommandPaletteResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [activeIndex, setActiveIndex] = useState(0);

  const inputRef = useRef<HTMLInputElement | null>(null);
  const debounceRef = useRef<number | null>(null);
  // Token gates stale responses — only the latest call wins.
  const requestTokenRef = useRef(0);

  // Reset everything when the palette closes so the next open is clean.
  useEffect(() => {
    if (!isOpen) {
      setQuery("");
      setResults([]);
      setLoading(false);
      setActiveIndex(0);
      if (debounceRef.current != null) {
        window.clearTimeout(debounceRef.current);
        debounceRef.current = null;
      }
    }
  }, [isOpen]);

  // Focus input on open. Defer to next tick so the portal is mounted.
  useEffect(() => {
    if (isOpen) {
      const id = window.setTimeout(() => inputRef.current?.focus(), 0);
      return () => window.clearTimeout(id);
    }
    return undefined;
  }, [isOpen]);

  // Debounced search.
  useEffect(() => {
    if (!isOpen) return;
    const q = query.trim();
    if (debounceRef.current != null) {
      window.clearTimeout(debounceRef.current);
      debounceRef.current = null;
    }
    if (!q) {
      setResults([]);
      setLoading(false);
      return;
    }

    setLoading(true);
    const token = ++requestTokenRef.current;
    debounceRef.current = window.setTimeout(async () => {
      try {
        const rows = await searchFn(q, "all");
        // Drop stale responses — only the latest token wins.
        if (token !== requestTokenRef.current) return;
        setResults(rows);
      } catch {
        if (token !== requestTokenRef.current) return;
        setResults([]);
      } finally {
        if (token === requestTokenRef.current) setLoading(false);
      }
    }, debounceMs);

    return () => {
      if (debounceRef.current != null) {
        window.clearTimeout(debounceRef.current);
        debounceRef.current = null;
      }
    };
  }, [query, isOpen, debounceMs, searchFn]);

  // Group results by type — keep stable order so keyboard nav is predictable.
  const groupedResults = useMemo(() => {
    const buckets: Record<string, CommandPaletteResult[]> = {};
    for (const r of results) {
      const key = r.type;
      if (!buckets[key]) buckets[key] = [];
      buckets[key].push(r);
    }
    // Materialise in `GROUP_ORDER`, dropping empty buckets.
    return GROUP_ORDER.flatMap((t) =>
      buckets[t] && buckets[t].length > 0
        ? [{ type: t, rows: buckets[t] }]
        : [],
    );
  }, [results]);

  // Flat list of activatable rows in the same visual order — Enter on
  // `activeIndex` activates this row.
  const flatRows = useMemo<CommandPaletteResult[]>(
    () => groupedResults.flatMap((g) => g.rows),
    [groupedResults],
  );

  // Reset active index when results change so we don't point past the
  // end of a freshly-shrunk list.
  useEffect(() => {
    setActiveIndex(0);
  }, [flatRows]);

  const activateResult = useCallback(
    (row: CommandPaletteResult) => {
      pushRecent(query.trim());
      close();
      navigateImpl(row.url);
    },
    [close, navigateImpl, pushRecent, query],
  );

  const onKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLDivElement>) => {
      if (e.key === "Escape") {
        e.preventDefault();
        close();
        return;
      }
      // Cmd+K / Ctrl+K inside the open palette = close.
      if ((e.metaKey || e.ctrlKey) && (e.key === "k" || e.key === "K")) {
        e.preventDefault();
        close();
        return;
      }
      if (flatRows.length === 0) return;

      if (e.key === "ArrowDown") {
        e.preventDefault();
        setActiveIndex((i) => (i + 1) % flatRows.length);
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        setActiveIndex((i) => (i - 1 + flatRows.length) % flatRows.length);
      } else if (e.key === "Enter") {
        e.preventDefault();
        const row = flatRows[activeIndex];
        if (row) activateResult(row);
      }
    },
    [activateResult, activeIndex, close, flatRows],
  );

  const onSubmit = useCallback(
    (e: FormEvent) => {
      e.preventDefault();
      const row = flatRows[activeIndex];
      if (row) activateResult(row);
    },
    [activateResult, activeIndex, flatRows],
  );

  if (!isOpen) return null;
  if (typeof document === "undefined") return null;

  const showEmpty = !loading && query.trim().length > 0 && flatRows.length === 0;
  const showRecent = !query.trim() && recent.length > 0;
  const showQuickActions = !query.trim() && quickActions && quickActions.length > 0;

  // Cumulative offset tracker for the active-row outline rendering.
  let rowCursor = -1;

  const overlay: ReactNode = (
    <div
      className={styles.overlay}
      data-testid={testId}
      role="dialog"
      aria-modal="true"
      aria-label="Command palette"
      onMouseDown={(e) => {
        // Backdrop click closes — but ignore clicks that originate inside
        // the panel (which bubble up to the overlay).
        if (e.target === e.currentTarget) close();
      }}
      onKeyDown={onKeyDown}
    >
      <div className={styles.panel} data-testid={`${testId}-panel`}>
        <form className={styles.searchRow} onSubmit={onSubmit} role="search">
          <span aria-hidden="true" className={styles.searchIcon}>
            {/* Inline SVG so we don't pull a heavy icon lib for a single glyph. */}
            <svg
              width="18"
              height="18"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <circle cx="11" cy="11" r="7" />
              <line x1="21" y1="21" x2="16.65" y2="16.65" />
            </svg>
          </span>
          <input
            ref={inputRef}
            className={styles.searchInput}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder={labels.placeholder}
            type="text"
            autoComplete="off"
            spellCheck={false}
            data-testid={`${testId}-input`}
            aria-label={labels.placeholder}
          />
          <span className={styles.shortcutHint} aria-hidden="true">
            esc
          </span>
        </form>

        <div className={styles.results} data-testid={`${testId}-results`}>
          {showEmpty && (
            <div className={styles.empty} data-testid={`${testId}-empty`}>
              {labels.noResults}
            </div>
          )}

          {flatRows.length > 0 &&
            groupedResults.map((group) => (
              <div
                key={group.type}
                data-testid={`${testId}-group-${group.type}`}
              >
                <div className={styles.groupHeading}>
                  {groupLabel(group.type as CommandPaletteResultType, labels)}
                </div>
                {group.rows.map((row) => {
                  rowCursor += 1;
                  const isActive = rowCursor === activeIndex;
                  return (
                    <button
                      key={`${row.type}-${row.id}`}
                      type="button"
                      className={`${styles.row} ${isActive ? styles.rowActive : ""}`}
                      data-testid={`${testId}-row-${row.type}-${row.id}`}
                      data-active={isActive ? "true" : "false"}
                      onMouseEnter={() => setActiveIndex(rowCursor)}
                      onClick={() => activateResult(row)}
                    >
                      <span className={styles.typeBadge}>{row.type}</span>
                      <span className={styles.rowTextWrap}>
                        <span className={styles.rowTitle}>{row.title}</span>
                        <span className={styles.rowSubtitle}>{row.subtitle}</span>
                      </span>
                    </button>
                  );
                })}
              </div>
            ))}

          {showRecent && (
            <div data-testid={`${testId}-recent`}>
              <div className={styles.groupHeading}>{labels.recent}</div>
              {recent.slice(0, RECENT_MAX).map((term) => (
                <button
                  key={term}
                  type="button"
                  className={styles.recentRow}
                  onClick={() => {
                    setQuery(term);
                    inputRef.current?.focus();
                  }}
                  data-testid={`${testId}-recent-${term}`}
                >
                  <span aria-hidden="true" className={styles.recentIcon}>
                    {/* clock icon */}
                    <svg
                      width="14"
                      height="14"
                      viewBox="0 0 24 24"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="2"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    >
                      <circle cx="12" cy="12" r="10" />
                      <polyline points="12 6 12 12 16 14" />
                    </svg>
                  </span>
                  <span>{term}</span>
                </button>
              ))}
            </div>
          )}

          {showQuickActions && (
            <div data-testid={`${testId}-quick-actions`}>
              <div className={styles.groupHeading}>{labels.quickActions}</div>
              {quickActions!.map((qa) => (
                <button
                  key={qa.id}
                  type="button"
                  className={styles.recentRow}
                  onClick={() => {
                    close();
                    qa.onActivate(navigateImpl);
                  }}
                  data-testid={`${testId}-quick-action-${qa.id}`}
                >
                  <span aria-hidden="true" className={styles.recentIcon}>
                    {/* plus icon */}
                    <svg
                      width="14"
                      height="14"
                      viewBox="0 0 24 24"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="2"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    >
                      <line x1="12" y1="5" x2="12" y2="19" />
                      <line x1="5" y1="12" x2="19" y2="12" />
                    </svg>
                  </span>
                  <span>
                    {qa.title}
                    {qa.subtitle ? (
                      <span className={styles.rowSubtitle}>
                        {" "}
                        — {qa.subtitle}
                      </span>
                    ) : null}
                  </span>
                </button>
              ))}
            </div>
          )}
        </div>

        <div className={styles.footer} data-testid={`${testId}-footer`}>
          <span>{labels.shortcutHint}</span>
          <div className={styles.footerHints}>
            <span>
              <span className={styles.shortcutHint}>↑↓</span> navigate
            </span>
            <span>
              <span className={styles.shortcutHint}>↵</span> open
            </span>
            <span>
              <span className={styles.shortcutHint}>esc</span> close
            </span>
          </div>
        </div>
      </div>
    </div>
  );

  return createPortal(overlay, document.body);
}

export default CommandPalette;
