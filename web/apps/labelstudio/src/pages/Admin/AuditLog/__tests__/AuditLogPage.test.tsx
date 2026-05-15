/**
 * Tests for the TrainPlex admin Audit Log viewer page.
 * Phase 1 Step 4.2-4.
 *
 * Strategy
 * --------
 * Same approach as `DashboardWidget.test.tsx`: mock useAuth, useAPI,
 * useTranslation, and useQuery at the module-graph level so the page
 * renders deterministically.
 *
 * Coverage:
 * - Filter bar + table render together for admin users.
 * - Filter inputs (action, success, date range) are present.
 * - Empty results show the empty-state row.
 * - Failed rows pick up the failedRow CSS hook (visible by class assertion).
 * - Clicking a row opens the drawer with metadata.
 * - Non-admin sees the 403 fallback.
 * - Loading state renders before the query resolves.
 * - Hindi mode renders the Devanagari title.
 */

/* eslint-disable @typescript-eslint/no-var-requires */

import "@testing-library/jest-dom";
import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import React from "react";

// ---- Module mocks (must come before importing the SUT) ----

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

let mockQueryState: any = { data: undefined, isFetching: true, isError: false };
const setMockQuery = (state: any) => {
  mockQueryState = state;
};
jest.mock("@tanstack/react-query", () => ({
  useQuery: () => mockQueryState,
}));

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
    t: (key: string, vars?: Record<string, unknown>) => {
      const tpl = mockTranslations[key] ?? key;
      if (!vars) return tpl;
      return tpl.replace(/\{\{(\w+)\}\}/g, (_, name) => String(vars[name] ?? ""));
    },
    i18n: { language: mockLang },
  }),
}));

// ---- Now import the SUT ----

import { AuditLogPage } from "../AuditLogPage";
import type { AuditLogResponse } from "../types";

const ROW_SUCCESS = {
  id: 1001,
  action: "login_success",
  actor: { id: 7, email: "founder@trainplex.in", role: "admin" },
  target_type: "User",
  target_id: "7",
  ip_address: "10.0.0.1",
  user_agent: "Mozilla/5.0 (Macintosh)",
  success: true,
  metadata: {},
  created_at: "2026-05-15T12:34:56Z",
};

const ROW_FAIL = {
  id: 1002,
  action: "login_fail",
  actor: null,
  target_type: "User",
  target_id: "",
  ip_address: "203.0.113.4",
  user_agent: "curl/7.79",
  success: false,
  metadata: { reason: "wrong_password" },
  created_at: "2026-05-15T12:33:00Z",
};

const RESPONSE: AuditLogResponse = {
  page: 1,
  page_size: 50,
  total: 2,
  total_pages: 1,
  results: [ROW_SUCCESS, ROW_FAIL],
};

const renderPage = () =>
  render(
    <MemoryRouter>
      <AuditLogPage />
    </MemoryRouter>,
  );

beforeEach(() => {
  setMockRole("admin");
  setMockLang("en");
  setMockTranslations({});
  setMockQuery({ data: RESPONSE, isFetching: false, isError: false });
});

describe("AuditLogPage", () => {
  it("renders filter bar + table when the query succeeds", () => {
    renderPage();
    expect(screen.getByTestId("audit-filter-bar")).toBeInTheDocument();
    expect(screen.getByTestId("audit-table")).toBeInTheDocument();
    // Two rows from the mock response.
    expect(screen.getByTestId("audit-row-1001")).toBeInTheDocument();
    expect(screen.getByTestId("audit-row-1002")).toBeInTheDocument();
  });

  it("exposes all five filter inputs in the bar", () => {
    renderPage();
    expect(screen.getByTestId("audit-filter-action")).toBeInTheDocument();
    expect(screen.getByTestId("audit-filter-actor")).toBeInTheDocument();
    expect(screen.getByTestId("audit-filter-target")).toBeInTheDocument();
    expect(screen.getByTestId("audit-filter-success")).toBeInTheDocument();
    expect(screen.getByTestId("audit-filter-start")).toBeInTheDocument();
    expect(screen.getByTestId("audit-filter-end")).toBeInTheDocument();
  });

  it("shows the empty-state row when results is empty", () => {
    setMockQuery({
      data: { page: 1, page_size: 50, total: 0, total_pages: 0, results: [] },
      isFetching: false,
      isError: false,
    });
    setMockTranslations({ "admin.audit.no_results": "No matching audit entries" });
    renderPage();
    expect(screen.getByTestId("audit-empty")).toBeInTheDocument();
    expect(screen.getByTestId("audit-empty")).toHaveTextContent("No matching audit entries");
  });

  it("shows the loading skeleton while fetching with no data yet", () => {
    setMockQuery({ data: undefined, isFetching: true, isError: false });
    renderPage();
    expect(screen.getByTestId("audit-loading")).toBeInTheDocument();
    expect(screen.queryByTestId("audit-table")).not.toBeInTheDocument();
  });

  it("opens the drawer with row metadata on row click", () => {
    setMockTranslations({
      "admin.audit.row_metadata": "Details",
      "admin.audit.col_when": "When",
    });
    renderPage();
    fireEvent.click(screen.getByTestId("audit-row-1002"));
    expect(screen.getByTestId("audit-drawer")).toBeInTheDocument();
    expect(screen.getByTestId("audit-drawer-metadata")).toHaveTextContent(
      /wrong_password/,
    );

    // Close button hides the drawer.
    fireEvent.click(screen.getByTestId("audit-drawer-close"));
    expect(screen.queryByTestId("audit-drawer")).not.toBeInTheDocument();
  });

  it("marks failed rows with the failedRow CSS hook", () => {
    renderPage();
    const failedRow = screen.getByTestId("audit-row-1002");
    // The failedRow class is a CSS-module hash; we can't predict the suffix
    // but it must include the substring `failedRow` from the module file.
    expect(failedRow.className).toMatch(/failedRow/);
    // Successful row should NOT have the hook.
    const successRow = screen.getByTestId("audit-row-1001");
    expect(successRow.className ?? "").not.toMatch(/failedRow/);
  });

  it("renders status badges using the i18n strings", () => {
    setMockTranslations({
      "admin.audit.success_yes": "Success",
      "admin.audit.success_no": "Failed",
    });
    renderPage();
    expect(screen.getByTestId("audit-row-1001-status")).toHaveTextContent("Success");
    expect(screen.getByTestId("audit-row-1002-status")).toHaveTextContent("Failed");
  });

  it("hides the page behind a 403 fallback for non-admin users", () => {
    setMockRole("trainer");
    renderPage();
    expect(screen.getByTestId("audit-forbidden")).toBeInTheDocument();
    expect(screen.queryByTestId("audit-table")).not.toBeInTheDocument();
  });

  it("renders the Hindi title when language is hi", () => {
    setMockLang("hi");
    setMockTranslations({ "admin.audit.title": "ऑडिट लॉग" });
    renderPage();
    expect(screen.getByText("ऑडिट लॉग")).toBeInTheDocument();
    // Sanity: at least one Devanagari codepoint present.
    expect(/[ऀ-ॿ]/.test(screen.getByText("ऑडिट लॉग").textContent ?? "")).toBe(true);
  });

  it("renders an error box when the query fails", () => {
    setMockQuery({ data: undefined, isFetching: false, isError: true });
    setMockTranslations({ "admin.audit.fetch_failed": "Couldn't load audit log." });
    renderPage();
    expect(screen.getByTestId("audit-error")).toBeInTheDocument();
    expect(screen.getByTestId("audit-error")).toHaveTextContent(
      "Couldn't load audit log.",
    );
  });

  it("pagination controls disable correctly at the first page of a single-page result", () => {
    renderPage();
    const prev = screen.getByTestId("audit-page-prev") as HTMLButtonElement;
    const next = screen.getByTestId("audit-page-next") as HTMLButtonElement;
    expect(prev.disabled).toBe(true);
    expect(next.disabled).toBe(true);
  });
});

describe("AuditLogPage metadata", () => {
  it("exposes /admin/audit as the route path", () => {
    expect((AuditLogPage as any).path).toBe("/admin/audit");
    expect((AuditLogPage as any).exact).toBe(true);
  });
});
