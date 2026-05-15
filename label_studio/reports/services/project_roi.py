"""Per-project ROI service — Phase 1 Step 7.

Builds the cost / revenue / ROI breakdown for a single project so the founder
can quickly read which projects are paying for themselves and which need to
be repriced.

Output fields
-------------
* ``project_id`` / ``project_name`` / ``project_type``
* ``tasks_created`` / ``tasks_completed``
* ``trainer_payout_inr``        - sum of WalletTransaction.TYPE_RELEASE for this project
* ``reviewer_payout_inr``       - peer-review reviewer pay (Step 6 → consensus)
* ``infra_cost_inr``            - LS + storage + ML inference allocation
* ``total_cost_inr``            - sum of trainer + reviewer + infra
* ``external_revenue_inr``      - what we billed the customer (Phase 2 wiring)
* ``profit_inr``                - external_revenue - total_cost
* ``roi_pct``                   - (profit / total_cost) * 100, int
* ``cost_per_quality_task_inr`` - total_cost / max(1, quality_passed_tasks)
* ``time_to_complete_days``     - calendar days from kickoff → 95% completion
* ``quality_score_pct``         - share of tasks passing 3-reviewer consensus

Phase 1: deterministic mocks per project_id in a known seed range. Unknown
ids return a "not_found" sentinel (None) so the API can 404.

TODO Phase 2: replace with real aggregation joining Project / WalletTransaction
/ PayoutQueue / Submission tables.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Mock project catalogue
# ---------------------------------------------------------------------------

_PROJECT_CATALOG: Dict[int, Dict[str, Any]] = {
    101: {
        'project_id': 101,
        'project_name': 'KYC OCR — Hindi',
        'project_type': 'ocr',
        'language': 'hi',
        'tasks_created': 5000,
        'tasks_completed': 4825,
        'trainer_payout_inr': 96_500,
        'reviewer_payout_inr': 28_500,
        'infra_cost_inr': 20_000,
        'external_revenue_inr': 285_000,
        'time_to_complete_days': 18,
        'quality_score_pct': 92,
    },
    102: {
        'project_id': 102,
        'project_name': 'Voice intent — Bhojpuri',
        'project_type': 'voice',
        'language': 'bho',
        'tasks_created': 3200,
        'tasks_completed': 3040,
        'trainer_payout_inr': 64_000,
        'reviewer_payout_inr': 18_500,
        'infra_cost_inr': 9_500,
        'external_revenue_inr': 158_000,
        'time_to_complete_days': 22,
        'quality_score_pct': 87,
    },
    103: {
        'project_id': 103,
        'project_name': 'Receipt extract — Tamil',
        'project_type': 'ocr',
        'language': 'ta',
        'tasks_created': 2400,
        'tasks_completed': 2350,
        'trainer_payout_inr': 48_000,
        'reviewer_payout_inr': 14_000,
        'infra_cost_inr': 6_000,
        'external_revenue_inr': 118_000,
        'time_to_complete_days': 15,
        'quality_score_pct': 90,
    },
    104: {
        'project_id': 104,
        'project_name': 'Sentiment — Marathi',
        'project_type': 'sentiment',
        'language': 'mr',
        'tasks_created': 2000,
        'tasks_completed': 1880,
        'trainer_payout_inr': 38_000,
        'reviewer_payout_inr': 11_000,
        'infra_cost_inr': 5_000,
        'external_revenue_inr': 84_000,
        'time_to_complete_days': 16,
        'quality_score_pct': 85,
    },
    105: {
        'project_id': 105,
        'project_name': 'Image moderation',
        'project_type': 'moderation',
        'language': 'hi',
        'tasks_created': 1500,
        'tasks_completed': 1380,
        'trainer_payout_inr': 32_000,
        'reviewer_payout_inr': 9_500,
        'infra_cost_inr': 6_500,
        'external_revenue_inr': 62_000,
        'time_to_complete_days': 12,
        'quality_score_pct': 81,
    },
    106: {
        'project_id': 106,
        'project_name': 'Voice intent — Hindi',
        'project_type': 'voice',
        'language': 'hi',
        'tasks_created': 4200,
        'tasks_completed': 4020,
        'trainer_payout_inr': 78_000,
        'reviewer_payout_inr': 22_500,
        'infra_cost_inr': 11_500,
        'external_revenue_inr': 198_000,
        'time_to_complete_days': 19,
        'quality_score_pct': 89,
    },
}


# ---------------------------------------------------------------------------
# Computation
# ---------------------------------------------------------------------------


def _decorate_roi(row: Dict[str, Any]) -> Dict[str, Any]:
    """Compute the derived ROI / cost / profit fields from raw cost data.

    Kept as a single transform so the unit test can assert the math directly
    against the seed catalogue without having to spin up the API layer.
    """
    total_cost_inr = (
        row['trainer_payout_inr']
        + row['reviewer_payout_inr']
        + row['infra_cost_inr']
    )
    revenue = row['external_revenue_inr']
    profit_inr = revenue - total_cost_inr
    roi_pct = (
        int(round((profit_inr / total_cost_inr) * 100))
        if total_cost_inr > 0
        else 0
    )
    quality_passed = int(
        round(row['tasks_completed'] * row['quality_score_pct'] / 100)
    )
    cost_per_quality_task_inr = (
        int(round(total_cost_inr / max(1, quality_passed)))
    )

    return {
        'project_id': row['project_id'],
        'project_name': row['project_name'],
        'project_type': row['project_type'],
        'language': row['language'],
        'tasks_created': row['tasks_created'],
        'tasks_completed': row['tasks_completed'],
        'trainer_payout_inr': row['trainer_payout_inr'],
        'reviewer_payout_inr': row['reviewer_payout_inr'],
        'infra_cost_inr': row['infra_cost_inr'],
        'total_cost_inr': total_cost_inr,
        'external_revenue_inr': revenue,
        'profit_inr': profit_inr,
        'roi_pct': roi_pct,
        'cost_per_quality_task_inr': cost_per_quality_task_inr,
        'time_to_complete_days': row['time_to_complete_days'],
        'quality_score_pct': row['quality_score_pct'],
    }


def compute_project_roi(project_id: int) -> Optional[Dict[str, Any]]:
    """Return the ROI breakdown for a single project.

    Returns ``None`` for an unknown ``project_id`` so the API layer can 404.

    TODO Phase 2: replace the seed lookup with a real aggregation over the
    Project / WalletTransaction / PayoutQueue tables joined on project_id.
    """
    row = _PROJECT_CATALOG.get(int(project_id))
    if row is None:
        return None
    return _decorate_roi(row)


def compute_all_project_roi() -> List[Dict[str, Any]]:
    """Return every project's ROI breakdown — used for the table view.

    Sorted DESC by roi_pct so the founder reads top-performing projects first.
    """
    rows = [_decorate_roi(row) for row in _PROJECT_CATALOG.values()]
    rows.sort(key=lambda r: -r['roi_pct'])
    return rows
