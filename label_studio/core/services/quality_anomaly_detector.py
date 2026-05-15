"""TrainPlex quality / fraud anomaly detector — Phase 1 Step 4.2-8.

Three detection heuristics, all write into the ``htx_quality_alert`` table
so the admin can triage from the React `/admin/quality-alerts` page.

Phase 1 vs Week 5
-----------------
The functions in this module are wired-in MOCK detection — they accept
the detector inputs (time, reviewer results, recent-submission queryset)
as plain arguments rather than reading them from a real peer-review or
certification table. The intention is to lock the *shape* + *thresholds*
in Phase 1 so Week 5 (when peer-review native lands) just needs to call
these functions from the submission completion hook. No schema or API
change is required in Week 5; only a new call site.

The TODO comments below mark the exact call-sites that flip from
"admin-fired test" to "auto-fired from real submission pipeline".
"""

from __future__ import annotations

import hashlib
import json
import logging
from typing import Any, Dict, Iterable, List, Optional

from django.utils import timezone

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Tunable thresholds. Pinned here (not in settings) so changing them is a
# code-review event — these decide who gets flagged for fraud, which is the
# kind of policy that should never silently drift via env var.
# ---------------------------------------------------------------------------

# Time-anomaly thresholds — ratio of actual / expected.
TIME_ANOMALY_MEDIUM_RATIO = 0.3   # < 30 % of expected → medium
TIME_ANOMALY_HIGH_RATIO = 0.1     # < 10 % of expected → high

# Duplicate-pattern threshold — > N identical answers in window = medium flag.
DUPLICATE_PATTERN_THRESHOLD = 5


# ---------------------------------------------------------------------------
# Internal helper — single point that creates the row.
# Kept tiny so each `flag_*` function reads as policy, not plumbing.
# ---------------------------------------------------------------------------


def _create_alert(
    trigger_type: str,
    severity: str,
    *,
    trainer=None,
    submission_id: Optional[int] = None,
    details: Optional[Dict[str, Any]] = None,
):
    """Persist a ``QualityAlert`` row and return it.

    Late-imported so this module is safe to import from tests that haven't
    yet booted Django's app loader.
    """
    from core.models_alerts import QualityAlert

    safe_details = details or {}
    alert = QualityAlert.objects.create(
        trigger_type=trigger_type,
        severity=severity,
        trainer=trainer,
        submission_id=submission_id,
        details=safe_details,
        status=QualityAlert.STATUS_OPEN,
    )
    logger.info(
        'TrainPlex quality alert created: id=%s trigger=%s severity=%s '
        'trainer_id=%s submission_id=%s details=%s',
        alert.id,
        trigger_type,
        severity,
        getattr(trainer, 'id', None),
        submission_id,
        safe_details,
    )
    return alert


# ---------------------------------------------------------------------------
# (1) Time anomaly — trainer submitted suspiciously fast.
# ---------------------------------------------------------------------------


def flag_time_anomaly(
    submission,
    time_taken_sec: float,
    expected_min_sec: float,
    *,
    trainer=None,
):
    """Flag a submission that came in under a fraction of the expected time.

    Rules
    -----
    * ``time_taken < expected_min * TIME_ANOMALY_HIGH_RATIO``    → ``high``
    * ``time_taken < expected_min * TIME_ANOMALY_MEDIUM_RATIO``  → ``medium``
    * otherwise                                                  → no flag (return None)

    ``submission`` is treated as opaque — only its ``id`` and ``trainer``
    (if not explicitly passed) are read. Pass a duck-typed object in tests
    so we don't have to bind this module to a not-yet-existing table.

    Returns the created `QualityAlert` row or ``None`` if no flag fired.

    TODO Week 5: invoke from the peer-review submission completion hook —
    pass the actual `Annotation` / `Submission` row + the real per-template
    expected_min_sec lookup.
    """
    if expected_min_sec is None or expected_min_sec <= 0:
        # Defensive: divide-by-zero would mark every submission as a flag.
        return None
    if time_taken_sec is None or time_taken_sec < 0:
        return None

    ratio = float(time_taken_sec) / float(expected_min_sec)
    if ratio >= TIME_ANOMALY_MEDIUM_RATIO:
        return None

    severity = (
        'high'
        if ratio < TIME_ANOMALY_HIGH_RATIO
        else 'medium'
    )

    submission_id = getattr(submission, 'id', None)
    chosen_trainer = trainer if trainer is not None else getattr(submission, 'trainer', None)

    return _create_alert(
        trigger_type='time_anomaly',
        severity=severity,
        trainer=chosen_trainer,
        submission_id=submission_id,
        details={
            'time_taken_sec': float(time_taken_sec),
            'expected_min_sec': float(expected_min_sec),
            'ratio': round(ratio, 4),
            'medium_below': TIME_ANOMALY_MEDIUM_RATIO,
            'high_below': TIME_ANOMALY_HIGH_RATIO,
        },
    )


# ---------------------------------------------------------------------------
# (2) Reviewer disagreement — 3 reviewers, count how many agreed.
# ---------------------------------------------------------------------------


def flag_reviewer_disagree(
    submission,
    reviewers_results: Iterable[bool],
    *,
    trainer=None,
):
    """Flag based on how many reviewers agreed with the trainer's answer.

    ``reviewers_results`` is a list of ``True``/``False`` (one entry per
    reviewer). We classify by the agree-count:

    * 0/3 agree → ``critical``
    * 1/3 agree → ``high``
    * 2/3 agree → ``medium``
    * 3/3 agree → no flag

    Empty / partial reviewer panels return ``None`` (we can't reason about
    disagreement until the panel completes; the Week 5 caller is expected
    to invoke this only on the final reviewer submission).

    TODO Week 5: invoke from the peer-review aggregation step once 3
    reviewer rows land for the same submission.
    """
    results = list(reviewers_results or [])
    if len(results) < 3:
        return None

    agree_count = sum(1 for r in results if bool(r))
    total = len(results)

    if agree_count == total:
        return None

    if agree_count == 0:
        severity = 'critical'
    elif agree_count == 1:
        severity = 'high'
    elif agree_count == 2:
        severity = 'medium'
    else:
        # 3+ agreements out of 3 (or unusual panel sizes) — no flag.
        return None

    submission_id = getattr(submission, 'id', None)
    chosen_trainer = trainer if trainer is not None else getattr(submission, 'trainer', None)

    return _create_alert(
        trigger_type='reviewer_disagree',
        severity=severity,
        trainer=chosen_trainer,
        submission_id=submission_id,
        details={
            'agree_count': agree_count,
            'total_reviewers': total,
            'reviewers_results': [bool(r) for r in results],
        },
    )


# ---------------------------------------------------------------------------
# (3) Duplicate-answer pattern — same trainer copy-pasting same answer.
# ---------------------------------------------------------------------------


def _normalised_answer_fingerprint(answer: Any) -> str:
    """Return a stable hash for an answer payload so we can group duplicates.

    Strings are lower-cased + stripped. Dicts/lists are JSON-serialised with
    sorted keys. Numbers are stringified. We hash so the table doesn't have
    to store full answer bodies in memory while detecting.
    """
    if answer is None:
        normalised = ''
    elif isinstance(answer, str):
        normalised = answer.strip().lower()
    elif isinstance(answer, (dict, list, tuple)):
        try:
            normalised = json.dumps(answer, sort_keys=True, ensure_ascii=False)
        except TypeError:
            normalised = str(answer)
    else:
        normalised = str(answer)
    return hashlib.sha1(normalised.encode('utf-8')).hexdigest()


def flag_duplicate_pattern(
    trainer,
    recent_answers: Iterable[Any],
    *,
    window_size: int = 30,
):
    """Flag a trainer who submitted > N identical answers in the recent window.

    ``recent_answers`` is the trainer's last `window_size` answer payloads,
    most-recent-first. We fingerprint each one and look for any single
    fingerprint with count > ``DUPLICATE_PATTERN_THRESHOLD``.

    Returns the created alert (or ``None`` when no fingerprint exceeds the
    threshold). The detected fingerprint + count + a small sample of the
    most recent duplicate values land in ``details`` so the admin can
    investigate without opening the raw submissions.

    TODO Week 5: pass `Annotation.objects.filter(user=trainer).order_by('-id')[:30]`
    and extract `.result` from each row, then call this.
    """
    if trainer is None:
        return None

    answers = list(recent_answers or [])
    if not answers:
        return None

    # Slice to the requested window so a caller that passes a giant list
    # by accident still respects the "last N" semantics.
    answers = answers[:window_size]

    counts: Dict[str, int] = {}
    samples: Dict[str, List[Any]] = {}
    for ans in answers:
        fp = _normalised_answer_fingerprint(ans)
        counts[fp] = counts.get(fp, 0) + 1
        samples.setdefault(fp, []).append(ans)

    # Most-duplicated fingerprint.
    best_fp = None
    best_count = 0
    for fp, c in counts.items():
        if c > best_count:
            best_fp = fp
            best_count = c

    if best_fp is None or best_count <= DUPLICATE_PATTERN_THRESHOLD:
        return None

    return _create_alert(
        trigger_type='duplicate_pattern',
        severity='medium',
        trainer=trainer,
        submission_id=None,
        details={
            'window_size': window_size,
            'threshold': DUPLICATE_PATTERN_THRESHOLD,
            'duplicate_count': best_count,
            'duplicate_fingerprint': best_fp,
            # Keep the sample bounded so a giant answer blob can't blow up
            # the details column. 3 entries is plenty for admin context.
            'sample_values': [str(s)[:200] for s in samples[best_fp][:3]],
            'detected_at': timezone.now().isoformat().replace('+00:00', 'Z'),
        },
    )


# ---------------------------------------------------------------------------
# Convenience — list helpers used by the admin endpoint.
# ---------------------------------------------------------------------------


def open_alert_count_by_severity() -> Dict[str, int]:
    """Return ``{severity: open_count}`` — used by the dashboard widget.

    Always returns all 4 severity keys even if zero, so the React widget
    can render a 4-cell grid without `?? 0` ceremony on every render.
    """
    from core.models_alerts import QualityAlert

    out: Dict[str, int] = {
        QualityAlert.SEVERITY_LOW: 0,
        QualityAlert.SEVERITY_MEDIUM: 0,
        QualityAlert.SEVERITY_HIGH: 0,
        QualityAlert.SEVERITY_CRITICAL: 0,
    }
    rows = (
        QualityAlert.objects
        .filter(status=QualityAlert.STATUS_OPEN)
        .values_list('severity')
    )
    for (sev,) in rows:
        if sev in out:
            out[sev] += 1
    return out
