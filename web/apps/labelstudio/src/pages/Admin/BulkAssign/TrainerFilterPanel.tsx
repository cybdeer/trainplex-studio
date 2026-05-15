/**
 * TrainerFilterPanel — chip-based filter for the Bulk Assign page.
 *
 * Phase 1 Step 4.2-3. Reuses the same 4 filter groups (State / Tier /
 * Language / Cert) the founder team already learnt on the Project Wizard
 * Step 3 + WA Broadcast pages.
 *
 * The chip option lists are imported from the wizard so a single source
 * of truth keeps the three admin surfaces visually identical.
 */

import { useTranslation } from "@humansignal/app-common";
import {
  TP_CERTS,
  TP_LANGS,
  TP_STATES,
  TP_TIERS,
} from "../ProjectWizard/Step3_Assign";
import type { BulkFilterState } from "./types";
import styles from "./BulkAssign.module.css";

type FilterKey = keyof BulkFilterState;

interface FilterChipsProps {
  options: readonly string[];
  selected: Set<string>;
  testIdPrefix: string;
  onToggle: (value: string) => void;
  label: string;
}

function FilterChips({ options, selected, testIdPrefix, onToggle, label }: FilterChipsProps) {
  return (
    <div className={styles.filterGroup} data-testid={`${testIdPrefix}-group`}>
      <span className={styles.filterGroupLabel}>{label}</span>
      <div className={styles.filterChipRow}>
        {options.map((opt) => {
          const isActive = selected.has(opt);
          return (
            <button
              key={opt}
              type="button"
              className={`${styles.filterChip} ${
                isActive ? styles.filterChipActive : ""
              }`}
              data-testid={`${testIdPrefix}-${opt}`}
              aria-pressed={isActive}
              onClick={() => onToggle(opt)}
            >
              {opt}
            </button>
          );
        })}
      </div>
    </div>
  );
}

export interface TrainerFilterPanelProps {
  filters: BulkFilterState;
  onToggle: (key: FilterKey, value: string) => void;
}

export function TrainerFilterPanel({ filters, onToggle }: TrainerFilterPanelProps) {
  const { t } = useTranslation();

  return (
    <div className={styles.filtersBlock} data-testid="bulk-filter-panel">
      <h2 className={styles.sectionHeading}>{t("admin.bulk.filter_panel")}</h2>
      <FilterChips
        options={TP_STATES}
        selected={filters.states}
        testIdPrefix="bulk-filter-state"
        onToggle={(v) => onToggle("states", v)}
        label={t("admin.wizard.filter_state")}
      />
      <FilterChips
        options={TP_TIERS}
        selected={filters.tiers}
        testIdPrefix="bulk-filter-tier"
        onToggle={(v) => onToggle("tiers", v)}
        label={t("admin.wizard.filter_tier")}
      />
      <FilterChips
        options={TP_LANGS}
        selected={filters.languages}
        testIdPrefix="bulk-filter-language"
        onToggle={(v) => onToggle("languages", v)}
        label={t("admin.wizard.filter_language")}
      />
      <FilterChips
        options={TP_CERTS}
        selected={filters.cert}
        testIdPrefix="bulk-filter-cert"
        onToggle={(v) => onToggle("cert", v)}
        label={t("admin.wizard.filter_cert")}
      />
    </div>
  );
}

export default TrainerFilterPanel;
