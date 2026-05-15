import { registerAnalytics } from "@humansignal/core";
registerAnalytics();

// TrainPlex Step 1.4-C — Initialize i18n (en / hi) BEFORE any React component mounts,
// so the very first render of <App/> already has translations resolved + the persisted
// language pulled out of localStorage (`tp_lang`) / cookie. Importing the config module
// runs `i18n.init()` as a side effect (LanguageDetector resolves synchronously inside
// init, so `i18n.language` is already populated by the time the next line runs).
//
// Note: ES module imports below are hoisted, but the side-effect statements between
// imports still run in source order RELATIVE TO EACH OTHER once all modules have been
// evaluated. The `i18n.on(...)` + `document.documentElement.lang` calls below must run
// after `i18n` is initialized — that's guaranteed because they live in the same module
// after the `import i18n from "..."` line.
import i18n from "@humansignal/app-common/i18n/config";

// Keep <html lang="..."> in sync with the active i18n language so the CSS rules in
// `tokens.trainplex.css` ([lang="hi"] line-height / Devanagari kerning) kick in automatically.
i18n.on("languageChanged", (lng) => {
  document.documentElement.lang = lng;
});
// Apply the initial detected language too.
document.documentElement.lang = i18n.language || "en";

import "./app/App";
import "./utils/service-worker";
import "./utils/state-registry-lso";
