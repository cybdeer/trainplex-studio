/**
 * Tests for the TrainPlex Admin Submissions Preview drawer.
 * Phase 1 Step 4.2-9.
 *
 * Strategy
 * --------
 * Same approach as `QualityAlertsPage.test.tsx` and
 * `DashboardWidget.test.tsx`: mock useAuth, useAPI, useTranslation and
 * useQuery at the module-graph level so the drawer renders deterministically.
 *
 * Coverage
 * --------
 * - Drawer renders for admin with mock response (cards + filter toolbar).
 * - Card count matches the response payload.
 * - Each card surfaces task / answer / 3 reviewer dots / status.
 * - URL `task_preview` renders an <img>, text renders a snippet.
 * - Status filter dropdown changes update the query params.
 * - Empty state renders when response has 0 rows.
 * - Loading skeleton renders before the first response.
 * - Error box renders on query failure.
 * - Non-admin sees the forbidden box (and no fetch fired).
 * - `open={false}` renders nothing.
 * - Backdrop click + X-button close fire the parent's onClose.
 * - Hindi mode renders the Devanagari title.
 * - ReviewerScoreBadges renders 3 dots with right agreed attrs.
 */

/* eslint-disable @typescript-eslint/no-var-requires */

import "@testing-library/jest-dom";
import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

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

import { SubmissionsPreviewDrawer } from "../SubmissionsPreviewDrawer";
import { ReviewerScoreBadges } from "../ReviewerScoreBadges";
import type {
  SubmissionPreview,
  SubmissionsPreviewResponse,
} from "../types";

const IMAGE_ROW: SubmissionPreview = {
  id: 9000,
  project_id: 501,
  trainer: { id: 101, name: "Geeta P.", role: "trainer" },
  task_preview: "https://placehold.co/120x120/png?text=KYC+1",
  answer_preview: '{"first_name": "Geeta", "last_name": "Patel"}',
  reviewer_scores: [
    { reviewer_id: 201, score: 1, agreed: true },
    { reviewer_id: 202, score: 1, agreed: true },
    { reviewer_id: 203, score: 1, agreed: true },
  ],
  created_at: "2026-05-15T12:34:56Z",
  status: "approved",
};

const TEXT_ROW: SubmissionPreview = {
  id: 9001,
  project_id: 502,
  trainer: { id: 102, name: "Sunil M.", role: "trainer" },
  task_preview: 'Identify the language: "नमस्ते"',
  answer_preview: '{"language": "Hindi"}',
  reviewer_scores: [
    { reviewer_id: 201, score: 1, agreed: true },
    { reviewer_id: 202, score: 0, agreed: false },
    { reviewer_id: 203, score: 0, agreed: false },
  ],
  created_at: "2026-05-15T12:22:56Z",
  status: "rejected",
};

const RESPONSE: SubmissionsPreviewResponse = {
  as_of: "2026-05-15T13:00:00Z",
  limit: 10,
  filters: {},
  submissions: [IMAGE_ROW, TEXT_ROW],
};

const renderDrawer = (props?: Partial<React.ComponentProps<typeof SubmissionsPreviewDrawer>>) => {
  const onClose = props?.onClose ?? jest.fn();
  return {
    onClose,
    ...render(
      <MemoryRouter>
        <SubmissionsPreviewDrawer open onClose={onClose} {...props} />
      </MemoryRouter>,
    ),
  };
};

beforeEach(() => {
  setMockRole("admin");
  setMockLang("en");
  setMockTranslations({});
  setMockQuery({ data: RESPONSE, isFetching: false, isError: false });
});

describe("SubmissionsPreviewDrawer", () => {
  it("renders nothing when open is false", () => {
    const onClose = jest.fn();
    render(
      <MemoryRouter>
        <SubmissionsPreviewDrawer open={false} onClose={onClose} />
      </MemoryRouter>,
    );
    expect(screen.queryByTestId("submissions-preview-drawer")).not.toBeInTheDocument();
  });

  it("renders the drawer with cards + filter toolbar for admin", () => {
    renderDrawer();
    expect(screen.getByTestId("submissions-preview-drawer")).toBeInTheDocument();
    expect(screen.getByTestId("submissions-preview-toolbar")).toBeInTheDocument();
    expect(screen.getByTestId("submissions-preview-status-filter")).toBeInTheDocument();
    expect(screen.getByTestId("submissions-preview-list")).toBeInTheDocument();
    // One card per response row.
    expect(screen.getByTestId(`submission-card-${IMAGE_ROW.id}`)).toBeInTheDocument();
    expect(screen.getByTestId(`submission-card-${TEXT_ROW.id}`)).toBeInTheDocument();
  });

  it("renders the trainer name + answer + status pill for each card", () => {
    renderDrawer();
    expect(screen.getByTestId(`submission-trainer-${IMAGE_ROW.id}`)).toHaveTextContent(
      "Geeta P.",
    );
    expect(screen.getByTestId(`submission-answer-${IMAGE_ROW.id}`)).toHaveTextContent(
      "first_name",
    );
    expect(screen.getByTestId(`submission-status-${IMAGE_ROW.id}`)).toBeInTheDocument();
  });

  it("renders an <img> when task_preview is an http(s) URL", () => {
    renderDrawer();
    const thumb = screen.getByTestId(`submission-task-thumb-${IMAGE_ROW.id}`);
    expect(thumb.tagName).toBe("IMG");
    expect(thumb).toHaveAttribute("src", IMAGE_ROW.task_preview);
  });

  it("renders a text snippet when task_preview is not a URL", () => {
    renderDrawer();
    const text = screen.getByTestId(`submission-task-text-${TEXT_ROW.id}`);
    expect(text).toBeInTheDocument();
    expect(text).toHaveTextContent("Identify the language");
    // And there's no image element for that row.
    expect(
      screen.queryByTestId(`submission-task-thumb-${TEXT_ROW.id}`),
    ).not.toBeInTheDocument();
  });

  it("renders 3 reviewer dots per card with correct agreed attrs", () => {
    renderDrawer();
    // IMAGE_ROW: all 3 agreed → all data-agreed='true'.
    for (let i = 0; i < 3; i++) {
      const dot = screen.getByTestId(`reviewer-score-dot-${IMAGE_ROW.id}-${i}`);
      expect(dot).toHaveAttribute("data-agreed", "true");
    }
    // TEXT_ROW: first agreed, last 2 disagreed.
    expect(
      screen.getByTestId(`reviewer-score-dot-${TEXT_ROW.id}-0`),
    ).toHaveAttribute("data-agreed", "true");
    expect(
      screen.getByTestId(`reviewer-score-dot-${TEXT_ROW.id}-1`),
    ).toHaveAttribute("data-agreed", "false");
    expect(
      screen.getByTestId(`reviewer-score-dot-${TEXT_ROW.id}-2`),
    ).toHaveAttribute("data-agreed", "false");
    // Summary shows agreed/total.
    expect(
      screen.getByTestId(`reviewer-score-summary-${IMAGE_ROW.id}`),
    ).toHaveTextContent("3/3");
    expect(
      screen.getByTestId(`reviewer-score-summary-${TEXT_ROW.id}`),
    ).toHaveTextContent("1/3");
  });

  it("changes status filter when the dropdown is updated", () => {
    renderDrawer();
    const select = screen.getByTestId(
      "submissions-preview-status-filter",
    ) as HTMLSelectElement;
    expect(select.value).toBe("");
    fireEvent.change(select, { target: { value: "approved" } });
    expect(
      (screen.getByTestId("submissions-preview-status-filter") as HTMLSelectElement)
        .value,
    ).toBe("approved");
  });

  it("renders the empty-state row when results is empty", () => {
    setMockQuery({
      data: { as_of: "x", limit: 10, filters: {}, submissions: [] },
      isFetching: false,
      isError: false,
    });
    setMockTranslations({ "admin.submissions.no_recent": "No recent submissions" });
    renderDrawer();
    expect(screen.getByTestId("submissions-preview-empty")).toBeInTheDocument();
    expect(screen.getByTestId("submissions-preview-empty")).toHaveTextContent(
      "No recent submissions",
    );
  });

  it("renders the loading state while fetching with no data yet", () => {
    setMockQuery({ data: undefined, isFetching: true, isError: false });
    renderDrawer();
    expect(screen.getByTestId("submissions-preview-loading")).toBeInTheDocument();
    expect(screen.queryByTestId("submissions-preview-list")).not.toBeInTheDocument();
  });

  it("renders the error box when the query fails", () => {
    setMockQuery({ data: undefined, isFetching: false, isError: true });
    setMockTranslations({
      "admin.submissions.fetch_failed": "Couldn't load submissions.",
    });
    renderDrawer();
    expect(screen.getByTestId("submissions-preview-error")).toBeInTheDocument();
    expect(screen.getByTestId("submissions-preview-error")).toHaveTextContent(
      "Couldn't load submissions.",
    );
  });

  it("hides the drawer body behind a 403 surface for non-admin users", () => {
    setMockRole("trainer");
    renderDrawer();
    expect(screen.getByTestId("submissions-preview-forbidden")).toBeInTheDocument();
    expect(screen.queryByTestId("submissions-preview-list")).not.toBeInTheDocument();
  });

  it("fires onClose when the backdrop is clicked", () => {
    const onClose = jest.fn();
    renderDrawer({ onClose });
    fireEvent.click(screen.getByTestId("submissions-preview-backdrop"));
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("fires onClose when the X button is clicked", () => {
    const onClose = jest.fn();
    renderDrawer({ onClose });
    fireEvent.click(screen.getByTestId("submissions-preview-close"));
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("does not fire onClose when the drawer body is clicked", () => {
    const onClose = jest.fn();
    renderDrawer({ onClose });
    fireEvent.click(screen.getByTestId("submissions-preview-drawer"));
    expect(onClose).not.toHaveBeenCalled();
  });

  it("renders the Hindi title when language is hi", () => {
    setMockLang("hi");
    setMockTranslations({ "admin.submissions.title": "हाल के जमा कार्य" });
    renderDrawer();
    expect(screen.getByText("हाल के जमा कार्य")).toBeInTheDocument();
    expect(/[ऀ-ॿ]/.test(screen.getByText("हाल के जमा कार्य").textContent ?? "")).toBe(
      true,
    );
  });
});

describe("ReviewerScoreBadges", () => {
  it("renders exactly 3 dots even when given fewer scores", () => {
    render(
      <ReviewerScoreBadges
        scores={[{ reviewer_id: 1, score: 1, agreed: true }]}
        testIdSuffix="t1"
      />,
    );
    // Padded to 3 dots — last 2 default to disagreed.
    expect(screen.getByTestId("reviewer-score-dot-t1-0")).toHaveAttribute(
      "data-agreed",
      "true",
    );
    expect(screen.getByTestId("reviewer-score-dot-t1-1")).toHaveAttribute(
      "data-agreed",
      "false",
    );
    expect(screen.getByTestId("reviewer-score-dot-t1-2")).toHaveAttribute(
      "data-agreed",
      "false",
    );
    expect(screen.getByTestId("reviewer-score-summary-t1")).toHaveTextContent(
      "1/3",
    );
  });

  it("renders agreed-count data attribute on the wrapper", () => {
    render(
      <ReviewerScoreBadges
        scores={[
          { reviewer_id: 1, score: 1, agreed: true },
          { reviewer_id: 2, score: 1, agreed: true },
          { reviewer_id: 3, score: 0, agreed: false },
        ]}
        testIdSuffix="t2"
      />,
    );
    expect(screen.getByTestId("reviewer-score-badges-t2")).toHaveAttribute(
      "data-agreed-count",
      "2",
    );
  });
});
