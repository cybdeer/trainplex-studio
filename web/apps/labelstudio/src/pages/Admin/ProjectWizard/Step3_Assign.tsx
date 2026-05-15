/**
 * Step 3 — Assign Trainers.
 *
 * Phase 1 Step 4.2-2. Multi-select trainer table with chip-based filters:
 * State (12 Indian states multi-pick), Tier (bronze/silver/gold/platinum),
 * Language (Hindi/Tamil/Telugu/Bengali/Marathi/Gujarati/Punjabi), and Cert
 * (passed/pending). Rows are checkbox-select.
 *
 * Trainer roster is mocked locally — the real `/api/v1/admin/trainers/`
 * roster endpoint lands in Phase 2 (Step 8 migration). The shape of the
 * mock matches `TrainerRow` so the swap is one network call away.
 */

import { useMemo, useState } from "react";
import { useTranslation } from "@humansignal/app-common";
import type { TrainerRow } from "./types";
import styles from "./ProjectWizard.module.css";

/** 12 Indian states the founder team primarily operates in. */
export const TP_STATES = [
  "Rajasthan",
  "UP",
  "Gujarat",
  "Punjab",
  "MP",
  "Bihar",
  "Maharashtra",
  "Haryana",
  "Tamil Nadu",
  "Telangana",
  "Karnataka",
  "West Bengal",
] as const;

export const TP_TIERS = ["bronze", "silver", "gold", "platinum"] as const;

export const TP_LANGS = [
  "Hindi",
  "Tamil",
  "Telugu",
  "Bengali",
  "Marathi",
  "Gujarati",
  "Punjabi",
] as const;

export const TP_CERTS = ["passed", "pending"] as const;

/**
 * Mock trainer roster — used until the real API endpoint exists in Phase 2.
 * Exported so tests can assert filter behaviour deterministically.
 *
 * TODO Phase 2: replace with `useQuery('admin/trainers/roster')`.
 */
export const MOCK_TRAINERS: TrainerRow[] = [
  { id: 5, name: "Geeta P.", state: "Rajasthan", tier: "gold", languages: ["Hindi"], cert: "passed" },
  { id: 7, name: "Sunil M.", state: "UP", tier: "silver", languages: ["Hindi"], cert: "passed" },
  { id: 12, name: "Anil K.", state: "Bihar", tier: "bronze", languages: ["Hindi"], cert: "pending" },
  { id: 19, name: "Rekha S.", state: "MP", tier: "gold", languages: ["Hindi"], cert: "passed" },
  { id: 23, name: "Vikas T.", state: "Haryana", tier: "silver", languages: ["Hindi", "Punjabi"], cert: "passed" },
  { id: 31, name: "Priya N.", state: "Maharashtra", tier: "platinum", languages: ["Marathi", "Hindi"], cert: "passed" },
  { id: 42, name: "Karthik R.", state: "Tamil Nadu", tier: "gold", languages: ["Tamil"], cert: "passed" },
  { id: 47, name: "Lakshmi V.", state: "Telangana", tier: "silver", languages: ["Telugu"], cert: "pending" },
  { id: 51, name: "Amitabh G.", state: "Gujarat", tier: "bronze", languages: ["Gujarati", "Hindi"], cert: "passed" },
  { id: 58, name: "Sneha M.", state: "Punjab", tier: "gold", languages: ["Punjabi", "Hindi"], cert: "passed" },
  { id: 63, name: "Raju D.", state: "Karnataka", tier: "silver", languages: ["Hindi"], cert: "pending" },
  { id: 71, name: "Mita B.", state: "West Bengal", tier: "bronze", languages: ["Bengali"], cert: "passed" },
];

export interface Step3AssignProps {
  selectedIds: number[];
  onSelectionChange: (ids: number[]) => void;
  /** Optional override for the trainer roster (used by tests). */
  trainers?: TrainerRow[];
}

type FilterKey = "states" | "tiers" | "languages" | "cert";

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
              className={`${styles.filterChip} ${isActive ? styles.filterChipActive : ""}`}
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

export function Step3Assign({
  selectedIds,
  onSelectionChange,
  trainers = MOCK_TRAINERS,
}: Step3AssignProps) {
  const { t } = useTranslation();
  const [filters, setFilters] = useState<Record<FilterKey, Set<string>>>({
    states: new Set(),
    tiers: new Set(),
    languages: new Set(),
    cert: new Set(),
  });

  const toggle = (key: FilterKey, value: string) => {
    setFilters((prev) => {
      const next = { ...prev };
      const setCopy = new Set(prev[key]);
      if (setCopy.has(value)) setCopy.delete(value);
      else setCopy.add(value);
      next[key] = setCopy;
      return next;
    });
  };

  const filtered = useMemo(() => {
    return trainers.filter((tr) => {
      if (filters.states.size > 0 && !filters.states.has(tr.state)) return false;
      if (filters.tiers.size > 0 && !filters.tiers.has(tr.tier)) return false;
      if (filters.cert.size > 0 && !filters.cert.has(tr.cert)) return false;
      if (filters.languages.size > 0) {
        const overlap = tr.languages.some((l) => filters.languages.has(l));
        if (!overlap) return false;
      }
      return true;
    });
  }, [trainers, filters]);

  const selectedSet = new Set(selectedIds);

  const toggleTrainer = (id: number) => {
    if (selectedSet.has(id)) {
      onSelectionChange(selectedIds.filter((x) => x !== id));
    } else {
      onSelectionChange([...selectedIds, id]);
    }
  };

  const allFilteredSelected =
    filtered.length > 0 && filtered.every((tr) => selectedSet.has(tr.id));

  const toggleSelectAll = () => {
    if (allFilteredSelected) {
      onSelectionChange(selectedIds.filter((id) => !filtered.some((tr) => tr.id === id)));
    } else {
      const merged = new Set(selectedIds);
      filtered.forEach((tr) => merged.add(tr.id));
      onSelectionChange(Array.from(merged));
    }
  };

  return (
    <section
      className={styles.step3Root}
      aria-label={t("admin.wizard.step3")}
      data-testid="wizard-step3"
    >
      <h2 className={styles.stepHeading}>{t("admin.wizard.step3")}</h2>

      <div className={styles.filtersBlock}>
        <FilterChips
          options={TP_STATES}
          selected={filters.states}
          testIdPrefix="filter-state"
          onToggle={(v) => toggle("states", v)}
          label={t("admin.wizard.filter_state")}
        />
        <FilterChips
          options={TP_TIERS}
          selected={filters.tiers}
          testIdPrefix="filter-tier"
          onToggle={(v) => toggle("tiers", v)}
          label={t("admin.wizard.filter_tier")}
        />
        <FilterChips
          options={TP_LANGS}
          selected={filters.languages}
          testIdPrefix="filter-language"
          onToggle={(v) => toggle("languages", v)}
          label={t("admin.wizard.filter_language")}
        />
        <FilterChips
          options={TP_CERTS}
          selected={filters.cert}
          testIdPrefix="filter-cert"
          onToggle={(v) => toggle("cert", v)}
          label={t("admin.wizard.filter_cert")}
        />
      </div>

      <table className={styles.trainerTable} data-testid="trainer-table">
        <thead>
          <tr>
            <th>
              <input
                type="checkbox"
                aria-label="Select all visible"
                data-testid="trainer-select-all"
                checked={allFilteredSelected}
                onChange={toggleSelectAll}
              />
            </th>
            <th>{t("admin.wizard.col_name")}</th>
            <th>{t("admin.wizard.col_state")}</th>
            <th>{t("admin.wizard.col_tier")}</th>
            <th>{t("admin.wizard.col_languages")}</th>
            <th>{t("admin.wizard.col_cert")}</th>
          </tr>
        </thead>
        <tbody>
          {filtered.length === 0 ? (
            <tr>
              <td colSpan={6} className={styles.emptyRow} data-testid="trainer-empty">
                {t("admin.wizard.no_trainers")}
              </td>
            </tr>
          ) : (
            filtered.map((tr) => (
              <tr
                key={tr.id}
                data-testid={`trainer-row-${tr.id}`}
                className={selectedSet.has(tr.id) ? styles.trainerRowSelected : ""}
              >
                <td>
                  <input
                    type="checkbox"
                    aria-label={`Select ${tr.name}`}
                    data-testid={`trainer-checkbox-${tr.id}`}
                    checked={selectedSet.has(tr.id)}
                    onChange={() => toggleTrainer(tr.id)}
                  />
                </td>
                <td>{tr.name}</td>
                <td>{tr.state}</td>
                <td>{tr.tier}</td>
                <td>{tr.languages.join(", ")}</td>
                <td>{tr.cert}</td>
              </tr>
            ))
          )}
        </tbody>
      </table>

      <div className={styles.selectedSummary} data-testid="wizard-selected-summary">
        {t("admin.wizard.selected_count", { count: selectedIds.length })}
      </div>
    </section>
  );
}

export default Step3Assign;
