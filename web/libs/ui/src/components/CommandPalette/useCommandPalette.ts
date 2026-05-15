/**
 * useCommandPalette — React hook that owns the Cmd+K palette's open state,
 * recent-search history, and global keyboard binding.
 *
 * TrainPlex Studio Phase 1 Step 14 (Global Search).
 *
 * Why a hook (not Context)
 * ------------------------
 * The palette is admin-only and mounted exactly once at the root in
 * `main.tsx` under a `<RoleGate allow={['admin']} />`. A single instance
 * means we don't need a provider — the hook hosts state inline and the
 * `<CommandPalette />` component reads it directly.
 *
 * Recent searches
 * ---------------
 * Persisted to `localStorage` under `tp_cmdk_recent` — capped at 10 entries
 * so the dropdown never grows unbounded. New entries deduplicate the list
 * (most-recent first). All writes are wrapped in a try/catch because the
 * trainer-facing surface can run in private-browsing where storage throws.
 *
 * Keyboard binding
 * ----------------
 * - Mac:    Cmd+K  (event.metaKey)
 * - Win/Lx: Ctrl+K (event.ctrlKey)
 * - The handler short-circuits when the active element is a `<textarea>`
 *   so Cmd+K inside a comment box (rare) is still respected as a textarea
 *   shortcut. We intentionally DO override `<input>` because there's no
 *   common Cmd+K binding inside form inputs — and users expect Cmd+K to
 *   open the palette from anywhere.
 */

import { useCallback, useEffect, useRef, useState } from "react";

export const RECENT_STORAGE_KEY = "tp_cmdk_recent";
export const RECENT_MAX = 10;

/** Read recent searches from localStorage. Returns `[]` on any error. */
export function readRecent(): string[] {
  try {
    const raw = window.localStorage.getItem(RECENT_STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    // Sanity-filter so a malformed entry can't crash the render.
    return parsed.filter((x): x is string => typeof x === "string" && x.length > 0).slice(0, RECENT_MAX);
  } catch {
    return [];
  }
}

/** Persist recent searches to localStorage. Silently no-ops on error. */
export function writeRecent(items: string[]): void {
  try {
    window.localStorage.setItem(
      RECENT_STORAGE_KEY,
      JSON.stringify(items.slice(0, RECENT_MAX)),
    );
  } catch {
    /* private browsing — best-effort only */
  }
}

export interface UseCommandPaletteResult {
  /** Whether the palette is currently open. */
  isOpen: boolean;
  /** Open the palette. */
  open: () => void;
  /** Close the palette. */
  close: () => void;
  /** Toggle the palette. */
  toggle: () => void;
  /** Recent search history (most-recent first, cap 10). */
  recent: string[];
  /** Push a new search term to the recent list, dedup + cap. */
  pushRecent: (term: string) => void;
  /** Wipe the recent list. */
  clearRecent: () => void;
}

/**
 * Hook that wires the global Cmd+K / Ctrl+K listener and exposes the
 * palette's open/recent state.
 *
 * @param enabled — gate the keyboard listener. Pass `false` when the
 *                  current user is NOT admin so non-admins can't pop the
 *                  palette via DOM trickery. Defaults to `true`.
 */
export function useCommandPalette(enabled = true): UseCommandPaletteResult {
  const [isOpen, setIsOpen] = useState(false);
  const [recent, setRecent] = useState<string[]>(() => readRecent());

  // Refs so the keydown handler is stable across renders without
  // re-binding the document listener every time.
  const isOpenRef = useRef(isOpen);
  isOpenRef.current = isOpen;

  const open = useCallback(() => setIsOpen(true), []);
  const close = useCallback(() => setIsOpen(false), []);
  const toggle = useCallback(() => setIsOpen((v) => !v), []);

  const pushRecent = useCallback((term: string) => {
    const cleaned = term.trim();
    if (!cleaned) return;
    setRecent((prev) => {
      // dedupe (case-insensitive) + cap at RECENT_MAX
      const without = prev.filter((x) => x.toLowerCase() !== cleaned.toLowerCase());
      const next = [cleaned, ...without].slice(0, RECENT_MAX);
      writeRecent(next);
      return next;
    });
  }, []);

  const clearRecent = useCallback(() => {
    setRecent([]);
    writeRecent([]);
  }, []);

  useEffect(() => {
    if (!enabled) return;

    function onKeyDown(e: KeyboardEvent) {
      // Cmd+K (Mac) / Ctrl+K (Win/Lx). Both modifiers checked so the same
      // binding works on either platform without OS sniffing.
      const isCmdOrCtrlK =
        (e.metaKey || e.ctrlKey) && (e.key === "k" || e.key === "K");
      if (!isCmdOrCtrlK) {
        // Esc closes whether or not we own the open state.
        if (e.key === "Escape" && isOpenRef.current) {
          e.preventDefault();
          setIsOpen(false);
        }
        return;
      }

      // Don't hijack Cmd+K inside textarea so a long-form comment can use
      // it for, e.g., link-insert shortcuts wired in some editors.
      const target = e.target as HTMLElement | null;
      if (target?.tagName === "TEXTAREA") {
        return;
      }

      e.preventDefault();
      setIsOpen((v) => !v);
    }

    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [enabled]);

  return {
    isOpen,
    open,
    close,
    toggle,
    recent,
    pushRecent,
    clearRecent,
  };
}

export default useCommandPalette;
