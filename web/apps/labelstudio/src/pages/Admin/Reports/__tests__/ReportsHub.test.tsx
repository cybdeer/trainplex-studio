/**
 * Tests for the TrainPlex Reports Hub.
 * Phase 1 Step 7.
 *
 * Coverage
 * --------
 * - Hub renders 4 link cards when admin
 * - Non-admin sees the RoleGate fallback
 * - Each card title comes from i18n
 * - Page metadata exposes /admin/reports as the route path
 */

/* eslint-disable @typescript-eslint/no-var-requires */

import "@testing-library/jest-dom";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import React from "react";

let mockUserRole: string | null = "admin";
jest.mock("@humansignal/core/providers/AuthProvider", () => ({
  useAuth: () => ({ user: { role: mockUserRole } }),
}));

let mockLang = "en";
let mockTranslations: Record<string, string> = {};
jest.mock("@humansignal/app-common", () => ({
  useTranslation: () => ({
    t: (key: string) => mockTranslations[key] ?? key,
    i18n: { language: mockLang },
  }),
}));

import { ReportsHub } from "../ReportsHub";

const renderHub = () =>
  render(
    <MemoryRouter>
      <ReportsHub />
    </MemoryRouter>,
  );

describe("ReportsHub", () => {
  beforeEach(() => {
    mockUserRole = "admin";
    mockLang = "en";
    mockTranslations = {};
  });

  it("renders 4 link cards for admin", () => {
    renderHub();
    expect(screen.getByTestId("hub-link-founder")).toBeInTheDocument();
    expect(screen.getByTestId("hub-link-leaderboard")).toBeInTheDocument();
    expect(screen.getByTestId("hub-link-cohorts")).toBeInTheDocument();
    expect(screen.getByTestId("hub-link-project-roi")).toBeInTheDocument();
  });

  it("links target the 4 sub-pages", () => {
    renderHub();
    expect(screen.getByTestId("hub-link-founder")).toHaveAttribute("href", "/admin/reports/founder");
    expect(screen.getByTestId("hub-link-leaderboard")).toHaveAttribute("href", "/admin/reports/leaderboard");
    expect(screen.getByTestId("hub-link-cohorts")).toHaveAttribute("href", "/admin/reports/cohorts");
    expect(screen.getByTestId("hub-link-project-roi")).toHaveAttribute("href", "/admin/reports/project-roi");
  });

  it("blocks non-admin with the RoleGate fallback", () => {
    mockUserRole = "trainer";
    renderHub();
    expect(screen.getByTestId("reports-forbidden")).toBeInTheDocument();
  });

  it("renders Hindi labels when locale is hi", () => {
    mockLang = "hi";
    mockTranslations = {
      "admin.reports.title": "रिपोर्ट",
      "admin.reports.founder_weekly": "साप्ताहिक रिपोर्ट",
    };
    renderHub();
    expect(screen.getByText("रिपोर्ट")).toBeInTheDocument();
    expect(screen.getByText("साप्ताहिक रिपोर्ट")).toBeInTheDocument();
  });

  it("exposes route path metadata", () => {
    expect(ReportsHub.path).toBe("/admin/reports");
    expect(ReportsHub.exact).toBe(true);
  });
});
