/**
 * ReviewSplitScreen — TrainPlex peer-review split-pane form.
 *
 * Phase 1 Step 6. Left pane: task + trainer answer (blind — no submitter
 * name shown). Right pane: review form with 1-5 rating, agree/partial/
 * disagree/dispute, optional category checks + comment.
 *
 * Route: /reviewer/review/:task_id
 *
 * Wiring
 * ------
 * The route param is the *task_id* (not the assignment id) because the
 * queue page links via the human-readable "#123" submission identifier.
 * On mount we pull the reviewer's queue and find the matching assignment
 * for this task id. Submission POSTs `/api/v1/reviewer/submit-review` with
 * the assignment id resolved client-side.
 *
 * Mock-vs-real
 * ------------
 * The task content + trainer answer pane is a *placeholder* in Phase 1 —
 * the real task / answer payload comes from the existing LS tasks API and
 * is wired in Step 8. The peer-review FE in Phase 1 ships the form +
 * submit flow; the task body block reads "Task #<id>" with a stub so the
 * reviewer can exercise the full submit-review round-trip end-to-end.
 */

import { Button, RoleGate, Spinner } from "@humansignal/ui";
import { useTranslation } from "@humansignal/app-common";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useAuth } from "@humansignal/core/providers/AuthProvider";
import { useAPI } from "../../providers/ApiProvider";
import type { Page } from "../types/Page";
import type {
  ReviewAgreement,
  ReviewerAssignmentRow,
  ReviewerQueueResponse,
  SubmitReviewResponse,
} from "./types";
import styles from "./Reviewer.module.css";

const AGREEMENT_OPTIONS: { value: ReviewAgreement; labelKey: string; testId: string }[] = [
  { value: "agree", labelKey: "reviewer.review.agree", testId: "review-agreement-agree" },
  { value: "partial", labelKey: "reviewer.review.partial", testId: "review-agreement-partial" },
  { value: "disagree", labelKey: "reviewer.review.disagree", testId: "review-agreement-disagree" },
  { value: "dispute", labelKey: "reviewer.review.dispute", testId: "review-agreement-dispute" },
];

// The category-check list is intentionally stubby in Phase 1; Step 8 will
// fetch it from the project config (per-template category schema).
const CATEGORY_CHECKS: { key: string; labelKey: string }[] = [
  { key: "grammar", labelKey: "reviewer.review.cat_grammar" },
  { key: "factual", labelKey: "reviewer.review.cat_factual" },
  { key: "language_pure", labelKey: "reviewer.review.cat_language_pure" },
];

interface FormState {
  score: number;
  agreement: ReviewAgreement | null;
  comment: string;
  categoryChecks: Record<string, boolean>;
}

const INITIAL_FORM: FormState = {
  score: 3,
  agreement: null,
  comment: "",
  categoryChecks: {},
};

export const ReviewSplitScreen: Page = () => {
  const api = useAPI();
  const { t } = useTranslation();
  const { user } = useAuth();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { task_id: taskIdParam } = useParams<{ task_id: string }>();
  const taskId = Number(taskIdParam);

  const [form, setForm] = useState<FormState>(INITIAL_FORM);
  const [errorBanner, setErrorBanner] = useState<string | null>(null);
  const [successBanner, setSuccessBanner] = useState<string | null>(null);

  // Pull the reviewer's open queue once to resolve task_id → assignment_id.
  // We use page_size 200 so a busy reviewer doesn't need pagination just to
  // find the assignment they clicked into.
  const queueQuery = useQuery<ReviewerQueueResponse>({
    queryKey: ["reviewer-queue", { page: 1, page_size: 200, status: "open" }],
    queryFn: async () => {
      const res = await api.callApi("reviewerQueue", {
        params: { page: 1, page_size: 200, status: "open" },
      });
      return res as ReviewerQueueResponse;
    },
    enabled: user?.role === "reviewer" && !Number.isNaN(taskId),
  });

  const assignment: ReviewerAssignmentRow | undefined = useMemo(() => {
    if (!queueQuery.data) return undefined;
    return queueQuery.data.results.find((r) => r.task_id === taskId);
  }, [queueQuery.data, taskId]);

  const submitMutation = useMutation<
    SubmitReviewResponse,
    Error,
    { assignmentId: number; form: FormState }
  >({
    mutationFn: async ({ assignmentId, form: f }) => {
      const res = (await api.callApi("reviewerSubmitReview", {
        body: {
          review_assignment_id: assignmentId,
          score: f.score,
          agreement: f.agreement,
          comment: f.comment,
          category_checks: f.categoryChecks,
        },
      })) as SubmitReviewResponse;
      return res;
    },
    onSuccess: (res) => {
      if (!res?.ok) {
        setErrorBanner(res?.error || t("reviewer.review.submit_failed"));
        return;
      }
      setSuccessBanner(t("reviewer.review.submit_success"));
      setErrorBanner(null);
      // Invalidate the queue head so the dashboard badge updates.
      queryClient.invalidateQueries({ queryKey: ["reviewer-queue-head"] });
      queryClient.invalidateQueries({ queryKey: ["reviewer-queue"] });
      // Push back to queue after a short beat so the success banner reads.
      window.setTimeout(() => navigate("/reviewer/queue"), 800);
    },
    onError: (err) => {
      setErrorBanner(err?.message || t("reviewer.review.submit_failed"));
    },
  });

  useEffect(() => {
    // Reset success banner whenever the user picks a different task.
    setSuccessBanner(null);
    setErrorBanner(null);
    setForm(INITIAL_FORM);
  }, [taskId]);

  const handleSubmit = () => {
    setErrorBanner(null);
    if (!assignment) {
      setErrorBanner(t("reviewer.review.no_assignment"));
      return;
    }
    if (!form.agreement) {
      setErrorBanner(t("reviewer.review.agreement_required"));
      return;
    }
    submitMutation.mutate({ assignmentId: assignment.id, form });
  };

  return (
    <main className={`p-6 ${styles.reviewerRoot}`} data-testid="reviewer-review">
      <RoleGate
        allow={["reviewer"]}
        userRole={user?.role}
        fallback={
          <div className={styles.errorBox} data-testid="reviewer-review-forbidden">
            403 — reviewer only
          </div>
        }
      >
        <header className={styles.header}>
          <h1 className={styles.title}>
            {t("reviewer.review.title")} #{taskId}
          </h1>
        </header>

        {queueQuery.isFetching && !queueQuery.data ? (
          <div className={styles.loadingBox} role="status" aria-live="polite">
            <Spinner />
            <span>{t("reviewer.review.loading")}</span>
          </div>
        ) : !assignment ? (
          <div className={styles.errorBox} data-testid="reviewer-review-missing">
            {t("reviewer.review.no_assignment")}
          </div>
        ) : (
          <div className={styles.splitPane} data-testid="reviewer-review-split">
            {/* Left: task + trainer answer (blind) */}
            <section className={styles.leftPane} aria-label={t("reviewer.review.left_label")}>
              <h2 className={styles.sectionHeading}>
                {t("reviewer.review.task_heading")}
              </h2>
              {/* Phase 1 stub — real task payload wiring lands Step 8. */}
              <div className={styles.taskCard} data-testid="reviewer-review-task-card">
                <div className={styles.metaLine}>
                  {t("reviewer.review.task_id_label")}: #{assignment.task_id}
                </div>
                <div className={styles.metaLine}>
                  {t("reviewer.review.assigned_label")}: {assignment.assigned_at}
                </div>
                <div className={styles.metaLine}>
                  {t("reviewer.review.deadline_label")}: {assignment.deadline_at}
                </div>
                <p className={styles.placeholderText}>
                  {t("reviewer.review.task_placeholder")}
                </p>
              </div>
              <h3 className={styles.sectionHeading}>
                {t("reviewer.review.answer_heading")}
              </h3>
              <div className={styles.answerCard} data-testid="reviewer-review-answer-card">
                <p className={styles.placeholderText}>
                  {t("reviewer.review.answer_placeholder")}
                </p>
              </div>
            </section>

            {/* Right: review form */}
            <section className={styles.rightPane} aria-label={t("reviewer.review.right_label")}>
              <h2 className={styles.sectionHeading}>{t("reviewer.review.form_heading")}</h2>

              {successBanner ? (
                <div className={styles.successBox} data-testid="reviewer-review-success">
                  {successBanner}
                </div>
              ) : null}
              {errorBanner ? (
                <div className={styles.errorBox} data-testid="reviewer-review-error">
                  {errorBanner}
                </div>
              ) : null}

              <fieldset className={styles.fieldset}>
                <legend className={styles.legend}>{t("reviewer.review.rating")}</legend>
                <div className={styles.ratingRow} role="radiogroup" aria-label={t("reviewer.review.rating")}>
                  {[1, 2, 3, 4, 5].map((n) => (
                    <button
                      type="button"
                      key={n}
                      data-testid={`review-score-${n}`}
                      onClick={() => setForm((f) => ({ ...f, score: n }))}
                      aria-pressed={form.score === n}
                      className={form.score === n ? styles.ratingButtonActive : styles.ratingButton}
                    >
                      {n}
                    </button>
                  ))}
                </div>
              </fieldset>

              <fieldset className={styles.fieldset}>
                <legend className={styles.legend}>{t("reviewer.review.agreement_label")}</legend>
                <div className={styles.agreementRow}>
                  {AGREEMENT_OPTIONS.map((opt) => (
                    <label
                      key={opt.value}
                      className={form.agreement === opt.value ? styles.agreementChipActive : styles.agreementChip}
                      data-testid={opt.testId}
                    >
                      <input
                        type="radio"
                        name="agreement"
                        value={opt.value}
                        checked={form.agreement === opt.value}
                        onChange={() => setForm((f) => ({ ...f, agreement: opt.value }))}
                        className={styles.srOnly}
                      />
                      {t(opt.labelKey)}
                    </label>
                  ))}
                </div>
              </fieldset>

              <fieldset className={styles.fieldset}>
                <legend className={styles.legend}>{t("reviewer.review.categories_label")}</legend>
                <div className={styles.categoryGrid}>
                  {CATEGORY_CHECKS.map((cat) => (
                    <label key={cat.key} className={styles.categoryRow}>
                      <input
                        type="checkbox"
                        data-testid={`review-cat-${cat.key}`}
                        checked={Boolean(form.categoryChecks[cat.key])}
                        onChange={(e) =>
                          setForm((f) => ({
                            ...f,
                            categoryChecks: {
                              ...f.categoryChecks,
                              [cat.key]: e.target.checked,
                            },
                          }))
                        }
                      />
                      {t(cat.labelKey)}
                    </label>
                  ))}
                </div>
              </fieldset>

              <label className={styles.commentLabel}>
                {t("reviewer.review.comment_label")}
                <textarea
                  className={styles.commentInput}
                  rows={4}
                  data-testid="review-comment"
                  value={form.comment}
                  onChange={(e) => setForm((f) => ({ ...f, comment: e.target.value }))}
                />
              </label>

              <Button
                look="filled"
                size="medium"
                className={styles.ctaPrimary}
                data-testid="review-submit"
                disabled={submitMutation.isPending}
                onClick={handleSubmit}
              >
                {submitMutation.isPending
                  ? t("reviewer.review.submitting")
                  : t("reviewer.review.submit_button")}
              </Button>
            </section>
          </div>
        )}
      </RoleGate>
    </main>
  );
};

ReviewSplitScreen.title = "Review Task";
ReviewSplitScreen.path = "/reviewer/review/:task_id";
ReviewSplitScreen.exact = true;

export default ReviewSplitScreen;
