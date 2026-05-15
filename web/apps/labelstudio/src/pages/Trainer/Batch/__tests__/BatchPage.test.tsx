/**
 * Tests for the TrainPlex trainer batch view.
 * Phase 1 Step 1.4-E.
 *
 * Strategy mirrors `HeatmapPage.test.tsx`: mock providers (Auth, API,
 * React Query, i18n) at the module-graph level + render with controlled
 * inputs.
 *
 * Coverage
 * --------
 * - Renders one tile per task given the 10-task mock batch.
 * - Earnings ticker totals match the batch sum (₹ done / ₹ total).
 * - Progress dots: one per task; done dots carry the "done" data-status.
 * - Batch progress pill reads "{done}/{total} done".
 * - Loading skeleton shows while fetching with no data.
 * - Error box shows when the query errors.
 * - Non-trainer (admin, reviewer) sees the RoleGate fallback.
 * - Completion modal renders when every task is `done`.
 * - Completion modal does NOT render when at least one task is pending.
 * - Hindi translation keys produce Devanagari output.
 * - Page metadata exposes /trainer/batch as the route path.
 */

/* eslint-disable @typescript-eslint/no-var-requires */

import "@testing-library/jest-dom";
import { render, screen, fireEvent } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import React from "react";

jest.mock("../../../../providers/ApiProvider", () => ({
  useAPI: () => ({ callApi: jest.fn() }),
  ApiContext: { Provider: ({ children }: any) => children },
}));

let mockUserRole: string | null = "trainer";
const setMockRole = (role: string | null) => {
  mockUserRole = role;
};
jest.mock("@humansignal/core/providers/AuthProvider", () => ({
  useAuth: () => ({ user: { role: mockUserRole } }),
}));

let mockQueryState: any = { data: undefined, isFetching: true, isError: false };
const mockInvalidate = jest.fn();
const setMockQuery = (state: any) => {
  mockQueryState = state;
};
jest.mock("@tanstack/react-query", () => ({
  useQuery: () => mockQueryState,
  useQueryClient: () => ({ invalidateQueries: mockInvalidate }),
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
    t: (key: string, vars?: Record<string, string | number>) => {
      const raw = mockTranslations[key] ?? key;
      if (!vars) return raw;
      return raw.replace(/\{\{(\w+)\}\}/g, (_, k) => String(vars[k] ?? ""));
    },
    i18n: { language: mockLang },
  }),
  // TrainPlex Phase 1 Step 4.3 + 4.4 — BatchPage now imports the offline
  // submit-queue helpers. The real implementation needs IndexedDB which
  // isn't worth wiring into every existing test; jest.fn stubs are
  // enough since these existing assertions don't touch the queue path.
  enqueueSubmit: jest.fn(),
  flushQueue: jest.fn(),
  onQueueChange: jest.fn(() => () => undefined),
}));

import { BatchPage } from "../BatchPage";
import type { BatchTask } from "../types";

// 10-task batch mirroring the backend's deterministic mock for user_id=1.
const BATCH: BatchTask[] = [
  { task_id: 9001001, project_id: 1000, task_type: "image_classification", preview: "Classify the object", earnings_inr: 8, estimated_min: 1, tier: "bronze", status: "in_progress" },
  { task_id: 9001002, project_id: 1001, task_type: "bounding_box", preview: "Draw bounding boxes", earnings_inr: 15, estimated_min: 3, tier: "silver", status: "in_progress" },
  { task_id: 9001003, project_id: 1002, task_type: "text_sentiment", preview: "Tag the sentiment", earnings_inr: 5, estimated_min: 1, tier: "bronze", status: "pending" },
  { task_id: 9001004, project_id: 1003, task_type: "audio_transcription", preview: "Transcribe audio", earnings_inr: 25, estimated_min: 5, tier: "silver", status: "pending" },
  { task_id: 9001005, project_id: 1004, task_type: "ocr_kyc", preview: "Read Aadhaar", earnings_inr: 12, estimated_min: 2, tier: "silver", status: "pending" },
  { task_id: 9001006, project_id: 1000, task_type: "video_action", preview: "Tag action", earnings_inr: 20, estimated_min: 4, tier: "gold", status: "pending" },
  { task_id: 9001007, project_id: 1001, task_type: "translation_qa", preview: "Review translation", earnings_inr: 10, estimated_min: 2, tier: "silver", status: "pending" },
  { task_id: 9001008, project_id: 1002, task_type: "named_entity", preview: "Tag entities", earnings_inr: 14, estimated_min: 3, tier: "silver", status: "pending" },
  { task_id: 9001009, project_id: 1003, task_type: "safety_review", preview: "Flag unsafe", earnings_inr: 7, estimated_min: 1, tier: "bronze", status: "pending" },
  { task_id: 9001010, project_id: 1004, task_type: "qa_dispute_review", preview: "Review dispute", earnings_inr: 30, estimated_min: 5, tier: "gold", status: "pending" },
];

const renderBatch = () =>
  render(
    <MemoryRouter>
      <BatchPage />
    </MemoryRouter>,
  );

beforeEach(() => {
  setMockRole("trainer");
  setMockLang("en");
  setMockTranslations({});
  setMockQuery({ data: BATCH, isFetching: false, isError: false });
  mockInvalidate.mockClear();
});

describe("BatchPage", () => {
  it("renders one tile per task given the 10-task batch", () => {
    renderBatch();
    expect(screen.getByTestId("batch-tile-grid")).toBeInTheDocument();
    BATCH.forEach((t) => {
      expect(screen.getByTestId(`task-card-${t.task_id}`)).toBeInTheDocument();
    });
  });

  it("renders the earnings ticker with done/total totals", () => {
    renderBatch();
    const ticker = screen.getByTestId("earnings-ticker");
    expect(ticker).toBeInTheDocument();
    // Two tasks are in_progress, none done → done total = ₹0.
    const earnings = screen.getByTestId("ticker-earnings");
    // Total of the 10 sample tasks: 8+15+5+25+12+20+10+14+7+30 = 146.
    expect(earnings.textContent ?? "").toContain("₹0");
    expect(earnings.textContent ?? "").toContain("/ ₹146");
  });

  it("renders one progress dot per task with correct data-status", () => {
    renderBatch();
    const dots = screen.getByTestId("ticker-progress-dots").children;
    expect(dots.length).toBe(BATCH.length);
    expect((dots[0] as HTMLElement).getAttribute("data-status")).toBe("in_progress");
    expect((dots[2] as HTMLElement).getAttribute("data-status")).toBe("pending");
  });

  it("renders the {done}/{total} progress pill", () => {
    setMockTranslations({
      "trainer.batch.title": "Today's Batch",
      "trainer.batch.progress": "{{done}}/{{total}} done",
    });
    renderBatch();
    // No tasks are done in the seed batch — pill should say "0/10 done".
    const pill = screen.getByTestId("batch-progress-pill");
    expect(pill.textContent ?? "").toContain("0/10 done");
  });

  it("renders the loading skeleton when fetching with no data", () => {
    setMockQuery({ data: undefined, isFetching: true, isError: false });
    renderBatch();
    expect(screen.getByTestId("batch-skeleton")).toBeInTheDocument();
    expect(screen.queryByTestId("batch-tile-grid")).not.toBeInTheDocument();
  });

  it("renders the error box when the batch query fails", () => {
    setMockQuery({ data: undefined, isFetching: false, isError: true });
    setMockTranslations({ "trainer.batch.load_failed": "Couldn't load your batch." });
    renderBatch();
    expect(screen.getByTestId("batch-error")).toBeInTheDocument();
    expect(screen.getByTestId("batch-error")).toHaveTextContent("Couldn't load your batch.");
  });

  it("hides the page behind 403 fallback when the user is admin", () => {
    setMockRole("admin");
    renderBatch();
    expect(screen.getByTestId("batch-forbidden")).toBeInTheDocument();
    expect(screen.queryByTestId("batch-tile-grid")).not.toBeInTheDocument();
  });

  it("hides the page behind 403 fallback when the user is reviewer", () => {
    setMockRole("reviewer");
    renderBatch();
    expect(screen.getByTestId("batch-forbidden")).toBeInTheDocument();
  });

  it("does NOT show the completion celebration when any task is pending", () => {
    renderBatch();
    expect(screen.queryByTestId("batch-celebration")).not.toBeInTheDocument();
  });

  it("shows the completion celebration when every task is done", () => {
    const finishedBatch: BatchTask[] = BATCH.map((t) => ({ ...t, status: "done" }));
    setMockQuery({ data: finishedBatch, isFetching: false, isError: false });
    setMockTranslations({
      "trainer.batch.complete": "Batch complete!",
      "trainer.batch.next_batch": "Start Next Batch",
    });
    renderBatch();
    expect(screen.getByTestId("batch-celebration")).toBeInTheDocument();
    expect(screen.getByTestId("celebration-earnings").textContent).toContain("₹146");
    expect(screen.getByTestId("celebration-task-count").textContent).toBe("10");
  });

  it("clicking 'Start Next Batch' invalidates the batch query", () => {
    const finishedBatch: BatchTask[] = BATCH.map((t) => ({ ...t, status: "done" }));
    setMockQuery({ data: finishedBatch, isFetching: false, isError: false });
    setMockTranslations({ "trainer.batch.next_batch": "Start Next Batch →" });
    renderBatch();
    fireEvent.click(screen.getByTestId("celebration-next-batch"));
    expect(mockInvalidate).toHaveBeenCalled();
  });

  it("renders Devanagari labels when the language is Hindi", () => {
    setMockLang("hi");
    setMockTranslations({
      "trainer.batch.title": "आज का बैच",
      "trainer.batch.progress": "{{done}}/{{total}} पूरे",
      "trainer.batch.earnings_so_far": "अब तक की कमाई",
    });
    renderBatch();
    expect(screen.getByText("आज का बैच")).toBeInTheDocument();
    const header = screen.getByText("आज का बैच").textContent ?? "";
    expect(/[ऀ-ॿ]/.test(header)).toBe(true);
  });
});

describe("BatchPage page metadata", () => {
  it("exposes /trainer/batch as the route path", () => {
    expect((BatchPage as any).path).toBe("/trainer/batch");
    expect((BatchPage as any).exact).toBe(true);
  });
});
