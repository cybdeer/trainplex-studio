/**
 * Step 1 — Choose Template.
 *
 * Phase 1 Step 4.2-2. 4-column responsive grid of template cards (60 total:
 * 10 TrainPlex India + 50 LS native). Each card shows: bilingual title,
 * category badge, optional "TrainPlex India" badge, and a tier chip. Click
 * selects the template and highlights the card; the parent advances to Step 2
 * via the "Next" button (handled by `ProjectWizard.tsx`).
 *
 * The component is presentational — it does not fetch the catalog itself;
 * the parent passes `templates` so loading / error states stay in one place.
 */

import { useTranslation } from "@humansignal/app-common";
import type { TemplateCard } from "./types";
import styles from "./ProjectWizard.module.css";

export interface Step1TemplateProps {
  templates: TemplateCard[];
  /** Currently-selected template id (or null). */
  selectedId: string | null;
  /** Called when the user picks a card. */
  onSelect: (template: TemplateCard) => void;
}

/**
 * Resolve the display title — Hindi if available + language is hi, else
 * the English title. Hindi titles only exist for TrainPlex India templates
 * in Phase 1, which is exactly the right behaviour: the 10 India templates
 * surface in Devanagari, the 50 LS native ones stay in English until
 * localized in Phase 2.
 */
function titleFor(t: TemplateCard, lang: string): string {
  if (lang === "hi" && t.title_hi) return t.title_hi;
  return t.title;
}

export function Step1Template({ templates, selectedId, onSelect }: Step1TemplateProps) {
  const { t, i18n } = useTranslation();
  const lang = i18n.language || "en";

  return (
    <section
      className={styles.step1Root}
      aria-label={t("admin.wizard.step1")}
      data-testid="wizard-step1"
    >
      <h2 className={styles.stepHeading}>{t("admin.wizard.step1")}</h2>
      <div className={styles.templateGrid} data-testid="template-grid">
        {templates.map((tpl) => {
          const isSelected = tpl.id === selectedId;
          const cardClass = [
            styles.templateCard,
            isSelected ? styles.templateCardSelected : "",
          ].join(" ");
          return (
            <button
              key={tpl.id}
              type="button"
              className={cardClass}
              data-testid={`template-card-${tpl.id}`}
              data-selected={isSelected ? "true" : "false"}
              aria-pressed={isSelected}
              onClick={() => onSelect(tpl)}
            >
              <div className={styles.templateCardHeader}>
                <span className={styles.templateCategoryBadge}>{tpl.category}</span>
                {tpl.trainplex_custom ? (
                  <span
                    className={styles.templateIndiaBadge}
                    data-testid={`template-india-badge-${tpl.id}`}
                  >
                    TrainPlex India
                  </span>
                ) : null}
              </div>
              <div className={styles.templateCardTitle}>{titleFor(tpl, lang)}</div>
              {tpl.title_hi && lang !== "hi" ? (
                <div className={styles.templateCardSubtitle}>{tpl.title_hi}</div>
              ) : null}
              <div className={styles.templateCardFooter}>
                <span
                  className={`${styles.tierChip} ${styles[`tier_${tpl.tier}`] || ""}`}
                  data-testid={`template-tier-${tpl.id}`}
                >
                  {tpl.tier}
                </span>
              </div>
            </button>
          );
        })}
      </div>
    </section>
  );
}

export default Step1Template;
