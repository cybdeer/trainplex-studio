/**
 * TemplatePicker — Dropdown of 5 known WA templates (en + hi labels).
 *
 * Phase 1 Step 4.2-7. Keeps the picker dumb: parent owns selected id +
 * the list of templates, this component just renders the `<select>` + the
 * bilingual description block underneath. Tested independently in
 * `__tests__/WhatsAppBroadcastPage.test.tsx`.
 */

import { useTranslation } from "@humansignal/app-common";
import type { WaTemplate } from "./types";
import styles from "./WhatsAppBroadcast.module.css";

export interface TemplatePickerProps {
  templates: WaTemplate[];
  value: string | null;
  onChange: (id: string) => void;
  /** Optional placeholder shown when no template is selected. */
  placeholder?: string;
}

export function TemplatePicker({
  templates,
  value,
  onChange,
  placeholder,
}: TemplatePickerProps) {
  const { t, i18n } = useTranslation();
  const isHi = i18n.language === "hi";

  const selected = templates.find((tpl) => tpl.id === value) || null;

  return (
    <div className={styles.templatePicker} data-testid="wa-template-picker">
      <label className={styles.templateSelectLabel} htmlFor="wa-template-select">
        {t("admin.wa.choose_template")}
      </label>
      <select
        id="wa-template-select"
        className={styles.templateSelect}
        data-testid="wa-template-select"
        value={value || ""}
        onChange={(e) => onChange(e.target.value)}
      >
        <option value="">{placeholder || t("admin.wa.choose_template")}</option>
        {templates.map((tpl) => (
          <option key={tpl.id} value={tpl.id} data-testid={`wa-template-option-${tpl.id}`}>
            {isHi ? `${tpl.title_hi} (${tpl.title_en})` : `${tpl.title_en} — ${tpl.title_hi}`}
          </option>
        ))}
      </select>
      {selected ? (
        <div className={styles.templateDescription} data-testid="wa-template-description">
          {selected.description_en}
          <span className={styles.templateDescriptionHi}>{selected.description_hi}</span>
        </div>
      ) : null}
    </div>
  );
}

export default TemplatePicker;
