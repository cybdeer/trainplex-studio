/**
 * ReviewerScoreBadges — 3-dot consensus visualisation.
 *
 * Phase 1 Step 4.2-9. Pure presentational: renders one dot per reviewer
 * (always exactly 3), green for agreed, red for disagreed. Reads at a
 * glance so admin can scan a list of 10 submissions and see which need
 * a closer look (any row with red dots).
 *
 * The dot list is accompanied by a short "agreed/disagreed" summary
 * label so the visualisation is also accessible to screen readers and
 * to users who can't distinguish red/green.
 */

import { useTranslation } from "@humansignal/app-common";
import type { ReviewerScore } from "./types";
import styles from "./SubmissionsPreview.module.css";

export interface ReviewerScoreBadgesProps {
  /** Always 3 entries — backend guarantees this. */
  scores: ReviewerScore[];
  /** Optional test-id suffix so callers can target a specific row's badges. */
  testIdSuffix?: string;
}

export function ReviewerScoreBadges({
  scores,
  testIdSuffix,
}: ReviewerScoreBadgesProps) {
  const { t } = useTranslation();

  // Defensive: pad to length 3 in case a malformed payload sneaks through.
  // We don't want a single weird row to crash the whole drawer.
  const padded: ReviewerScore[] = [...scores];
  while (padded.length < 3) {
    padded.push({ reviewer_id: -1, score: 0, agreed: false });
  }
  const trimmed = padded.slice(0, 3);

  const agreedCount = trimmed.filter((s) => s.agreed).length;
  const totalCount = trimmed.length;

  const suffix = testIdSuffix ? `-${testIdSuffix}` : "";

  return (
    <span
      className={styles.scoreDotsWrap}
      data-testid={`reviewer-score-badges${suffix}`}
      data-agreed-count={agreedCount}
      role="img"
      aria-label={
        agreedCount === totalCount
          ? t("admin.submissions.score_agreed")
          : agreedCount === 0
            ? t("admin.submissions.score_disagreed")
            : `${agreedCount} / ${totalCount}`
      }
    >
      {trimmed.map((s, idx) => (
        <span
          key={`${s.reviewer_id}-${idx}`}
          data-testid={`reviewer-score-dot${suffix}-${idx}`}
          data-agreed={String(s.agreed)}
          className={`${styles.scoreDot} ${
            s.agreed ? styles.scoreDotAgreed : styles.scoreDotDisagreed
          }`}
          title={
            s.agreed
              ? t("admin.submissions.score_agreed")
              : t("admin.submissions.score_disagreed")
          }
        />
      ))}
      <span className={styles.scoreSummary} data-testid={`reviewer-score-summary${suffix}`}>
        {agreedCount}/{totalCount}
      </span>
    </span>
  );
}

export default ReviewerScoreBadges;
