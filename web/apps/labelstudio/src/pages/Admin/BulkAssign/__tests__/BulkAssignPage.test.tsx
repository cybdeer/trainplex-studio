/**
 * Tests for the TrainPlex Admin Bulk Task Assign page.
 * Phase 1 Step 4.2-3.
 *
 * Mocks providers (Auth, API, React Query, i18n) at the module-graph level
 * + renders with controlled snapshot data — same strategy as the WA
 * Broadcast / Project Wizard tests.
 */

/* eslint-disable @typescript-eslint/no-var-requires */

import "@testing-library/jest-dom";
import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

// ---- Module mocks ----

jest.mock("../../../../providers/ApiProvider", () => ({
  useAPI: () => ({ callApi: jest.fn() }),
  ApiContext: { Provider: ({ children }: any) => children },
}));

let mockUserRole: string | null = "admin";
const setMockRole = (role: string | null) => {
  mockUserRole = role;
};
jest.mock("@humansignal/core/providers/AuthProvider", () => ({
  useAuth: () => ({ user: { role: mockUserRole } }),
}));

let mockQueryState: any = { data: undefined, isLoading: true, isError: false };
const setMockQuery = (state: any) => {
  mockQueryState = state;
};
let mockMutation: any = { isPending: false, mutate: jest.fn() };
const setMockMutation = (state: any) => {
  mockMutation = state;
};
jest.mock("@tanstack/react-query", () => ({
  useQuery: () => mockQueryState,
  useMutation: ({ onSuccess }: any) => ({
    isPending: mockMutation.isPending,
    mutate: () => {
      mockMutation.mutate();
      if (onSuccess && mockMutation.successData) onSuccess(mockMutation.successData);
    },
  }),
  useQueryClient: () => ({ invalidateQueries: jest.fn() }),
}));

jest.mock("@humansignal/app-common", () => ({
  useTranslation: () => ({
    t: (key: string, opts?: any) =>
      opts && typeof opts.count === "number" ? `${key}:${opts.count}` : key,
    i18n: { language: "en" },
  }),
}));

// ---- Import the SUT ----

import { BulkAssignPage } from "../BulkAssignPage";
import type { TrainerFilterResponse, BulkAssignResponse } from "../types";

const MATCH_RESPONSE: TrainerFilterResponse = {
  count: 3,
  items: [
    {
      id: 5,
      name: "Geeta P.",
      state: "Rajasthan",
      tier: "gold",
      language: "Hindi",
      languages: ["Hindi"],
      cert_passed: true,
      current_active_tasks_count: 8,
    },
    {
      id: 7,
      name: "Sunil M.",
      state: "UP",
      tier: "silver",
      language: "Hindi",
      languages: ["Hindi"],
      cert_passed: true,
      current_active_tasks_count: 12,
    },
    {
      id: 12,
      name: "Anil K.",
      state: "Bihar",
      tier: "bronze",
      language: "Hindi",
      languages: ["Hindi"],
      cert_passed: false,
      current_active_tasks_count: 3,
    },
  ],
};

const ASSIGNMENT_RESPONSE: BulkAssignResponse = {
  ok: true,
  project_id: 42,
  strategy: "even",
  tasks_per_trainer: 10,
  plan: [
    {
      trainer_id: 5,
      name: "Geeta P.",
      tier: "gold",
      state: "Rajasthan",
      language: "Hindi",
      will_assign: 10,
      current_active_tasks_count: 8,
      unknown: false,
    },
    {
      trainer_id: 7,
      name: "Sunil M.",
      tier: "silver",
      state: "UP",
      language: "Hindi",
      will_assign: 10,
      current_active_tasks_count: 12,
      unknown: false,
    },
    {
      trainer_id: 12,
      name: "Anil K.",
      tier: "bronze",
      state: "Bihar",
      language: "Hindi",
      will_assign: 10,
      current_active_tasks_count: 3,
      unknown: false,
    },
  ],
  totals: { trainers: 3, tasks: 30 },
  summary: { project_id: 42, trainer_count: 3, total_tasks: 30, strategy: "even" },
};

const renderPage = () =>
  render(
    <MemoryRouter>
      <BulkAssignPage />
    </MemoryRouter>,
  );

beforeEach(() => {
  setMockRole("admin");
  setMockQuery({ data: MATCH_RESPONSE, isLoading: false, isError: false });
  setMockMutation({ isPending: false, mutate: jest.fn(), successData: undefined });
});

describe("BulkAssignPage", () => {
  it("renders the page header and the filter panel", () => {
    renderPage();
    expect(screen.getByTestId("admin-bulk-assign")).toBeInTheDocument();
    expect(screen.getByTestId("bulk-filter-panel")).toBeInTheDocument();
  });

  it("renders all 4 filter chip groups", () => {
    renderPage();
    expect(screen.getByTestId("bulk-filter-state-group")).toBeInTheDocument();
    expect(screen.getByTestId("bulk-filter-tier-group")).toBeInTheDocument();
    expect(screen.getByTestId("bulk-filter-language-group")).toBeInTheDocument();
    expect(screen.getByTestId("bulk-filter-cert-group")).toBeInTheDocument();
  });

  it("renders the match table with current active task counts", () => {
    renderPage();
    expect(screen.getByTestId("bulk-match-table")).toBeInTheDocument();
    expect(screen.getByTestId("bulk-matched-count")).toHaveTextContent("3");
    expect(screen.getByTestId("bulk-tasks-now-5")).toHaveTextContent("8");
    expect(screen.getByTestId("bulk-tasks-now-7")).toHaveTextContent("12");
  });

  it("Assign button is disabled until project_id is set", () => {
    renderPage();
    const btn = screen.getByTestId("bulk-assign-submit");
    expect(btn).toBeDisabled();
    fireEvent.change(screen.getByTestId("bulk-project-id-input"), {
      target: { value: "42" },
    });
    expect(screen.getByTestId("bulk-assign-submit")).not.toBeDisabled();
  });

  it("toggles a filter chip with one click", () => {
    renderPage();
    const chip = screen.getByTestId("bulk-filter-state-Rajasthan");
    expect(chip).toHaveAttribute("aria-pressed", "false");
    fireEvent.click(chip);
    expect(screen.getByTestId("bulk-filter-state-Rajasthan")).toHaveAttribute(
      "aria-pressed",
      "true",
    );
  });

  it("renders the loading placeholder while the filter query is fetching", () => {
    setMockQuery({ data: undefined, isLoading: true, isError: false });
    renderPage();
    expect(screen.getByTestId("bulk-loading")).toBeInTheDocument();
    expect(screen.queryByTestId("bulk-filter-panel")).not.toBeInTheDocument();
  });

  it("renders the error box when the filter query fails", () => {
    setMockQuery({ data: undefined, isLoading: false, isError: true });
    renderPage();
    expect(screen.getByTestId("bulk-filter-error")).toBeInTheDocument();
  });

  it("hides the page behind a 403 fallback when the user is not admin", () => {
    setMockRole("trainer");
    renderPage();
    expect(screen.getByTestId("bulk-forbidden")).toBeInTheDocument();
    expect(screen.queryByTestId("bulk-filter-panel")).not.toBeInTheDocument();
  });

  it("opens the result drawer after a successful assignment", () => {
    setMockMutation({
      isPending: false,
      mutate: jest.fn(),
      successData: ASSIGNMENT_RESPONSE,
    });
    renderPage();
    fireEvent.change(screen.getByTestId("bulk-project-id-input"), {
      target: { value: "42" },
    });
    fireEvent.click(screen.getByTestId("bulk-assign-submit"));
    expect(screen.getByTestId("bulk-result-drawer")).toBeInTheDocument();
    expect(screen.getByTestId("bulk-result-trainer-count")).toHaveTextContent("3");
    expect(screen.getByTestId("bulk-result-task-count")).toHaveTextContent("30");
  });

  it("closes the result drawer on close button", () => {
    setMockMutation({
      isPending: false,
      mutate: jest.fn(),
      successData: ASSIGNMENT_RESPONSE,
    });
    renderPage();
    fireEvent.change(screen.getByTestId("bulk-project-id-input"), {
      target: { value: "42" },
    });
    fireEvent.click(screen.getByTestId("bulk-assign-submit"));
    expect(screen.getByTestId("bulk-result-drawer")).toBeInTheDocument();
    fireEvent.click(screen.getByTestId("bulk-result-close"));
    expect(screen.queryByTestId("bulk-result-drawer")).not.toBeInTheDocument();
  });

  it("shows the rate-limit banner when mutation reports code=rate_limited", () => {
    setMockMutation({
      isPending: false,
      mutate: jest.fn(),
      successData: { error: "Rate limit hit", code: "rate_limited" },
    });
    renderPage();
    fireEvent.change(screen.getByTestId("bulk-project-id-input"), {
      target: { value: "42" },
    });
    fireEvent.click(screen.getByTestId("bulk-assign-submit"));
    expect(screen.getByTestId("bulk-banner-error")).toHaveTextContent("admin.bulk.rate_limited");
  });

  it("changing the tasks-per-trainer slider updates the displayed value", () => {
    renderPage();
    expect(screen.getByTestId("bulk-tasks-per-trainer-value")).toHaveTextContent("10");
    fireEvent.change(screen.getByTestId("bulk-tasks-per-trainer-slider"), {
      target: { value: "25" },
    });
    expect(screen.getByTestId("bulk-tasks-per-trainer-value")).toHaveTextContent("25");
  });

  it("strategy radio toggles between even and tier-weighted", () => {
    renderPage();
    expect(screen.getByTestId("bulk-strategy-even")).toBeChecked();
    fireEvent.click(screen.getByTestId("bulk-strategy-tier"));
    expect(screen.getByTestId("bulk-strategy-tier")).toBeChecked();
  });
});

describe("BulkAssignPage metadata", () => {
  it("exposes /admin/bulk-assign as the route path", () => {
    expect((BulkAssignPage as any).path).toBe("/admin/bulk-assign");
    expect((BulkAssignPage as any).exact).toBe(true);
  });
});
