/**
 * ProgressStepper — top-of-wizard 1 → 2 → 3 progress indicator.
 *
 * Phase 1 Step 4.2-2. Renders three labeled dots connected by a track. The
 * active step glows TrainPlex Indigo; completed steps fill in solid; future
 * steps stay greyed out. Click-back on a completed step is allowed so the
 * founder can revise an earlier choice.
 */

import styles from "./ProjectWizard.module.css";

export interface ProgressStepperProps {
  /** Current step (1, 2, or 3). */
  current: 1 | 2 | 3;
  /** Labels for steps 1, 2, 3 — already translated. */
  labels: [string, string, string];
  /** Optional callback when user clicks a completed step. */
  onStepClick?: (step: 1 | 2 | 3) => void;
}

export function ProgressStepper({ current, labels, onStepClick }: ProgressStepperProps) {
  const steps: Array<1 | 2 | 3> = [1, 2, 3];
  return (
    <nav className={styles.stepper} aria-label="Wizard progress" data-testid="wizard-stepper">
      {steps.map((s, idx) => {
        const state =
          s < current ? "complete" : s === current ? "active" : "pending";
        const clickable = state === "complete" && onStepClick != null;
        const dotClass = [
          styles.stepperDot,
          state === "active" ? styles.stepperDotActive : "",
          state === "complete" ? styles.stepperDotComplete : "",
        ].join(" ");
        return (
          <div key={s} className={styles.stepperItem}>
            <button
              type="button"
              className={dotClass}
              data-testid={`stepper-dot-${s}`}
              data-state={state}
              disabled={!clickable}
              aria-current={state === "active" ? "step" : undefined}
              onClick={() => clickable && onStepClick?.(s)}
            >
              {state === "complete" ? "✓" : s}
            </button>
            <span className={styles.stepperLabel} data-testid={`stepper-label-${s}`}>
              {labels[s - 1]}
            </span>
            {idx < steps.length - 1 ? (
              <span
                className={`${styles.stepperTrack} ${s < current ? styles.stepperTrackDone : ""}`}
                aria-hidden="true"
              />
            ) : null}
          </div>
        );
      })}
    </nav>
  );
}

export default ProgressStepper;
