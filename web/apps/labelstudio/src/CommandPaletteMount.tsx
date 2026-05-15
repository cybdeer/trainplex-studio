/**
 * CommandPaletteMount — wires the TrainPlex Cmd+K command palette into the
 * labelstudio React app.
 *
 * TrainPlex Studio Phase 1 Step 14 — Global Search.
 *
 * Mount strategy
 * --------------
 * Mounted at the **root** of the document in `main.tsx` as a SEPARATE
 * React tree. We can't reach into the existing `<App />` tree from here
 * because:
 *   - main.tsx is the synchronous entry that imports `./app/App` (which
 *     itself triggers `render(<App />, root)`).
 *   - App.jsx is wrapped in a `<Router>` + a tower of context providers,
 *     and we want the palette overlay to render OUTSIDE that tree so a
 *     navigation can't unmount it mid-flight.
 *
 * Putting the palette in a parallel React root that lives in `document.body`
 * sidesteps all of that. Cross-tree communication is only one-way:
 *   - palette pushes navigations via `window.LSH.push(url)` (history is
 *     attached to `window.LSH` in App.jsx).
 *   - palette reads the current user via `APP_SETTINGS.user` (the global
 *     bootstrapped by the Django template).
 *
 * Role gating
 * -----------
 * The palette is admin-only. We render through `<RoleGate allow={['admin']} />`
 * so even if a non-admin somehow opens it (DOM trickery), the children
 * (the actual CommandPalette + the global keyboard listener inside
 * `useCommandPalette`) never mount.
 *
 * What this DOES NOT do
 * ---------------------
 * - No analytics ping (host adds in Phase 2).
 * - No "create project" wizard auto-open (Phase 2 — the quick action
 *   navigates to `/projects/wizard` and the wizard page picks up from
 *   there).
 */

import { CommandPalette, RoleGate, useCommandPalette } from "@humansignal/ui";
import type {
  CommandPaletteLabels,
  CommandPaletteResult,
  CommandPaletteScope,
} from "@humansignal/ui";
import { useMemo } from "react";
import { useTranslation } from "react-i18next";

/** Pull the current user role out of `APP_SETTINGS` (bootstrapped by Django). */
function currentUserRole(): string | null {
  // The labelstudio template injects `window.APP_SETTINGS = {...}`.
  // `user.role` is set by the TrainPlex login response.
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const appSettings: any =
    typeof window !== "undefined" ? (window as any).APP_SETTINGS : null;
  return appSettings?.user?.role ?? null;
}

/** Push a route via the app's history (set up in App.jsx as `window.LSH`). */
function navigateViaAppHistory(url: string) {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const LSH: any =
    typeof window !== "undefined" ? (window as any).LSH : null;
  if (LSH && typeof LSH.push === "function") {
    LSH.push(url);
  } else {
    // Fallback for the rare case where the palette mounts before App.jsx.
    window.location.assign(url);
  }
}

/** Fetch results from the backend `/api/v1/admin/search` endpoint. */
async function searchFn(
  q: string,
  scope: CommandPaletteScope,
): Promise<CommandPaletteResult[]> {
  const url = `/api/v1/admin/search?q=${encodeURIComponent(q)}&scope=${encodeURIComponent(scope)}`;
  try {
    const resp = await fetch(url, {
      credentials: "include",
      headers: { Accept: "application/json" },
    });
    if (!resp.ok) return [];
    const body = await resp.json();
    return Array.isArray(body) ? body : [];
  } catch {
    // Network blip — empty results, palette UI shows the empty state.
    return [];
  }
}

export function CommandPaletteMount() {
  const role = currentUserRole();
  const { t } = useTranslation();

  // Hook owns open-state + recent searches + Cmd+K binding.
  // We pass it explicitly so the binding only enables for admins
  // (passing `false` to the hook disables `document.addEventListener`).
  const ctl = useCommandPalette(role === "admin");

  // i18n-driven labels — passes locale strings into the lib component
  // so the lib stays locale-agnostic.
  const labels = useMemo<Partial<CommandPaletteLabels>>(
    () => ({
      placeholder: t("cmdk.placeholder"),
      recent: t("cmdk.recent"),
      quickActions: t("cmdk.quick_actions"),
      noResults: t("cmdk.no_results"),
      groupTrainers: t("cmdk.group_trainers"),
      groupProjects: t("cmdk.group_projects"),
      groupSubmissions: t("cmdk.group_submissions"),
      groupAudit: t("cmdk.group_audit"),
      groupTasks: t("cmdk.group_tasks"),
      shortcutHint: t("cmdk.shortcut_hint"),
    }),
    [t],
  );

  const quickActions = useMemo(
    () => [
      {
        id: "new-project",
        title: t("admin.dashboard.new_project"),
        subtitle: t("admin.wizard.title"),
        onActivate: (nav: (url: string) => void) => nav("/projects/wizard"),
      },
    ],
    [t],
  );

  return (
    <RoleGate allow={["admin"]} userRole={role}>
      <CommandPalette
        controller={ctl}
        searchFn={searchFn}
        navigate={navigateViaAppHistory}
        labels={labels}
        quickActions={quickActions}
      />
    </RoleGate>
  );
}

export default CommandPaletteMount;
