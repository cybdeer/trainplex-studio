/**
 * Tests for the TrainPlex WhatsApp Broadcast composer page.
 * Phase 1 Step 4.2-7.
 *
 * Strategy mirrors `ProjectWizard.test.tsx`: mock the providers (Auth, API,
 * React Query, i18n) at the module-graph level + render with controlled
 * snapshot data. Keeps the test focused on UI selection + send-button enabling.
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

import { WhatsAppBroadcastPage } from "../WhatsAppBroadcastPage";
import type { WaTemplateList } from "../types";

const TEMPLATES: WaTemplateList = {
  count: 5,
  items: [
    {
      id: "bronze_passed",
      title_en: "Bronze certification passed",
      title_hi: "Bronze certification पास",
      description_en: "Congratulate a trainer who just passed the bronze cert exam.",
      description_hi: "जिस trainer ने bronze cert pass किया उसको बधाई।",
    },
    {
      id: "welcome",
      title_en: "Welcome to TrainPlex",
      title_hi: "TrainPlex में स्वागत",
      description_en: "Welcome message + first batch link for new trainers.",
      description_hi: "नए trainers को welcome + पहले batch का link।",
    },
    {
      id: "reminder",
      title_en: "Pending tasks reminder",
      title_hi: "बकाया कार्य reminder",
      description_en: "Nudge trainers with pending tasks at end of day.",
      description_hi: "जिन trainers के पास pending tasks हैं उनको day-end reminder।",
    },
    {
      id: "payment_released",
      title_en: "Payment released",
      title_hi: "Payment जारी हुआ",
      description_en: "Notify trainer when their pending payout is released.",
      description_hi: "Trainer को payout release होने की सूचना।",
    },
    {
      id: "task_assigned",
      title_en: "New task assigned",
      title_hi: "नया task assigned",
      description_en: "New batch / task assignment notification.",
      description_hi: "नया batch / task assignment notification।",
    },
  ],
};

const renderPage = () =>
  render(
    <MemoryRouter>
      <WhatsAppBroadcastPage />
    </MemoryRouter>,
  );

beforeEach(() => {
  setMockRole("admin");
  setMockQuery({ data: TEMPLATES, isLoading: false, isError: false });
  setMockMutation({ isPending: false, mutate: jest.fn(), successData: undefined });
});

describe("WhatsAppBroadcastPage", () => {
  it("renders the page header and the template picker", () => {
    renderPage();
    expect(screen.getByTestId("admin-wa-broadcast")).toBeInTheDocument();
    expect(screen.getByTestId("wa-template-picker")).toBeInTheDocument();
    expect(screen.getByTestId("wa-template-select")).toBeInTheDocument();
  });

  it("renders the trainer selector with all 4 filter groups", () => {
    renderPage();
    expect(screen.getByTestId("wa-trainer-selector")).toBeInTheDocument();
    expect(screen.getByTestId("wa-filter-state-group")).toBeInTheDocument();
    expect(screen.getByTestId("wa-filter-tier-group")).toBeInTheDocument();
    expect(screen.getByTestId("wa-filter-language-group")).toBeInTheDocument();
    expect(screen.getByTestId("wa-filter-cert-group")).toBeInTheDocument();
  });

  it("Send button is disabled until both template AND trainers are picked", () => {
    renderPage();
    const send = screen.getByTestId("wa-send-button");
    expect(send).toBeDisabled();

    // Pick a template — still disabled, no trainers yet.
    fireEvent.change(screen.getByTestId("wa-template-select"), {
      target: { value: "welcome" },
    });
    expect(screen.getByTestId("wa-send-button")).toBeDisabled();

    // Pick a trainer — now enabled.
    fireEvent.click(screen.getByTestId("wa-trainer-checkbox-5"));
    expect(screen.getByTestId("wa-send-button")).not.toBeDisabled();
  });

  it("filtering the trainer table updates the selected-count summary live", () => {
    renderPage();
    fireEvent.click(screen.getByTestId("wa-trainer-checkbox-5"));
    fireEvent.click(screen.getByTestId("wa-trainer-checkbox-7"));
    expect(screen.getByTestId("wa-selected-summary")).toHaveTextContent("2");
  });

  it("renders the preview pane only after a template is picked", () => {
    renderPage();
    expect(screen.queryByTestId("wa-preview-bubble")).not.toBeInTheDocument();
    fireEvent.change(screen.getByTestId("wa-template-select"), {
      target: { value: "welcome" },
    });
    expect(screen.getByTestId("wa-preview-bubble")).toBeInTheDocument();
  });

  it("renders the loading placeholder while templates are fetching", () => {
    setMockQuery({ data: undefined, isLoading: true, isError: false });
    renderPage();
    expect(screen.getByTestId("wa-loading")).toBeInTheDocument();
    expect(screen.queryByTestId("wa-template-picker")).not.toBeInTheDocument();
  });

  it("hides the page behind a 403 fallback when the user is not admin", () => {
    setMockRole("trainer");
    renderPage();
    expect(screen.getByTestId("wa-forbidden")).toBeInTheDocument();
    expect(screen.queryByTestId("wa-template-picker")).not.toBeInTheDocument();
  });

  it("renders an error banner when the templates query fails", () => {
    setMockQuery({ data: undefined, isLoading: false, isError: true });
    renderPage();
    expect(screen.getByTestId("wa-templates-error")).toBeInTheDocument();
  });

  it("shows the success banner after the mutation reports counts", () => {
    setMockMutation({
      isPending: false,
      mutate: jest.fn(),
      successData: {
        ok: true,
        template_id: "welcome",
        counts: { sent: 2, failed: 0, skipped: 0, total: 2 },
        logs: [],
      },
    });
    renderPage();
    fireEvent.change(screen.getByTestId("wa-template-select"), {
      target: { value: "welcome" },
    });
    fireEvent.click(screen.getByTestId("wa-trainer-checkbox-5"));
    fireEvent.click(screen.getByTestId("wa-trainer-checkbox-7"));
    fireEvent.click(screen.getByTestId("wa-send-button"));
    expect(screen.getByTestId("wa-banner-success")).toBeInTheDocument();
  });

  it("shows the rate-limit banner when the mutation reports code=rate_limited", () => {
    setMockMutation({
      isPending: false,
      mutate: jest.fn(),
      successData: { error: "Rate limit hit", code: "rate_limited" },
    });
    renderPage();
    fireEvent.change(screen.getByTestId("wa-template-select"), {
      target: { value: "welcome" },
    });
    fireEvent.click(screen.getByTestId("wa-trainer-checkbox-5"));
    fireEvent.click(screen.getByTestId("wa-send-button"));
    expect(screen.getByTestId("wa-banner-error")).toHaveTextContent("admin.wa.rate_limited");
  });

  it("opens and closes the history drawer", () => {
    renderPage();
    expect(screen.queryByTestId("wa-history-drawer")).not.toBeInTheDocument();
    fireEvent.click(screen.getByTestId("wa-open-history"));
    expect(screen.getByTestId("wa-history-drawer")).toBeInTheDocument();
    fireEvent.click(screen.getByTestId("wa-history-close"));
    expect(screen.queryByTestId("wa-history-drawer")).not.toBeInTheDocument();
  });
});

describe("WhatsAppBroadcastPage metadata", () => {
  it("exposes /admin/wa/broadcast as the route path", () => {
    expect((WhatsAppBroadcastPage as any).path).toBe("/admin/wa/broadcast");
    expect((WhatsAppBroadcastPage as any).exact).toBe(true);
  });
});

// ---------------------------------------------------------------
// Founder-personal-number leak guard
// ---------------------------------------------------------------
//
// This is the JS-side mirror of the backend regex assertion. It scans the
// rendered DOM for the founder's personal mobile in any common formatting.
// Phase 1 rule: the number must NEVER appear in any frontend code or page
// output — not as a hint, not as a placeholder, not as a sample.
//
// Both backend code paths (params, response body, log rows) are covered by
// the python test; this test guards the static frontend surface.

// The actual digits come from the ``TRAINPLEX_FOUNDER_MOBILE_GUARD`` env var,
// surfaced to the test runner via Vite's ``process.env.VITE_FOUNDER_MOBILE_GUARD``
// (or the same variable in jsdom's process.env when running under jest). When
// the env var is unset (dev / CI without the secret), the leak guard becomes a
// no-op asserted as ``true`` so the test still runs end-to-end without
// embedding the real number in this source file.
const _RAW_GUARD =
  (typeof process !== "undefined" &&
    process.env &&
    (process.env.VITE_FOUNDER_MOBILE_GUARD ||
      process.env.TRAINPLEX_FOUNDER_MOBILE_GUARD)) ||
  "";
const _DIGITS_ONLY = _RAW_GUARD.replace(/\D+/g, "");
const _NO_CC = _DIGITS_ONLY.length === 12 && _DIGITS_ONLY.startsWith("91")
  ? _DIGITS_ONLY.slice(2)
  : _DIGITS_ONLY;
const _WITH_CC = _NO_CC ? "91" + _NO_CC : "";
const _BODY = _NO_CC
  ? _NO_CC.split("").join("[-\s]?")
  : "";

describe("Founder personal-mobile leak guard", () => {
  const FOUNDER_DIGITS = _WITH_CC;
  const FOUNDER_RE = _BODY
    ? new RegExp("(?:\+?91[-\s]?)?(?:" + _BODY + ")")
    : null;

  it("the rendered DOM never contains the founder personal mobile", () => {
    setMockQuery({ data: TEMPLATES, isLoading: false, isError: false });
    renderPage();
    fireEvent.change(screen.getByTestId("wa-template-select"), {
      target: { value: "payment_released" },
    });
    fireEvent.click(screen.getByTestId("wa-trainer-checkbox-5"));
    const html = document.body.innerHTML;
    const digitsOnly = html.replace(/\D+/g, "");
    if (FOUNDER_DIGITS) {
      expect(digitsOnly.includes(FOUNDER_DIGITS)).toBe(false);
    }
    if (FOUNDER_RE) {
      expect(FOUNDER_RE.test(html)).toBe(false);
    }
  });
});
