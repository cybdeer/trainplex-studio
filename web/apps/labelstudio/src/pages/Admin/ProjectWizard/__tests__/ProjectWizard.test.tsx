/**
 * Tests for the TrainPlex admin Project Wizard top-level page.
 * Phase 1 Step 4.2-2.
 *
 * Strategy mirrors `DashboardWidget.test.tsx`: mock the providers (Auth, API,
 * React Query, i18n) at the module-graph level + render with controlled
 * snapshot data. Keeps the test focused on wizard navigation + role gating.
 */

/* eslint-disable @typescript-eslint/no-var-requires */

import "@testing-library/jest-dom";
import { render, screen } from "@testing-library/react";
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
jest.mock("@tanstack/react-query", () => ({
  useQuery: () => mockQueryState,
}));

jest.mock("@humansignal/app-common", () => ({
  useTranslation: () => ({
    t: (key: string, opts?: any) =>
      opts && typeof opts.count === "number" ? `${key}:${opts.count}` : key,
    i18n: { language: "en" },
  }),
}));

// ---- Import the SUT ----

import { ProjectWizard } from "../ProjectWizard";
import type { TemplateCatalog } from "../types";

const CATALOG: TemplateCatalog = {
  count: 2,
  trainplex_count: 1,
  native_count: 1,
  items: [
    {
      id: "aadhaar_ocr_validation",
      title: "Aadhaar/PAN OCR Validation",
      title_hi: "आधार/पैन OCR सत्यापन",
      category: "OCR & Document",
      description: "Verify Aadhaar OCR fields.",
      description_hi: "OCR सत्यापन",
      india_relevance: "KYC",
      thumbnail_url: null,
      tier: "bronze",
      trainplex_custom: true,
    },
    {
      id: "text_classification",
      title: "Text Classification",
      title_hi: "",
      category: "Text / NLP",
      description: "",
      description_hi: "",
      india_relevance: "",
      thumbnail_url: null,
      tier: "bronze",
      trainplex_custom: false,
    },
  ],
};

const renderWizard = () =>
  render(
    <MemoryRouter>
      <ProjectWizard />
    </MemoryRouter>,
  );

beforeEach(() => {
  setMockRole("admin");
  setMockQuery({ data: CATALOG, isLoading: false, isError: false });
});

describe("ProjectWizard", () => {
  it("renders Step 1 by default with the template grid", () => {
    renderWizard();
    expect(screen.getByTestId("admin-project-wizard")).toBeInTheDocument();
    expect(screen.getByTestId("wizard-stepper")).toBeInTheDocument();
    expect(screen.getByTestId("wizard-step1")).toBeInTheDocument();
    expect(screen.getByTestId("template-grid")).toBeInTheDocument();
    // Step 2 and Step 3 must not be in the DOM yet.
    expect(screen.queryByTestId("wizard-step2")).not.toBeInTheDocument();
    expect(screen.queryByTestId("wizard-step3")).not.toBeInTheDocument();
  });

  it("renders the page-level title and the stepper labels", () => {
    renderWizard();
    expect(screen.getAllByText("admin.wizard.title").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByTestId("stepper-label-1")).toHaveTextContent("admin.wizard.step1");
    expect(screen.getByTestId("stepper-label-2")).toHaveTextContent("admin.wizard.step2");
    expect(screen.getByTestId("stepper-label-3")).toHaveTextContent("admin.wizard.step3");
  });

  it("Next button is disabled on Step 1 until a template is selected", () => {
    renderWizard();
    const next = screen.getByTestId("wizard-next");
    expect(next).toBeDisabled();
  });

  it("renders the loading placeholder while the catalog is fetching", () => {
    setMockQuery({ data: undefined, isLoading: true, isError: false });
    renderWizard();
    expect(screen.getByTestId("wizard-loading")).toBeInTheDocument();
    expect(screen.queryByTestId("template-grid")).not.toBeInTheDocument();
  });

  it("hides the wizard behind a 403 fallback when the user is not admin", () => {
    setMockRole("trainer");
    renderWizard();
    expect(screen.getByTestId("wizard-forbidden")).toBeInTheDocument();
    expect(screen.queryByTestId("template-grid")).not.toBeInTheDocument();
  });

  it("renders an error box when the catalog query fails", () => {
    setMockQuery({ data: undefined, isLoading: false, isError: true });
    renderWizard();
    expect(screen.getByTestId("wizard-error")).toBeInTheDocument();
  });
});

describe("ProjectWizard page metadata", () => {
  it("exposes /admin/projects/new as the route path", () => {
    expect((ProjectWizard as any).path).toBe("/admin/projects/new");
    expect((ProjectWizard as any).exact).toBe(true);
  });
});
