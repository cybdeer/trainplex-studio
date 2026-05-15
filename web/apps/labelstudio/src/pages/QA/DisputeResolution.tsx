/**
 * DisputeResolution — TrainPlex three-way comparison + QA verdict form.
 *
 * Phase 1 Step 6. Route: /qa/disputes/:dispute_id. RoleGate `['qa_lead']`.
 *
 * Layout
 * ------
 *   ┌───────────────────────────────────────────────────────────┐
 *   │ Three-way comparison                                       │
 *   ├─────────────┬─────────────┬─────────────────────────────────┤
 *   │ Task body   │ Trainer ans │ 3 reviewers' verdicts          │
 *   ├─────────────┴─────────────┴─────────────────────────────────┤
 *   │ QA decision form:                                          │
 *   │   ○ Trainer correct                                        │
 *   │   ○ Reviewer majority correct                              │
 *   │   ○ Send to ML re-check                                    │
 *   │   ○ Inconclusive                                           │
 *   │   [ QA notes textarea ]                                    │
 *   │   [ Resolve dispute ]                                      │
 *   └───────────────────────────────────────────────────────────┘
 *
 * Mock-vs-real
 * ------------
 * Task body + trainer answer + per-reviewer comments are not yet wired —
 * Step 8 hooks them up to the existing LS tasks API. Phase 1 ships the
 * resolution flow against a stub task panel so the QA lead can exercise
 * the full submit round-trip end-to-end.
 */

import { Button, ConsensusBadge, RoleGate, Spinner } from "@humansignal/ui";
import { useTranslation } from "@humansignal/app-common";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useAuth } from "@humansignal/core/providers/AuthProvider";
import { useAPI } from "../../providers/ApiProvider";
import type { Page } from "../types/Page";
import type {
  DisputeListResponse,
  DisputeResolution as DisputeResolutionEnum,
  DisputeResolveBody,
  DisputeRow,
} from "./types";
import styles from "./QA.module.css";

const RESOLUTIONS: { value: DisputeResolutionEnum; labelKey: string; testId: string }[] = [
  { value: "trainer_correct", labelKey: "qa.disputes.decision_trainer", testId: "qa-decision-trainer" },
  { value: "reviewer_correct", labelKey: "qa.disputes.decision_reviewer", testId: "qa-decision-reviewer" },
  { value: "ml_recheck", labelKey: "qa.disputes.decision_ml_recheck", testId: "qa-decision-ml-recheck" },
  { value: "inconclusive", labelKey: "qa.disputes.decision_inconclusive", testId: "qa-decision-inconclusive" },
];

export const DisputeResolution: Page = () => {
  const api = useAPI();
  const { t } = useTranslation();
  const { user } = useAuth();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { dispute_id } = useParams<{ dispute_id: string }>();
  const disputeId = Number(dispute_id);

  const [resolution, setResolution] = useState<DisputeResolutionEnum | null>(null);
  const [qaNotes, setQaNotes] = useState("");
  const [errorBanner, setErrorBanner] = useState<string | null>(null);
  const [successBanner, setSuccessBanner] = useState<string | null>(null);

  // Phase 1 lookup: fetch the open list (status=all) and find the row by id.
  // Step 8 will swap this for a dedicated GET /qa/disputes/:id endpoint.
  const listQuery = useQuery<DisputeListResponse>({
    queryKey: ["qa-disputes", { page: 1, page_size: 200, status: "all" }],
    queryFn: async () => {
      const res = await api.callApi("qaDisputes", {
        params: { page: 1, page_size: 200, status: "all" },
      });
      return res as DisputeListResponse;
    },
    enabled: user?.role === "qa_lead" && !Number.isNaN(disputeId),
  });

  const dispute: DisputeRow | undefined = useMemo(() => {
    if (!listQuery.data) return undefined;
    return listQuery.data.results.find((d) => d.id === disputeId);
  }, [listQuery.data, disputeId]);

  const resolveMutation = useMutation<
    { ok: boolean; dispute?: DisputeRow; error?: string } | undefined,
    Error,
    DisputeResolveBody
  >({
    mutationFn: async (body) => {
      const res = (await api.callApi("qaDisputeResolve", {
        params: { dispute_id: disputeId },
        body,
      })) as { ok: boolean; dispute?: DisputeRow; error?: string } | undefined;
      return res;
    },
    onSuccess: (res) => {
      if (!res?.ok) {
        setErrorBanner(res?.error || t("qa.disputes.resolve_failed"));
        return;
      }
      setSuccessBanner(t("qa.disputes.resolve_success"));
      setErrorBanner(null);
      queryClient.invalidateQueries({ queryKey: ["qa-disputes"] });
      window.setTimeout(() => navigate("/qa/disputes"), 800);
    },
    onError: (err) => {
      setErrorBanner(err?.message || t("qa.disputes.resolve_failed"));
    },
  });

  const handleResolve = () => {
    setErrorBanner(null);
    if (!resolution) {
      setErrorBanner(t("qa.disputes.resolution_required"));
      return;
    }
    resolveMutation.mutate({
      resolution,
      qa_notes: qaNotes,
    });
  };

  return (
    <main className={`p-6 ${styles.qaRoot}`} data-testid="qa-dispute-detail">
      <RoleGate
        allow={["qa_lead"]}
        userRole={user?.role}
        fallback={
          <div className={styles.errorBox} data-testid="qa-dispute-forbidden">
            403 — QA lead only
          </div>
        }
      >
        <header className={styles.header}>
          <h1 className={styles.title}>
            {t("qa.disputes.three_way")} #{disputeId}
          </h1>
        </header>

        {listQuery.isFetching && !listQuery.data ? (
          <div className={styles.loadingBox} role="status" aria-live="polite">
            <Spinner />
            <span>{t("qa.disputes.loading")}</span>
          </div>
        ) : !dispute ? (
          <div className={styles.errorBox} data-testid="qa-dispute-missing">
            {t("qa.disputes.not_found")}
          </div>
        ) : (
          <>
            <section className={styles.threeWay} aria-label={t("qa.disputes.three_way")}>
              <div className={styles.panel} data-testid="qa-dispute-task-panel">
                <h2 className={styles.sectionHeading}>{t("qa.disputes.task_heading")}</h2>
                <div className={styles.metaLine}>
                  {t("qa.disputes.task_id_label")}: #{dispute.task_id}
                </div>
                <div className={styles.metaLine}>
                  {t("qa.disputes.escalated_label")}: {dispute.escalated_at}
                </div>
                <p className={styles.placeholderText}>
                  {t("qa.disputes.task_placeholder")}
                </p>
              </div>
              <div className={styles.panel} data-testid="qa-dispute-trainer-panel">
                <h2 className={styles.sectionHeading}>{t("qa.disputes.trainer_heading")}</h2>
                <p className={styles.placeholderText}>
                  {t("qa.disputes.trainer_placeholder")}
                </p>
              </div>
              <div className={styles.panel} data-testid="qa-dispute-reviewers-panel">
                <h2 className={styles.sectionHeading}>{t("qa.disputes.reviewers_heading")}</h2>
                <div className={styles.reviewerSummaryRow}>
                  <ConsensusBadge
                    status={dispute.consensus_status}
                    agreedCount={dispute.agreed_count}
                    totalReviewers={dispute.total_reviewers}
                    testId="qa-dispute-consensus-badge"
                  />
                  <span className={styles.metaLine}>
                    {t("qa.disputes.agreed_label", {
                      agreed: dispute.agreed_count,
                      total: dispute.total_reviewers,
                    })}
                  </span>
                </div>
                <p className={styles.placeholderText}>
                  {t("qa.disputes.reviewers_placeholder")}
                </p>
              </div>
            </section>

            <section className={styles.resolutionForm} aria-label={t("qa.disputes.form_heading")}>
              <h2 className={styles.sectionHeading}>{t("qa.disputes.form_heading")}</h2>

              {successBanner ? (
                <div className={styles.successBox} data-testid="qa-dispute-success">
                  {successBanner}
                </div>
              ) : null}
              {errorBanner ? (
                <div className={styles.errorBox} data-testid="qa-dispute-error">
                  {errorBanner}
                </div>
              ) : null}

              {dispute.resolved_at ? (
                <div className={styles.statusResolved} data-testid="qa-dispute-already-resolved">
                  {t("qa.disputes.already_resolved", { at: dispute.resolved_at })}
                </div>
              ) : (
                <>
                  <fieldset className={styles.fieldset}>
                    <legend className={styles.legend}>{t("qa.disputes.decision_label")}</legend>
                    <div className={styles.decisionList} role="radiogroup">
                      {RESOLUTIONS.map((opt) => (
                        <label
                          key={opt.value}
                          className={
                            resolution === opt.value
                              ? styles.decisionChipActive
                              : styles.decisionChip
                          }
                          data-testid={opt.testId}
                        >
                          <input
                            type="radio"
                            name="resolution"
                            value={opt.value}
                            checked={resolution === opt.value}
                            onChange={() => setResolution(opt.value)}
                            className={styles.srOnly}
                          />
                          {t(opt.labelKey)}
                        </label>
                      ))}
                    </div>
                  </fieldset>

                  <label className={styles.notesLabel}>
                    {t("qa.disputes.notes_label")}
                    <textarea
                      className={styles.notesInput}
                      rows={4}
                      data-testid="qa-dispute-notes"
                      value={qaNotes}
                      onChange={(e) => setQaNotes(e.target.value)}
                    />
                  </label>

                  <Button
                    look="filled"
                    size="medium"
                    className={styles.ctaPrimary}
                    data-testid="qa-dispute-resolve"
                    disabled={resolveMutation.isPending}
                    onClick={handleResolve}
                  >
                    {resolveMutation.isPending
                      ? t("qa.disputes.resolving")
                      : t("qa.disputes.resolve_button")}
                  </Button>
                </>
              )}
            </section>
          </>
        )}
      </RoleGate>
    </main>
  );
};

DisputeResolution.title = "Resolve Dispute";
DisputeResolution.path = "/qa/disputes/:dispute_id";
DisputeResolution.exact = true;

export default DisputeResolution;
