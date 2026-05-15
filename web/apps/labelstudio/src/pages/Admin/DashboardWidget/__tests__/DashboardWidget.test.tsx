/**
 * Tests for the TrainPlex admin dashboard widget.
 * Phase 1 Step 4.2-1.
 *
 * Strategy
 * --------
 * The page wires together useAuth (AppStore), useAPI (LS ApiProvider) and
 * `useQuery` (React Query) — none of which we want to spin up for a unit
 * test. So we mock those modules at the module-graph level and render the
 * component with controlled inputs.
 *
 * Coverage (matches the task spec):
 * - 4 KPI tiles render given mock snapshot data
 * - Top trainers count matches the snapshot
 * - Hindi mode shows Devanagari labels
 * - Loading state renders the skeleton placeholder
 *
 * Plus one extra: non-admin sees the RoleGate fallback (defensive — task
 * spec explicitly says wrap with RoleGate).
 */

/* eslint-disable @typescript-eslint/no-var-requires */

import "@testing-library/jest-dom";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import React from "react";

// ---- Module mocks (must come before importing the SUT) ----

// API: the SUT calls `api.callApi('adminDashboardSnapshot')`. We don't care
// what it returns in unit tests — `useQuery` is mocked below.
jest.mock("../../../../providers/ApiProvider", () => ({
  useAPI: () => ({ callApi: jest.fn() }),
  ApiContext: { Provider: ({ children }: any) => children },
}));

// Auth: we toggle the role per test via `setMockRole`. Default = admin.
let mockUserRole: string | null = "admin";
const setMockRole = (role: string | null) => {
  mockUserRole = role;
};
jest.mock("@humansignal/core/providers/AuthProvider", () => ({
  useAuth: () => ({ user: { role: mockUserRole } }),
}));

// React Query: deterministic per-test control of loading / success / error.
let mockQueryState: any = { data: undefined, isFetching: true, isError: false };
const setMockQuery = (state: any) => {
  mockQueryState = state;
};
jest.mock("@tanstack/react-query", () => ({
  useQuery: () => mockQueryState,
}));

// i18n: lightweight stub. `t(key)` returns the key by default. Tests that
// need a specific language (e.g. Hindi) override the lookup table.
let mockLang = "en";
let mockTranslations: Record<string, string> = {};
const setMockLang = (lang: string) => {
  mockLang = lang;
};
const setMockTranslations = (table: Record<string, string>) => {
  mockTranslations = table;
};
jest.mock("@humansignal/app-common", () => ({
  useTranslation: () => ({
    t: (key: string) => mockTranslations[key] ?? key,
    i18n: { language: mockLang },
  }),
}));

// ---- Now import the SUT ----

import { DashboardWidget } from "../DashboardWidget";
import type { DashboardSnapshot } from "../types";

const SNAPSHOT: DashboardSnapshot = {
  as_of: "2026-05-15T12:34:56Z",
  today: {
    submissions_count: 142,
    submissions_delta_pct: 12,
    active_trainers: 47,
    pay_hold_total_inr: 4200,
    pay_released_today_inr: 18500,
  },
  top_trainers: [
    { id: 5, name: "Geeta P.", state: "Rajasthan", tasks_today: 87, earnings_today_inr: 4350 },
    { id: 7, name: "Sunil M.", state: "UP", tasks_today: 82, earnings_today_inr: 4100 },
    { id: 12, name: "Anil K.", state: "Bihar", tasks_today: 78, earnings_today_inr: 3900 },
    { id: 19, name: "Rekha S.", state: "MP", tasks_today: 71, earnings_today_inr: 3550 },
    { id: 23, name: "Vikas T.", state: "Haryana", tasks_today: 68, earnings_today_inr: 3400 },
  ],
  alerts: { disputes_pending: 2, quality_flags: 1, stuck_payouts: 0 },
};

const renderDashboard = () =>
  render(
    <MemoryRouter>
      <DashboardWidget />
    </MemoryRouter>,
  );

beforeEach(() => {
  // Reset all module-level test state between tests.
  setMockRole("admin");
  setMockLang("en");
  setMockTranslations({});
  setMockQuery({ data: SNAPSHOT, isFetching: false, isError: false });
});

describe("DashboardWidget", () => {
  it("renders 4 KPI tiles given the mock snapshot", () => {
    renderDashboard();
    expect(screen.getByTestId("kpi-row")).toBeInTheDocument();
    expect(screen.getByTestId("kpi-submissions")).toBeInTheDocument();
    expect(screen.getByTestId("kpi-active-trainers")).toBeInTheDocument();
    expect(screen.getByTestId("kpi-pay-hold")).toBeInTheDocument();
    expect(screen.getByTestId("kpi-alerts")).toBeInTheDocument();

    // The submissions count appears in the rendered tile value (locale-formatted
    // — Intl.NumberFormat with en-IN returns "142" for three-digit numbers).
    expect(screen.getByTestId("kpi-submissions-value")).toHaveTextContent("142");
    // Active trainers = 47.
    expect(screen.getByTestId("kpi-active-trainers-value")).toHaveTextContent("47");
    // Alerts total = 2 + 1 + 0 = 3.
    expect(screen.getByTestId("kpi-alerts-value")).toHaveTextContent("3");
  });

  it("renders one row per trainer in the top-trainers table (5 rows)", () => {
    renderDashboard();
    const table = screen.getByTestId("top-trainers-table");
    expect(table).toBeInTheDocument();
    // Snapshot has 5 trainers (Geeta, Sunil, Anil, Rekha, Vikas) — one <tr>
    // per trainer, each carrying a stable trainer-row-{id} test id.
    SNAPSHOT.top_trainers.forEach((tr) => {
      expect(screen.getByTestId(`trainer-row-${tr.id}`)).toBeInTheDocument();
    });
    expect(screen.getAllByText(/Geeta P\.|Sunil M\.|Anil K\.|Rekha S\.|Vikas T\./)).toHaveLength(5);
  });

  it("renders the skeleton placeholder while fetching with no data", () => {
    setMockQuery({ data: undefined, isFetching: true, isError: false });
    renderDashboard();
    expect(screen.getByTestId("dashboard-skeleton")).toBeInTheDocument();
    // The KPI row should not be in the DOM during the loading state.
    expect(screen.queryByTestId("kpi-row")).not.toBeInTheDocument();
  });

  it("shows Devanagari labels when the language is Hindi", () => {
    setMockLang("hi");
    setMockTranslations({
      "admin.dashboard.today_snapshot": "आज का स्नैपशॉट",
      "admin.dashboard.submissions": "जमा कार्य",
      "admin.dashboard.active_trainers": "सक्रिय ट्रेनर",
      "admin.dashboard.pay_hold": "रोका हुआ payment",
      "admin.dashboard.alerts": "अलर्ट",
      "admin.dashboard.top_trainers": "टॉप 5 ट्रेनर (राज्य-वार)",
      "admin.dashboard.quick_actions": "त्वरित कार्य",
      "admin.dashboard.new_project": "नया प्रोजेक्ट",
      "admin.dashboard.wa_broadcast": "WA ब्रॉडकास्ट",
      "admin.dashboard.bulk_assign": "बल्क असाइन",
      "admin.dashboard.trainer_name": "ट्रेनर",
      "admin.dashboard.state": "राज्य",
      "admin.dashboard.tasks_today": "आज के कार्य",
      "admin.dashboard.earnings_today": "आज की कमाई",
      "admin.dashboard.disputes_pending": "विवाद लंबित",
      "admin.dashboard.quality_flags": "गुणवत्ता फ्लैग",
      "admin.dashboard.stuck_payouts": "अटके payouts",
    });
    renderDashboard();
    expect(screen.getByText("आज का स्नैपशॉट")).toBeInTheDocument();
    expect(screen.getByText("टॉप 5 ट्रेनर (राज्य-वार)")).toBeInTheDocument();
    expect(screen.getByText("नया प्रोजेक्ट")).toBeInTheDocument();
    // Devanagari unicode block sanity — Hindi text must contain ≥1 codepoint
    // in U+0900..U+097F (so we know the locale switched).
    const header = screen.getByText("आज का स्नैपशॉट").textContent ?? "";
    expect(/[ऀ-ॿ]/.test(header)).toBe(true);
  });

  it("hides the dashboard behind a 403 fallback when the user is not admin", () => {
    setMockRole("trainer");
    renderDashboard();
    expect(screen.getByTestId("dashboard-forbidden")).toBeInTheDocument();
    expect(screen.queryByTestId("kpi-row")).not.toBeInTheDocument();
  });

  it("renders an error box when the snapshot query fails", () => {
    setMockQuery({ data: undefined, isFetching: false, isError: true });
    setMockTranslations({
      "admin.dashboard.snapshot_failed": "Couldn't load dashboard snapshot.",
    });
    renderDashboard();
    expect(screen.getByTestId("dashboard-error")).toBeInTheDocument();
    expect(screen.getByTestId("dashboard-error")).toHaveTextContent(
      "Couldn't load dashboard snapshot.",
    );
  });
});

describe("DashboardWidget page metadata", () => {
  it("exposes /admin/dashboard as the route path", () => {
    expect((DashboardWidget as any).path).toBe("/admin/dashboard");
    expect((DashboardWidget as any).exact).toBe(true);
  });
});
