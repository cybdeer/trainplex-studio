/**
 * Tests for Step 1 — Choose Template.
 * Phase 1 Step 4.2-2.
 */

/* eslint-disable @typescript-eslint/no-var-requires */

import "@testing-library/jest-dom";
import { fireEvent, render, screen } from "@testing-library/react";

let mockLang = "en";
const setMockLang = (l: string) => {
  mockLang = l;
};

jest.mock("@humansignal/app-common", () => ({
  useTranslation: () => ({
    t: (key: string) => key,
    i18n: { language: mockLang },
  }),
}));

import { Step1Template } from "../Step1_Template";
import type { TemplateCard } from "../types";

const TEMPLATES: TemplateCard[] = [
  {
    id: "aadhaar_ocr_validation",
    title: "Aadhaar/PAN OCR Validation",
    title_hi: "आधार/पैन OCR सत्यापन",
    category: "OCR & Document",
    description: "",
    description_hi: "",
    india_relevance: "",
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
    tier: "silver",
    trainplex_custom: false,
  },
  {
    id: "image_classification",
    title: "Image Classification",
    title_hi: "",
    category: "Image",
    description: "",
    description_hi: "",
    india_relevance: "",
    thumbnail_url: null,
    tier: "bronze",
    trainplex_custom: false,
  },
];

beforeEach(() => {
  setMockLang("en");
});

describe("Step1_Template", () => {
  it("renders one card per template in the grid", () => {
    render(<Step1Template templates={TEMPLATES} selectedId={null} onSelect={() => {}} />);
    expect(screen.getByTestId("template-grid")).toBeInTheDocument();
    TEMPLATES.forEach((tpl) => {
      expect(screen.getByTestId(`template-card-${tpl.id}`)).toBeInTheDocument();
    });
  });

  it("renders the TrainPlex India badge only for trainplex_custom templates", () => {
    render(<Step1Template templates={TEMPLATES} selectedId={null} onSelect={() => {}} />);
    expect(
      screen.getByTestId("template-india-badge-aadhaar_ocr_validation"),
    ).toBeInTheDocument();
    expect(
      screen.queryByTestId("template-india-badge-text_classification"),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByTestId("template-india-badge-image_classification"),
    ).not.toBeInTheDocument();
  });

  it("invokes onSelect with the clicked template", () => {
    const onSelect = jest.fn();
    render(<Step1Template templates={TEMPLATES} selectedId={null} onSelect={onSelect} />);
    fireEvent.click(screen.getByTestId("template-card-text_classification"));
    expect(onSelect).toHaveBeenCalledTimes(1);
    expect(onSelect.mock.calls[0][0].id).toBe("text_classification");
  });

  it("marks the selected card with data-selected=true", () => {
    render(
      <Step1Template
        templates={TEMPLATES}
        selectedId="aadhaar_ocr_validation"
        onSelect={() => {}}
      />,
    );
    expect(screen.getByTestId("template-card-aadhaar_ocr_validation")).toHaveAttribute(
      "data-selected",
      "true",
    );
    expect(screen.getByTestId("template-card-text_classification")).toHaveAttribute(
      "data-selected",
      "false",
    );
  });

  it("shows Hindi title when language is hi and title_hi present", () => {
    setMockLang("hi");
    render(<Step1Template templates={TEMPLATES} selectedId={null} onSelect={() => {}} />);
    expect(screen.getByText("आधार/पैन OCR सत्यापन")).toBeInTheDocument();
    // Text Classification has no title_hi — should still show English title.
    expect(screen.getByText("Text Classification")).toBeInTheDocument();
  });

  it("renders the tier chip with the template's tier text", () => {
    render(<Step1Template templates={TEMPLATES} selectedId={null} onSelect={() => {}} />);
    expect(screen.getByTestId("template-tier-aadhaar_ocr_validation")).toHaveTextContent("bronze");
    expect(screen.getByTestId("template-tier-text_classification")).toHaveTextContent("silver");
  });
});
