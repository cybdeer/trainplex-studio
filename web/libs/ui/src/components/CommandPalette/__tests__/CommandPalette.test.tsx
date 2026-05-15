/**
 * CommandPalette unit tests — TrainPlex Phase 1 Step 14.
 *
 * Covers the Cmd+K command palette React component and the
 * `useCommandPalette` hook that owns its state + keyboard binding.
 *
 * Test surface
 * ------------
 * - Cmd+K opens the palette.
 * - Esc closes the palette.
 * - The search input gets focus on open.
 * - Debounced search call fires after the configured timeout.
 * - Results render grouped by type with stable group order.
 * - ArrowDown / ArrowUp move the active index, with wraparound.
 * - Enter activates the active row and calls `navigate`.
 * - Backdrop click closes the palette.
 * - Empty state renders when the search returns 0 rows.
 * - Recent searches render when input is empty + there are recent entries.
 * - Quick actions render when input is empty.
 * - Clicking a row fires `navigate` and pushes onto recent searches.
 */

import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import "@testing-library/jest-dom";
import { CommandPalette } from "../CommandPalette";
import {
  RECENT_STORAGE_KEY,
  readRecent,
  useCommandPalette,
  writeRecent,
} from "../useCommandPalette";

// Lightweight fake searchFn: synchronous-resolving promise with predictable rows.
function fakeSearchFn(byTerm: Record<string, Parameters<typeof CommandPalette>[0]["searchFn"] extends infer T ? T extends (...args: any[]) => Promise<infer R> ? R : never : never>) {
  return jest.fn(async (q: string) => {
    const key = q.trim().toLowerCase();
    return byTerm[key] ?? [];
  });
}

const SEED_RESULTS = {
  hindi: [
    {
      type: "trainer" as const,
      id: 5,
      title: "Geeta Parihar",
      subtitle: "Rajasthan · Bronze · Hindi",
      url: "/admin/trainers/5",
    },
    {
      type: "project" as const,
      id: 12,
      title: "Hindi NER",
      subtitle: "Active · 487/500 tasks",
      url: "/admin/projects/12",
    },
    {
      type: "submission" as const,
      id: 1023,
      title: "Submission #1023",
      subtitle: "Geeta · 2h ago",
      url: "/admin/submissions/1023",
    },
  ],
  empty: [],
};

beforeEach(() => {
  window.localStorage.clear();
  jest.useFakeTimers();
});

afterEach(() => {
  // Drain any pending debounce / focus timers.
  act(() => {
    jest.runOnlyPendingTimers();
  });
  jest.useRealTimers();
});

/** Helper — render the palette with a fresh hook instance (auto-controller). */
function renderPalette(extra: Partial<Parameters<typeof CommandPalette>[0]> = {}) {
  const search = fakeSearchFn(SEED_RESULTS as any);
  const navigate = jest.fn();
  const utils = render(
    <CommandPalette
      searchFn={search as any}
      navigate={navigate}
      debounceMs={300}
      {...extra}
    />,
  );
  return { ...utils, search, navigate };
}

describe("CommandPalette", () => {
  it("is hidden by default (no overlay rendered)", () => {
    renderPalette();
    expect(screen.queryByTestId("command-palette")).not.toBeInTheDocument();
  });

  it("opens on Cmd+K and renders the search input", () => {
    renderPalette();
    act(() => {
      fireEvent.keyDown(document, { key: "k", metaKey: true });
    });
    expect(screen.getByTestId("command-palette")).toBeInTheDocument();
    expect(screen.getByTestId("command-palette-input")).toBeInTheDocument();
  });

  it("opens on Ctrl+K (Windows / Linux)", () => {
    renderPalette();
    act(() => {
      fireEvent.keyDown(document, { key: "k", ctrlKey: true });
    });
    expect(screen.getByTestId("command-palette")).toBeInTheDocument();
  });

  it("closes on Escape", () => {
    renderPalette();
    act(() => {
      fireEvent.keyDown(document, { key: "k", metaKey: true });
    });
    expect(screen.getByTestId("command-palette")).toBeInTheDocument();

    act(() => {
      fireEvent.keyDown(document, { key: "Escape" });
    });
    expect(screen.queryByTestId("command-palette")).not.toBeInTheDocument();
  });

  it("closes on backdrop click", () => {
    renderPalette();
    act(() => {
      fireEvent.keyDown(document, { key: "k", metaKey: true });
    });
    const overlay = screen.getByTestId("command-palette");
    act(() => {
      fireEvent.mouseDown(overlay, { target: overlay });
    });
    expect(screen.queryByTestId("command-palette")).not.toBeInTheDocument();
  });

  it("focuses the search input on open", () => {
    renderPalette();
    act(() => {
      fireEvent.keyDown(document, { key: "k", metaKey: true });
      // Focus is deferred to setTimeout(..., 0) — flush the timer.
      jest.runOnlyPendingTimers();
    });
    expect(screen.getByTestId("command-palette-input")).toHaveFocus();
  });

  it("debounces the search call", async () => {
    const { search } = renderPalette();
    act(() => {
      fireEvent.keyDown(document, { key: "k", metaKey: true });
      jest.runOnlyPendingTimers();
    });
    const input = screen.getByTestId("command-palette-input") as HTMLInputElement;

    act(() => {
      fireEvent.change(input, { target: { value: "h" } });
      fireEvent.change(input, { target: { value: "hi" } });
      fireEvent.change(input, { target: { value: "hindi" } });
    });
    // Before debounce fires, no call yet.
    expect(search).not.toHaveBeenCalled();
    act(() => {
      jest.advanceTimersByTime(300);
    });
    await waitFor(() => expect(search).toHaveBeenCalledTimes(1));
    expect(search).toHaveBeenCalledWith("hindi", "all");
  });

  it("renders grouped results after a debounced search", async () => {
    renderPalette();
    act(() => {
      fireEvent.keyDown(document, { key: "k", metaKey: true });
      jest.runOnlyPendingTimers();
    });
    const input = screen.getByTestId("command-palette-input");
    act(() => {
      fireEvent.change(input, { target: { value: "hindi" } });
      jest.advanceTimersByTime(300);
    });
    await waitFor(() =>
      expect(screen.getByTestId("command-palette-group-trainer")).toBeInTheDocument(),
    );
    expect(screen.getByTestId("command-palette-group-project")).toBeInTheDocument();
    expect(screen.getByTestId("command-palette-group-submission")).toBeInTheDocument();
    expect(screen.getByTestId("command-palette-row-trainer-5")).toBeInTheDocument();
    expect(screen.getByTestId("command-palette-row-project-12")).toBeInTheDocument();
  });

  it("ArrowDown / ArrowUp move the active index with wraparound", async () => {
    renderPalette();
    act(() => {
      fireEvent.keyDown(document, { key: "k", metaKey: true });
      jest.runOnlyPendingTimers();
    });
    const input = screen.getByTestId("command-palette-input");
    act(() => {
      fireEvent.change(input, { target: { value: "hindi" } });
      jest.advanceTimersByTime(300);
    });
    await waitFor(() =>
      expect(screen.getByTestId("command-palette-row-trainer-5")).toBeInTheDocument(),
    );
    const overlay = screen.getByTestId("command-palette");

    // Initial active = index 0 (trainer 5).
    expect(screen.getByTestId("command-palette-row-trainer-5")).toHaveAttribute(
      "data-active",
      "true",
    );

    act(() => {
      fireEvent.keyDown(overlay, { key: "ArrowDown" });
    });
    expect(screen.getByTestId("command-palette-row-project-12")).toHaveAttribute(
      "data-active",
      "true",
    );

    // Wrap-around at end.
    act(() => {
      fireEvent.keyDown(overlay, { key: "ArrowDown" });
      fireEvent.keyDown(overlay, { key: "ArrowDown" });
    });
    // 3 rows total, ArrowDown × 3 from index 0 → index 0 (wrap).
    expect(screen.getByTestId("command-palette-row-trainer-5")).toHaveAttribute(
      "data-active",
      "true",
    );

    act(() => {
      fireEvent.keyDown(overlay, { key: "ArrowUp" });
    });
    // ArrowUp from 0 wraps to last (submission 1023).
    expect(screen.getByTestId("command-palette-row-submission-1023")).toHaveAttribute(
      "data-active",
      "true",
    );
  });

  it("Enter on active row navigates and closes", async () => {
    const { navigate } = renderPalette();
    act(() => {
      fireEvent.keyDown(document, { key: "k", metaKey: true });
      jest.runOnlyPendingTimers();
    });
    const input = screen.getByTestId("command-palette-input");
    act(() => {
      fireEvent.change(input, { target: { value: "hindi" } });
      jest.advanceTimersByTime(300);
    });
    await waitFor(() =>
      expect(screen.getByTestId("command-palette-row-trainer-5")).toBeInTheDocument(),
    );
    const overlay = screen.getByTestId("command-palette");
    act(() => {
      fireEvent.keyDown(overlay, { key: "Enter" });
    });
    expect(navigate).toHaveBeenCalledWith("/admin/trainers/5");
    expect(screen.queryByTestId("command-palette")).not.toBeInTheDocument();
  });

  it("clicking a row navigates and pushes onto recent searches", async () => {
    const { navigate } = renderPalette();
    act(() => {
      fireEvent.keyDown(document, { key: "k", metaKey: true });
      jest.runOnlyPendingTimers();
    });
    const input = screen.getByTestId("command-palette-input");
    act(() => {
      fireEvent.change(input, { target: { value: "hindi" } });
      jest.advanceTimersByTime(300);
    });
    await waitFor(() =>
      expect(screen.getByTestId("command-palette-row-project-12")).toBeInTheDocument(),
    );
    act(() => {
      fireEvent.click(screen.getByTestId("command-palette-row-project-12"));
    });
    expect(navigate).toHaveBeenCalledWith("/admin/projects/12");
    expect(readRecent()).toContain("hindi");
  });

  it("shows the empty state when search returns 0 rows", async () => {
    renderPalette();
    act(() => {
      fireEvent.keyDown(document, { key: "k", metaKey: true });
      jest.runOnlyPendingTimers();
    });
    act(() => {
      fireEvent.change(screen.getByTestId("command-palette-input"), {
        target: { value: "empty" },
      });
      jest.advanceTimersByTime(300);
    });
    await waitFor(() =>
      expect(screen.getByTestId("command-palette-empty")).toBeInTheDocument(),
    );
  });

  it("shows recent searches when input is empty", () => {
    // Seed localStorage before mount so the hook reads it.
    writeRecent(["aadhaar", "geeta"]);
    renderPalette();
    act(() => {
      fireEvent.keyDown(document, { key: "k", metaKey: true });
      jest.runOnlyPendingTimers();
    });
    expect(screen.getByTestId("command-palette-recent")).toBeInTheDocument();
    expect(screen.getByTestId("command-palette-recent-aadhaar")).toBeInTheDocument();
    expect(screen.getByTestId("command-palette-recent-geeta")).toBeInTheDocument();
  });

  it("renders quick actions when input is empty", () => {
    const onActivate = jest.fn();
    renderPalette({
      quickActions: [
        {
          id: "new-project",
          title: "Create new project",
          subtitle: "Open the project wizard",
          onActivate,
        },
      ],
    });
    act(() => {
      fireEvent.keyDown(document, { key: "k", metaKey: true });
      jest.runOnlyPendingTimers();
    });
    expect(screen.getByTestId("command-palette-quick-actions")).toBeInTheDocument();
    act(() => {
      fireEvent.click(screen.getByTestId("command-palette-quick-action-new-project"));
    });
    expect(onActivate).toHaveBeenCalledTimes(1);
  });

  it("honours custom i18n labels", () => {
    renderPalette({
      labels: {
        placeholder: "ट्रेनर खोजें...",
        noResults: "कोई परिणाम नहीं",
      },
    });
    act(() => {
      fireEvent.keyDown(document, { key: "k", metaKey: true });
      jest.runOnlyPendingTimers();
    });
    expect(screen.getByPlaceholderText("ट्रेनर खोजें...")).toBeInTheDocument();
  });
});

describe("useCommandPalette recent-list helpers", () => {
  beforeEach(() => {
    window.localStorage.clear();
    jest.useRealTimers();
  });

  it("readRecent returns [] when nothing stored", () => {
    expect(readRecent()).toEqual([]);
  });

  it("writeRecent + readRecent roundtrips", () => {
    writeRecent(["alpha", "beta"]);
    expect(readRecent()).toEqual(["alpha", "beta"]);
  });

  it("readRecent ignores malformed JSON", () => {
    window.localStorage.setItem(RECENT_STORAGE_KEY, "not json");
    expect(readRecent()).toEqual([]);
  });

  it("readRecent caps at RECENT_MAX entries", () => {
    const big = Array.from({ length: 50 }, (_, i) => `term${i}`);
    writeRecent(big);
    const out = readRecent();
    expect(out.length).toBeLessThanOrEqual(10);
  });

  it("hook pushRecent dedupes + caps", () => {
    // Bare-bones renderer via the hook indirectly through CommandPalette
    // is overkill — exercise the hook in isolation through a small harness.
    function Harness() {
      const ctl = useCommandPalette(false);
      return (
        <div>
          <button
            type="button"
            data-testid="push"
            onClick={() => ctl.pushRecent("term-a")}
          >
            push
          </button>
          <button
            type="button"
            data-testid="push-dupe"
            onClick={() => ctl.pushRecent("TERM-A")}
          >
            push-dupe
          </button>
          <button
            type="button"
            data-testid="clear"
            onClick={() => ctl.clearRecent()}
          >
            clear
          </button>
          <div data-testid="recent">{ctl.recent.join(",")}</div>
        </div>
      );
    }
    render(<Harness />);
    fireEvent.click(screen.getByTestId("push"));
    fireEvent.click(screen.getByTestId("push"));
    fireEvent.click(screen.getByTestId("push-dupe"));
    // Despite 3 clicks, dedup keeps the list size at 1.
    expect(screen.getByTestId("recent").textContent).toBe("TERM-A");
    fireEvent.click(screen.getByTestId("clear"));
    expect(screen.getByTestId("recent").textContent).toBe("");
  });
});
