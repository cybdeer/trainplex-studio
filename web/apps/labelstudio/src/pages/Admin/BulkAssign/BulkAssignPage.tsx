/**
 * BulkAssignPage — TrainPlex Admin Bulk Task Assign composer.
 *
 * Phase 1 Step 4.2-3. Per plan: "State / tier / language / cert pe filter
 * → ek baar me 100 trainers ko tasks assign. Manual ek-ek checkbox khatam."
 *
 * Layout
 * ------
 *   ┌─────────────────────────────────────────────────────┐
 *   │ Bulk Task Assign                                    │  ← Indigo header
 *   ├─────────────────────────────────────────────────────┤
 *   │ Filter trainers                                     │
 *   │   [State chips] [Tier chips] [Lang chips] [Cert]    │
 *   ├─────────────────────────────────────────────────────┤
 *   │ N trainers matched                                  │
 *   │   ┌─────┬─────┬────┬─────┬────┬─────────────────┐   │
 *   │   │Name │State│Tier│Lang │Cert│ Current tasks   │   │
 *   │   └─────┴─────┴────┴─────┴────┴─────────────────┘   │
 *   ├─────────────────────────────────────────────────────┤
 *   │ Choose project [id] | Tasks/trainer [—■—] 10        │
 *   │ ( ) Even   ( ) Tier-weighted                        │
 *   │             [ Assign to N trainers ]  ← Saffron CTA │
 *   └─────────────────────────────────────────────────────┘
 *
 * Backend wiring
 * --------------
 *   GET  /api/v1/admin/trainers/filter        → match table
 *   POST /api/v1/admin/tasks/bulk-assign      → submit (mock plan, real
 *                                                wire-in Phase 2)
 *
 * Phase 1 caveats
 * ---------------
 * The trainer roster is mocked at the backend (same 12 rows as Project
 * Wizard Step 3) and the assignment itself is logged-not-persisted. The
 * frontend shape stays identical when Phase 2 swaps the backend.
 */

import { RoleGate, Spinner } from "@humansignal/ui";
import { useTranslation } from "@humansignal/app-common";
import { useMutation, useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { useAuth } from "@humansignal/core/providers/AuthProvider";
import { useAPI } from "../../../providers/ApiProvider";
import type { Page } from "../../types/Page";
import { AssignmentForm } from "./AssignmentForm";
import { AssignmentResultDrawer } from "./AssignmentResultDrawer";
import { TrainerFilterPanel } from "./TrainerFilterPanel";
import { TrainerMatchTable } from "./TrainerMatchTable";
import type {
  BulkAssignResponse,
  BulkFilterState,
  DistributeStrategy,
  TrainerFilterResponse,
} from "./types";
import styles from "./BulkAssign.module.css";

type FilterKey = keyof BulkFilterState;

function filtersToCsv(values: Set<string>): string | undefined {
  return values.size === 0 ? undefined : Array.from(values).join(",");
}

const FILTER_QUERY_KEY = "admin-bulk-trainer-filter";

export const BulkAssignPage: Page = () => {
  const api = useAPI();
  const { t } = useTranslation();
  const { user } = useAuth();

  const [filters, setFilters] = useState<BulkFilterState>({
    states: new Set(),
    tiers: new Set(),
    languages: new Set(),
    cert: new Set(),
  });
  const [projectIdInput, setProjectIdInput] = useState<string>("");
  const [tasksPerTrainer, setTasksPerTrainer] = useState<number>(10);
  const [strategy, setStrategy] = useState<DistributeStrategy>("even");
  const [drawerOpen, setDrawerOpen] = useState<boolean>(false);
  const [resultBanner, setResultBanner] = useState<
    { kind: "success" | "error"; text: string } | null
  >(null);
  const [assignmentResult, setAssignmentResult] = useState<BulkAssignResponse | null>(null);

  const toggleFilter = (key: FilterKey, value: string) => {
    setFilters((prev) => {
      const next = { ...prev };
      const copy = new Set(prev[key]);
      if (copy.has(value)) copy.delete(value);
      else copy.add(value);
      next[key] = copy;
      return next;
    });
  };

  // Encode every selected chip into the query so the backend filter
  // matches what the user sees. Empty sets collapse to undefined so we
  // don't send `state=&tier=` noise.
  const queryParams = useMemo(
    () => ({
      state: filtersToCsv(filters.states),
      tier: filtersToCsv(filters.tiers),
      language: filtersToCsv(filters.languages),
      cert_passed: filtersToCsv(filters.cert),
    }),
    [filters],
  );

  const filterQuery = useQuery<TrainerFilterResponse>({
    queryKey: [FILTER_QUERY_KEY, queryParams],
    queryFn: async () => {
      const res = await api.callApi("adminTrainerFilter", { params: queryParams });
      return (res as TrainerFilterResponse) ?? { count: 0, items: [] };
    },
    staleTime: 30_000,
    enabled: user?.role === "admin",
  });

  const matchedTrainers = filterQuery.data?.items ?? [];

  const submitMutation = useMutation<BulkAssignResponse | undefined, Error, void>({
    mutationFn: async () => {
      const project_id = Number(projectIdInput);
      if (!Number.isFinite(project_id) || project_id <= 0) return undefined;
      const trainer_ids = matchedTrainers.map((tr) => tr.id);
      if (trainer_ids.length === 0) return undefined;
      const body = {
        project_id,
        trainer_ids,
        tasks_per_trainer: tasksPerTrainer,
        distribute_strategy: strategy,
      };
      const res = (await api.callApi("adminBulkAssign", { body })) as
        | BulkAssignResponse
        | undefined;
      return res;
    },
    onSuccess: (res) => {
      if (!res) {
        setResultBanner({ kind: "error", text: t("admin.bulk.assign_failed") });
        return;
      }
      const errLike = (res as any)?.error;
      if (errLike) {
        const code = (res as any)?.code;
        if (code === "rate_limited") {
          setResultBanner({ kind: "error", text: t("admin.bulk.rate_limited") });
        } else {
          setResultBanner({ kind: "error", text: String(errLike) });
        }
        return;
      }
      setAssignmentResult(res);
      setDrawerOpen(true);
      setResultBanner({
        kind: "success",
        text: t("admin.bulk.assign_button", { count: res.summary.trainer_count }),
      });
    },
    onError: (err) => {
      setResultBanner({ kind: "error", text: err.message || t("admin.bulk.assign_failed") });
    },
  });

  const projectIdValid = (() => {
    const n = Number(projectIdInput);
    return Number.isFinite(n) && n > 0;
  })();

  const canSubmit =
    projectIdValid && matchedTrainers.length > 0 && !submitMutation.isPending;

  const body = (() => {
    if (filterQuery.isLoading) {
      return (
        <div className={styles.loadingBox} role="status" aria-live="polite" data-testid="bulk-loading">
          <Spinner />
          <span>{t("common.loading")}</span>
        </div>
      );
    }
    if (filterQuery.isError) {
      return (
        <div className={styles.errorBox} data-testid="bulk-filter-error">
          {t("admin.bulk.filter_failed")}
        </div>
      );
    }
    return (
      <>
        <section className={styles.section} aria-label={t("admin.bulk.filter_panel")}>
          <TrainerFilterPanel filters={filters} onToggle={toggleFilter} />
        </section>

        <section className={styles.section} aria-label="Matched trainers">
          <TrainerMatchTable trainers={matchedTrainers} isLoading={filterQuery.isFetching} />
        </section>

        <section className={styles.section} aria-label="Assignment form">
          <AssignmentForm
            projectId={projectIdInput}
            onProjectIdChange={(v) => {
              setProjectIdInput(v);
              setResultBanner(null);
            }}
            tasksPerTrainer={tasksPerTrainer}
            onTasksPerTrainerChange={setTasksPerTrainer}
            strategy={strategy}
            onStrategyChange={setStrategy}
            matchedCount={matchedTrainers.length}
            onSubmit={() => {
              setResultBanner(null);
              submitMutation.mutate();
            }}
            isSubmitting={submitMutation.isPending}
            canSubmit={canSubmit}
          />
          {resultBanner ? (
            <div
              className={
                resultBanner.kind === "success" ? styles.successBanner : styles.errorBanner
              }
              data-testid={`bulk-banner-${resultBanner.kind}`}
            >
              {resultBanner.text}
            </div>
          ) : null}
        </section>
      </>
    );
  })();

  return (
    <main className={`p-6 ${styles.bulkRoot}`} data-testid="admin-bulk-assign">
      <RoleGate
        allow={["admin"]}
        userRole={user?.role}
        fallback={
          <div className={styles.errorBox} data-testid="bulk-forbidden">
            403 — admin only
          </div>
        }
      >
        <header className={styles.bulkHeader}>
          <div>
            <h1 className={styles.bulkTitle}>{t("admin.bulk.title")}</h1>
            <div className={styles.bulkSubtitle}>Bulk task assign</div>
          </div>
        </header>
        {body}
        <AssignmentResultDrawer
          open={drawerOpen}
          result={assignmentResult}
          onClose={() => setDrawerOpen(false)}
        />
      </RoleGate>
    </main>
  );
};

BulkAssignPage.title = "Bulk Task Assign";
BulkAssignPage.path = "/admin/bulk-assign";
BulkAssignPage.exact = true;

export default BulkAssignPage;
