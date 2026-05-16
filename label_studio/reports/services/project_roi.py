"""Project ROI analyzer — Phase 2 WAVE-19 real-data wiring.

Computes per-project cost, revenue, profit, and ROI from real Django ORM
queries against ``projects.Project`` / ``tasks.Task`` / ``payments.PaymentHold``.

Empty DB → ``[]`` and ``compute_project_roi(unknown_id)`` → ``None``. No
fabricated activity.

Cost components (Phase 1 best-effort)
-------------------------------------
* ``trainer_payout_inr``   - sum(PaymentHold.amount_inr) for tasks in project
* ``reviewer_payout_inr``  - 0 until reviewer payment ledger lands (Phase 2/3)
* ``infra_cost_inr``       - 0 until ops-cost field lands on Project (Phase 2/3)
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Dict, List, Optional


def _decimal_to_int(v) -> int:
    if v is None:
        return 0
    if isinstance(v, Decimal):
        return int(v)
    return int(v)


def _build_roi_for_project(project) -> Dict[str, Any]:
    """Build the ROI dict for a single project from real ORM rows."""
    from django.db.models import Count, Sum

    from payments.models import PaymentHold
    from peer_review.models import ConsensusResult

    task_ids = list(project.tasks.values_list('id', flat=True))
    tasks_created = len(task_ids)
    tasks_completed = 0
    if task_ids:
        # "Completed" = consensus computed in approved/flagged status.
        tasks_completed = ConsensusResult.objects.filter(
            task_id__in=task_ids,
            status__in=[
                ConsensusResult.STATUS_APPROVED,
                ConsensusResult.STATUS_FLAGGED,
            ],
        ).count()

    trainer_payout_inr = 0
    if task_ids:
        trainer_payout_inr = _decimal_to_int(
            PaymentHold.objects.filter(
                task_id__in=task_ids,
                status__in=[
                    PaymentHold.STATUS_RELEASED,
                    PaymentHold.STATUS_HELD,
                ],
            ).aggregate(s=Sum('amount_inr'))['s']
        )

    reviewer_payout_inr = 0  # ledger not in scope for Phase 1
    infra_cost_inr = 0  # ops-cost field not on Project yet

    total_cost_inr = trainer_payout_inr + reviewer_payout_inr + infra_cost_inr
    # external_revenue_inr is not tracked anywhere yet — emit 0 honestly.
    external_revenue_inr = 0
    profit_inr = external_revenue_inr - total_cost_inr
    roi_pct = int(round((profit_inr / total_cost_inr) * 100)) if total_cost_inr > 0 else 0

    # Quality score
    consensus_rows = (
        ConsensusResult.objects.filter(task_id__in=task_ids) if task_ids else None
    )
    if consensus_rows and consensus_rows.exists():
        total = consensus_rows.count()
        passed = consensus_rows.filter(
            status__in=[
                ConsensusResult.STATUS_APPROVED,
                ConsensusResult.STATUS_FLAGGED,
            ]
        ).count()
        quality_score_pct = int(round((passed / total) * 100)) if total else 0
    else:
        quality_score_pct = 0

    quality_passed = int(round(tasks_completed * quality_score_pct / 100)) if quality_score_pct else 0
    cost_per_quality_task_inr = int(round(total_cost_inr / max(1, quality_passed))) if quality_passed else 0

    return {
        'project_id': project.id,
        'project_name': project.title or f'Project #{project.id}',
        'project_type': '',
        'language': '',
        'tasks_created': tasks_created,
        'tasks_completed': tasks_completed,
        'trainer_payout_inr': trainer_payout_inr,
        'reviewer_payout_inr': reviewer_payout_inr,
        'infra_cost_inr': infra_cost_inr,
        'total_cost_inr': total_cost_inr,
        'external_revenue_inr': external_revenue_inr,
        'profit_inr': profit_inr,
        'roi_pct': roi_pct,
        'cost_per_quality_task_inr': cost_per_quality_task_inr,
        'time_to_complete_days': 0,
        'quality_score_pct': quality_score_pct,
    }


def compute_project_roi(project_id: int) -> Optional[Dict[str, Any]]:
    """Return the ROI breakdown for a single project.

    Returns ``None`` for an unknown ``project_id`` so the API layer can 404.
    """
    try:
        from projects.models import Project
    except Exception:
        return None
    project = Project.objects.filter(id=int(project_id)).first()
    if project is None:
        return None
    return _build_roi_for_project(project)


def compute_all_project_roi() -> List[Dict[str, Any]]:
    """Return every project's ROI breakdown. Empty DB → ``[]``."""
    try:
        from projects.models import Project
    except Exception:
        return []
    rows = [_build_roi_for_project(p) for p in Project.objects.all()]
    rows.sort(key=lambda r: -r['roi_pct'])
    return rows
