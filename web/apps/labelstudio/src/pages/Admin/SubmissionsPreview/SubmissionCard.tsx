/**
 * SubmissionCard — one submission's preview block inside the drawer.
 *
 * Phase 1 Step 4.2-9. Pure presentational. Renders:
 *
 *   ┌──────────┬──────────────────────────────────────────┐
 *   │          │ Trainer name (role)       2026-05-15 13:21│
 *   │ [image]  │ ─────────────────────────────────────────│
 *   │   or     │ ANSWER                                    │
 *   │  text    │ {"first_name":"Geeta", ...}               │
 *   │ snippet  │ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ │
 *   │          │ REVIEWER SCORES  • • •   2/3   [Status]   │
 *   └──────────┴──────────────────────────────────────────┘
 *
 * Task preview is detected by URL prefix — `http(s)://` → render as
 * <img>; everything else → render as a clamped text snippet. Keeps the
 * component flexible for image / OCR / language / audio tasks alike.
 */

import { useTranslation } from "@humansignal/app-common";
import { ReviewerScoreBadges } from "./ReviewerScoreBadges";
import type { SubmissionPreview, SubmissionStatus } from "./types";
import styles from "./SubmissionsPreview.module.css";

export interface SubmissionCardProps {
  submission: SubmissionPreview;
}

/** Map status enum → CSS-module class + i18n key. */
const STATUS_CLASS_KEY: Record<
  SubmissionStatus,
  { cls: string; labelKey: string }
> = {
  submitted: { cls: styles.statusSubmitted, labelKey: "admin.submissions.status_submitted" },
  under_review: {
    cls: styles.statusUnderReview,
    labelKey: "admin.submissions.status_under_review",
  },
  approved: { cls: styles.statusApproved, labelKey: "admin.submissions.status_approved" },
  rejected: { cls: styles.statusRejected, labelKey: "admin.submissions.status_rejected" },
};

/**
 * `task_preview` is an HTTP(S) URL when starts with `http://` or `https://`.
 * Anything else is treated as a text snippet.
 */
function isImageUrl(taskPreview: string): boolean {
  return /^https?:\/\//i.test(taskPreview);
}

/** Format an ISO timestamp into a locale-aware short display string. */
function formatWhen(locale: string, isoTimestamp: string): string {
  try {
    const d = new Date(isoTimestamp);
    if (Number.isNaN(d.getTime())) return isoTimestamp;
    return d.toLocaleString(locale === "hi" ? "hi-IN" : "en-IN", {
      month: "short",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return isoTimestamp;
  }
}

export function SubmissionCard({ submission }: SubmissionCardProps) {
  const { t, i18n } = useTranslation();
  const locale = i18n.language || "en";

  const statusMeta = STATUS_CLASS_KEY[submission.status] ?? STATUS_CLASS_KEY.submitted;

  return (
    <article
      className={styles.submissionCard}
      data-testid={`submission-card-${submission.id}`}
      aria-label={`Submission #${submission.id}`}
    >
      {/* Task preview pane — image OR text snippet */}
      <div className={styles.taskPane}>
        {isImageUrl(submission.task_preview) ? (
          <img
            src={submission.task_preview}
            alt={t("admin.submissions.col_task")}
            className={styles.taskThumb}
            data-testid={`submission-task-thumb-${submission.id}`}
            loading="lazy"
            referrerPolicy="no-referrer"
          />
        ) : (
          <div
            className={styles.taskTextSnippet}
            data-testid={`submission-task-text-${submission.id}`}
          >
            {submission.task_preview}
          </div>
        )}
      </div>

      {/* Trainer + answer + reviewer scores pane */}
      <div className={styles.contentPane}>
        <div className={styles.cardHeaderRow}>
          <span>
            <span
              className={styles.trainerName}
              data-testid={`submission-trainer-${submission.id}`}
            >
              {submission.trainer.name}
            </span>
            {submission.trainer.role ? (
              <span className={styles.trainerRole}>{submission.trainer.role}</span>
            ) : null}
          </span>
          <span className={styles.cardWhen}>
            {formatWhen(locale, submission.created_at)}
          </span>
        </div>

        <div>
          <div className={styles.answerLabel}>{t("admin.submissions.col_answer")}</div>
          <pre
            className={styles.answerSnippet}
            data-testid={`submission-answer-${submission.id}`}
          >
            {submission.answer_preview}
          </pre>
        </div>

        <div className={styles.scoresRow}>
          <span className={styles.scoresLabel}>
            {t("admin.submissions.col_scores")}
          </span>
          <ReviewerScoreBadges
            scores={submission.reviewer_scores}
            testIdSuffix={String(submission.id)}
          />
          <span
            className={`${styles.statusPill} ${statusMeta.cls}`}
            data-testid={`submission-status-${submission.id}`}
          >
            {t(statusMeta.labelKey)}
          </span>
        </div>
      </div>
    </article>
  );
}

export default SubmissionCard;
