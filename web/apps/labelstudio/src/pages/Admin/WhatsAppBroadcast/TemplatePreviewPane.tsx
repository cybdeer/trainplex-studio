/**
 * TemplatePreviewPane — WhatsApp-styled bubble showing the rendered template.
 *
 * Phase 1 Step 4.2-7. The admin sees what the first trainer will receive,
 * with WA-brand green bubble styling so it's instantly recognizable as a
 * WhatsApp preview. The actual message body in Phase 1 is a deterministic
 * placeholder per template (Week 8 wires real AiSensy template bodies).
 */

import { useTranslation } from "@humansignal/app-common";
import type { WaTemplate } from "./types";
import styles from "./WhatsAppBroadcast.module.css";

/**
 * Phase 1 placeholder template bodies — deterministic per id so the preview
 * is stable. The real text lives in AiSensy's template store and is
 * fetched at send-time in Week 8.
 *
 * Founder note: NONE of these bodies reference the founder's personal
 * mobile (see the backend guard in `core/services/wa_broadcast.py` for the
 * exact detection digits). All support flows route through the
 * trainplex-helpline (a future placeholder).
 */
const PHASE_1_TEMPLATE_BODIES: Record<string, { en: string; hi: string }> = {
  bronze_passed: {
    en: "Hi {{name}}! Congrats — you passed the Bronze certification. You're now eligible for paid Bronze tasks. — TrainPlex",
    hi: "नमस्ते {{name}}! बधाई हो — आपने Bronze certification pass कर लिया है। अब आप paid Bronze tasks के लिए eligible हैं। — TrainPlex",
  },
  welcome: {
    en: "Welcome to TrainPlex, {{name}}! Tap the link in your email to claim your first batch. — TrainPlex",
    hi: "TrainPlex में स्वागत है {{name}}! अपना पहला batch claim करने के लिए email का link tap करें। — TrainPlex",
  },
  reminder: {
    en: "Hi {{name}}, you have pending tasks today. Open the app to complete and earn. — TrainPlex",
    hi: "नमस्ते {{name}}, आज आपके पास pending tasks हैं। पूरा करने और कमाने के लिए app खोलें। — TrainPlex",
  },
  payment_released: {
    en: "Hi {{name}}, ₹{{amount}} payment released to your account. Check the app for details. — TrainPlex",
    hi: "नमस्ते {{name}}, ₹{{amount}} का payment आपके खाते में जारी हुआ। विवरण के लिए app देखें। — TrainPlex",
  },
  task_assigned: {
    en: "Hi {{name}}, a new batch is assigned to you. Open the app to start. — TrainPlex",
    hi: "नमस्ते {{name}}, आपको नया batch assigned हुआ है। शुरू करने के लिए app खोलें। — TrainPlex",
  },
};

export interface TemplatePreviewPaneProps {
  template: WaTemplate | null;
  /** Sample params for the preview (first trainer's row in Phase 1). */
  sampleParams?: Record<string, string | number>;
}

function renderBody(body: string, params: Record<string, string | number>): string {
  let rendered = body;
  for (const [k, v] of Object.entries(params)) {
    rendered = rendered.replace(new RegExp(`\\{\\{\\s*${k}\\s*\\}\\}`, "g"), String(v));
  }
  return rendered;
}

export function TemplatePreviewPane({ template, sampleParams = {} }: TemplatePreviewPaneProps) {
  const { t, i18n } = useTranslation();
  const isHi = i18n.language === "hi";

  if (!template) {
    return null;
  }

  const body = PHASE_1_TEMPLATE_BODIES[template.id];
  if (!body) {
    return null;
  }

  const chosen = isHi ? body.hi : body.en;
  const rendered = renderBody(chosen, sampleParams);

  return (
    <div className={styles.previewWrap} data-testid="wa-preview-pane">
      <h3 className={styles.sectionHeading}>{t("admin.wa.preview")}</h3>
      <div className={styles.previewBubble} data-testid="wa-preview-bubble">
        {rendered}
      </div>
      <span className={styles.previewMeta} data-testid="wa-preview-meta">
        {template.id} · {isHi ? "hi" : "en"}
      </span>
    </div>
  );
}

export default TemplatePreviewPane;
