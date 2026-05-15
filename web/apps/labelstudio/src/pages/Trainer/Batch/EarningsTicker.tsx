/**
 * EarningsTicker — sticky bottom bar showing running earnings + progress.
 *
 * Per plan: "sticky earnings ticker" — bottom-pinned, animated rupee
 * counter, one dot per task showing pending / in_progress / done.
 *
 * The counter animates from its previous value to the new value over
 * ~300ms whenever the parent re-renders with a higher earnings number.
 * We use a CSS-only pulse on the in-progress dot so the bar stays alive
 * even when no task is being completed (founder rule: trainer must
 * always feel motion).
 *
 * Phase 1 Step 1.4-E.
 */

import { useEffect, useState } from "react";
import { useTranslation } from "@humansignal/app-common";
import type { BatchTask } from "./types";
import styles from "./Batch.module.css";

export interface EarningsTickerProps {
  batch: BatchTask[];
}

/** Run a short ease-out animation between two integer values. */
function useAnimatedNumber(target: number, durationMs = 300): number {
  const [value, setValue] = useState(target);
  useEffect(() => {
    if (target === value) return;
    const start = value;
    const delta = target - start;
    const startedAt = performance.now();
    let raf = 0;
    const tick = (now: number) => {
      const elapsed = now - startedAt;
      const t = Math.min(1, elapsed / durationMs);
      // Ease-out cubic.
      const eased = 1 - Math.pow(1 - t, 3);
      setValue(Math.round(start + delta * eased));
      if (t < 1) {
        raf = requestAnimationFrame(tick);
      }
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [target, durationMs]);
  return value;
}

export function EarningsTicker({ batch }: EarningsTickerProps) {
  const { t } = useTranslation();

  const earningsDone = batch
    .filter((b) => b.status === "done")
    .reduce((sum, b) => sum + b.earnings_inr, 0);

  const totalEarnings = batch.reduce((sum, b) => sum + b.earnings_inr, 0);
  const doneCount = batch.filter((b) => b.status === "done").length;
  const totalCount = batch.length;

  const animated = useAnimatedNumber(earningsDone);

  return (
    <aside
      className={styles.ticker}
      role="status"
      aria-live="polite"
      data-testid="earnings-ticker"
    >
      <div>
        <div className={styles.tickerLabel}>
          {t("trainer.batch.earnings_so_far")}
        </div>
        <div className={styles.tickerEarnings} data-testid="ticker-earnings">
          ₹{animated} <span style={{ opacity: 0.6, fontWeight: 500 }}>/ ₹{totalEarnings}</span>
        </div>
      </div>
      <div
        className={styles.progressDots}
        data-testid="ticker-progress-dots"
        aria-label={t("trainer.batch.progress", { done: doneCount, total: totalCount })}
      >
        {batch.map((task, idx) => {
          const dotClass =
            task.status === "done"
              ? `${styles.progressDot} ${styles.progressDotDone}`
              : task.status === "in_progress"
                ? `${styles.progressDot} ${styles.progressDotInProgress}`
                : styles.progressDot;
          return (
            <span
              key={task.task_id ?? idx}
              className={dotClass}
              data-testid={`progress-dot-${idx}`}
              data-status={task.status}
            />
          );
        })}
      </div>
      <div className={styles.tickerLabel}>
        {t("trainer.batch.progress", { done: doneCount, total: totalCount })}
      </div>
    </aside>
  );
}
