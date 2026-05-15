/**
 * Shared types for the TrainPlex Admin Project Wizard.
 *
 * Mirrors the backend contract in
 * `label_studio/core/views_template_gallery.py`. Single source of truth on the
 * frontend so the 3 step components agree on shapes without duck-typing.
 *
 * Phase 1 Step 4.2-2.
 */

/** One card in the Step 1 template gallery. */
export interface TemplateCard {
  id: string;
  /** English title — always present. */
  title: string;
  /** Hindi title — empty string for LS native templates in Phase 1. */
  title_hi: string;
  /** Display group (e.g. "Text / NLP", "Image", "OCR & Document"). */
  category: string;
  description: string;
  description_hi: string;
  /** Why this template matters for the Indian market — TrainPlex India only. */
  india_relevance: string;
  thumbnail_url: string | null;
  /** Labeler tier required (bronze / silver / gold / platinum). */
  tier: string;
  /** True iff sourced from `backend/data/ls_templates/trainplex_india/`. */
  trainplex_custom: boolean;
}

/** Response shape of GET /api/v1/admin/templates/catalog. */
export interface TemplateCatalog {
  count: number;
  trainplex_count: number;
  native_count: number;
  items: TemplateCard[];
}

/** Mock trainer roster row used by Step 3 until the real roster API lands. */
export interface TrainerRow {
  id: number;
  name: string;
  state: string;
  tier: "bronze" | "silver" | "gold" | "platinum";
  languages: string[];
  cert: "passed" | "pending";
}

/** Possible filter chip values for Step 3. */
export interface TrainerFilters {
  states: string[];
  tiers: string[];
  languages: string[];
  cert: string[];
}

/** Wizard state, threaded through the 3 step components. */
export interface WizardState {
  step: 1 | 2 | 3;
  templateId: string | null;
  template: TemplateCard | null;
  projectName: string;
  /** Upload reference — placeholder string in Phase 1 (real wiring in Phase 2). */
  dataFileUploadId: string | null;
  trainerIds: number[];
}
