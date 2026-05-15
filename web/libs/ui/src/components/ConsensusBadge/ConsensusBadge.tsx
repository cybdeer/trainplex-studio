/**
 * ConsensusBadge — 3-dot indicator for a peer-review consensus result.
 *
 * TrainPlex Phase 1 Step 6.
 *
 * Visual
 * ------
 *   ● ● ●    3/3 agree  → all green   ("approved")
 *   ● ● ○    2/3 agree  → 2 green, 1 red   ("flagged")
 *   ● ○ ○    1/3 agree  → 1 green, 2 red   ("dispute")
 *   ○ ○ ○    0/3 agree  → all red          ("rejected")
 *   ○ ○ ○    pending (no count) → all grey
 *
 * Colour values match the founder palette (Indigo primary, Vermilion danger,
 * Saffron warning isn't used here — flagged shows mixed dots not a single
 * orange). Each dot is keyboard-focusable for screen readers so the user
 * can hear "Agreed 2 of 3" via the aria-label.
 *
 * Phase 1 status
 * --------------
 * Presentational only. Status string is computed by the
 * consensus_engine.compute_consensus backend service and passed in as a
 * prop — the component never decides on its own.
 */

import type { CSSProperties } from "react";

export type ConsensusStatus =
  | "approved"
  | "flagged"
  | "dispute"
  | "rejected"
  | "pending";

export interface ConsensusBadgeProps {
  /** Status string from ConsensusResult.status. */
  status?: ConsensusStatus | string | null;
  /** Number of agreed reviewers (drives dot fill). 0..total. */
  agreedCount?: number;
  /** Total reviewers expected (defaults to 3). */
  totalReviewers?: number;
  /** Optional override aria-label; auto-generated otherwise. */
  ariaLabel?: string;
  /** Extra className for layout (margins etc). */
  className?: string;
  /** Pin a data-testid for test harness queries. */
  testId?: string;
}

const COLOUR_AGREE = "#2BB673"; // founder palette — Green
const COLOUR_DISAGREE = "#E54848"; // founder palette — Vermilion
const COLOUR_PENDING = "#C7C9D9"; // founder palette — light grey

function dotColour(status: string | null | undefined, dotIndex: number, agreedCount: number) {
  if (status === "pending" || status == null || status === "") return COLOUR_PENDING;
  // approved → all green.
  if (status === "approved") return COLOUR_AGREE;
  // rejected → all red.
  if (status === "rejected") return COLOUR_DISAGREE;
  // Mixed states — fill `agreedCount` dots from the left with green.
  return dotIndex < agreedCount ? COLOUR_AGREE : COLOUR_DISAGREE;
}

const DOT_STYLE: CSSProperties = {
  display: "inline-block",
  width: 10,
  height: 10,
  borderRadius: "50%",
  marginRight: 4,
};

export function ConsensusBadge({
  status,
  agreedCount = 0,
  totalReviewers = 3,
  ariaLabel,
  className,
  testId = "consensus-badge",
}: ConsensusBadgeProps) {
  const total = Math.max(1, totalReviewers);
  const agreed = Math.min(Math.max(agreedCount, 0), total);
  const label =
    ariaLabel ?? `Agreed ${agreed} of ${total} (${status ?? "pending"})`;

  return (
    <span
      className={className}
      data-testid={testId}
      role="img"
      aria-label={label}
      title={label}
      style={{ display: "inline-flex", alignItems: "center" }}
    >
      {Array.from({ length: total }).map((_, i) => (
        <span
          key={i}
          data-testid={`${testId}-dot-${i}`}
          style={{
            ...DOT_STYLE,
            backgroundColor: dotColour(status ?? null, i, agreed),
          }}
        />
      ))}
    </span>
  );
}

export default ConsensusBadge;
