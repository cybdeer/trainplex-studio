/**
 * StateTable — fallback / detail view for the admin India heatmap.
 *
 * Phase 1 Step 4.2-6.
 *
 * Renders the same `StateActivity[]` data as `IndiaMap`, but as a sortable
 * table — useful for screen readers and for founders who want exact numbers.
 *
 * Sort
 * ----
 * Default sort is by `active_trainers` desc — same ordering the heatmap uses
 * to drive its colour ramp, so the two views always tell the same story.
 * Clicking any column header toggles asc/desc.
 *
 * Locale
 * ------
 * Numbers go through `Intl.NumberFormat('hi-IN' / 'en-IN')`. INR amounts use
 * the `style: 'currency'` formatter — no paise (backend returns whole rupees).
 */

import { useMemo, useState } from "react";
import { useTranslation } from "@humansignal/app-common";
import type { HeatmapSortKey, StateActivity } from "./types";
import styles from "./Heatmap.module.css";

export interface StateTableProps {
  data: StateActivity[];
}

const formatInt = (locale: string, value: number) =>
  new Intl.NumberFormat(locale === "hi" ? "hi-IN" : "en-IN").format(value);

const formatINR = (locale: string, value: number) =>
  new Intl.NumberFormat(locale === "hi" ? "hi-IN" : "en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: 0,
  }).format(value);

type SortDir = "asc" | "desc";

interface SortState {
  key: HeatmapSortKey;
  dir: SortDir;
}

const DEFAULT_SORT: SortState = { key: "active_trainers", dir: "desc" };

function sortRows(rows: StateActivity[], sort: SortState): StateActivity[] {
  const copy = [...rows];
  copy.sort((a, b) => {
    const va = a[sort.key];
    const vb = b[sort.key];
    if (typeof va === "string" && typeof vb === "string") {
      const cmp = va.localeCompare(vb);
      return sort.dir === "asc" ? cmp : -cmp;
    }
    const cmp = (va as number) - (vb as number);
    return sort.dir === "asc" ? cmp : -cmp;
  });
  return copy;
}

export function StateTable({ data }: StateTableProps) {
  const { t, i18n } = useTranslation();
  const locale = i18n.language || "en";
  const [sort, setSort] = useState<SortState>(DEFAULT_SORT);

  const sorted = useMemo(() => sortRows(data, sort), [data, sort]);

  const toggleSort = (key: HeatmapSortKey) => {
    setSort((prev) =>
      prev.key === key
        ? { key, dir: prev.dir === "asc" ? "desc" : "asc" }
        : // First click on a new column: numeric cols default to desc (most
          // useful for activity rankings); the state-name col defaults to asc.
          { key, dir: key === "state_name" ? "asc" : "desc" },
    );
  };

  const indicator = (key: HeatmapSortKey) => {
    if (sort.key !== key) return null;
    return (
      <span className={styles.sortIndicator} aria-hidden="true">
        {sort.dir === "asc" ? "▲" : "▼"}
      </span>
    );
  };

  return (
    <section
      className={styles.tableBlock}
      data-testid="state-table"
      aria-label={t("admin.heatmap.table_heading")}
    >
      <h3 className={styles.tableHeading}>{t("admin.heatmap.table_heading")}</h3>
      <table className={styles.stateTable}>
        <thead>
          <tr>
            <th
              role="columnheader"
              aria-sort={sort.key === "state_name" ? (sort.dir === "asc" ? "ascending" : "descending") : "none"}
              onClick={() => toggleSort("state_name")}
              data-testid="th-state"
            >
              {t("admin.heatmap.col_state")}
              {indicator("state_name")}
            </th>
            <th
              className={styles.colNum}
              role="columnheader"
              aria-sort={sort.key === "active_trainers" ? (sort.dir === "asc" ? "ascending" : "descending") : "none"}
              onClick={() => toggleSort("active_trainers")}
              data-testid="th-trainers"
            >
              {t("admin.heatmap.col_trainers")}
              {indicator("active_trainers")}
            </th>
            <th
              className={styles.colNum}
              role="columnheader"
              aria-sort={sort.key === "submissions_count" ? (sort.dir === "asc" ? "ascending" : "descending") : "none"}
              onClick={() => toggleSort("submissions_count")}
              data-testid="th-submissions"
            >
              {t("admin.heatmap.col_submissions")}
              {indicator("submissions_count")}
            </th>
            <th
              className={styles.colNum}
              role="columnheader"
              aria-sort={sort.key === "total_earnings_inr" ? (sort.dir === "asc" ? "ascending" : "descending") : "none"}
              onClick={() => toggleSort("total_earnings_inr")}
              data-testid="th-earnings"
            >
              {t("admin.heatmap.col_earnings")}
              {indicator("total_earnings_inr")}
            </th>
          </tr>
        </thead>
        <tbody>
          {sorted.map((row) => (
            <tr key={row.state_code} data-testid={`state-row-${row.state_code}`}>
              <td>{row.state_name}</td>
              <td className={styles.colNum}>{formatInt(locale, row.active_trainers)}</td>
              <td className={styles.colNum}>{formatInt(locale, row.submissions_count)}</td>
              <td className={styles.colNum}>{formatINR(locale, row.total_earnings_inr)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}

export default StateTable;
