import * as pages from "./pages";

export { pages };

// Hooks
export { useStateHistory, type StateHistoryItem, type StateHistoryResponse } from "./hooks/useStateHistory";

// Components
export * from "./components/state-chips";

// i18n
export { i18n, SUPPORTED_LANGUAGES, useTranslation, Trans } from "./i18n";
export type { SupportedLanguage } from "./i18n";

// TrainPlex Phase 1 Step 4.3 + 4.4 — Offline submit queue (IndexedDB).
// The BatchPage subscribes to `onQueueChange` for the "Offline · N queued"
// chip; the SW + the client-side `online` listener both call `flushQueue`.
export {
  enqueueSubmit,
  getQueue,
  removeFromQueue,
  onQueueChange,
  flushQueue,
  backoffMs,
} from "./offline/submit-queue";
export type { QueuedSubmit, FlushQueueOptions, FlushQueueResult } from "./offline/submit-queue";
