/**
 * TrainerSelector — WA Broadcast trainer multi-select.
 *
 * Phase 1 Step 4.2-7. Thin wrapper around the same `Step3Assign` filter +
 * roster pattern from the Project Wizard so the admin sees one consistent
 * UX for picking trainers. The component lives in this folder (not as a
 * direct re-export) so we can ship WA-specific labels + a smaller table
 * footprint without polluting the wizard.
 *
 * Mock roster: reused from `ProjectWizard/Step3_Assign.tsx`. Real roster
 * lands in Phase 2 (Step 8) — same swap-in point.
 */

import { useMemo, useState } from "react";
import { useTranslation } from "@humansignal/app-common";
import {
  MOCK_TRAINERS,
  TP_CERTS,
  TP_LANGS,
  TP_STATES,
  TP_TIERS,
} from "../ProjectWizard/Step3_Assign";
import type { TrainerRow } from "../ProjectWizard/types";
import projectWizardStyles from "../ProjectWizard/ProjectWizard.module.css";

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
    <div className={projectWizardStyles.filterGroup} data-testid={`${testIdPrefix}-group`}>
      <span className={projectWizardStyles.filterGroupLabel}>{label}</span>
      <div className={projectWizardStyles.filterChipRow}>
        {options.map((opt) => {
          const isActive = selected.has(opt);
          return (
            <button
              key={opt}
              type="button"
              className={`${projectWizardStyles.filterChip} ${
                isActive ? projectWizardStyles.filterChipActive : ""
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

export interface TrainerSelectorProps {
  selectedIds: number[];
  onSelectionChange: (ids: number[]) => void;
  /** Optional override for the trainer roster (used by tests). */
  trainers?: TrainerRow[];
}

export function TrainerSelector({
  selectedIds,
  onSelectionChange,
  trainers = MOCK_TRAINERS,
}: TrainerSelectorProps) {
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
    <div data-testid="wa-trainer-selector">
      <div className={projectWizardStyles.filtersBlock}>
        <FilterChips
          options={TP_STATES}
          selected={filters.states}
          testIdPrefix="wa-filter-state"
          onToggle={(v) => toggle("states", v)}
          label={t("admin.wizard.filter_state")}
        />
        <FilterChips
          options={TP_TIERS}
          selected={filters.tiers}
          testIdPrefix="wa-filter-tier"
          onToggle={(v) => toggle("tiers", v)}
          label={t("admin.wizard.filter_tier")}
        />
        <FilterChips
          options={TP_LANGS}
          selected={filters.languages}
          testIdPrefix="wa-filter-language"
          onToggle={(v) => toggle("languages", v)}
          label={t("admin.wizard.filter_language")}
        />
        <FilterChips
          options={TP_CERTS}
          selected={filters.cert}
          testIdPrefix="wa-filter-cert"
          onToggle={(v) => toggle("cert", v)}
          label={t("admin.wizard.filter_cert")}
        />
      </div>

      <table className={projectWizardStyles.trainerTable} data-testid="wa-trainer-table">
        <thead>
          <tr>
            <th>
              <input
                type="checkbox"
                aria-label="Select all visible"
                data-testid="wa-trainer-select-all"
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
              <td colSpan={6} className={projectWizardStyles.emptyRow} data-testid="wa-trainer-empty">
                {t("admin.wizard.no_trainers")}
              </td>
            </tr>
          ) : (
            filtered.map((tr) => (
              <tr
                key={tr.id}
                data-testid={`wa-trainer-row-${tr.id}`}
                className={selectedSet.has(tr.id) ? projectWizardStyles.trainerRowSelected : ""}
              >
                <td>
                  <input
                    type="checkbox"
                    aria-label={`Select ${tr.name}`}
                    data-testid={`wa-trainer-checkbox-${tr.id}`}
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
    </div>
  );
}

export default TrainerSelector;
