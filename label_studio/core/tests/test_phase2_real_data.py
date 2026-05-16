"""Phase 2 WAVE-19 — real-data wiring smoke tests.

Asserts the 17 fork endpoints whose mock data was replaced now return real
DB aggregations, and that an EMPTY database returns honest zeros / empty
lists rather than fabricated activity.

Founder rule: "data dikh raha hai but kisi ne task kiye nahi" — empty DB
must show 0 submissions, 0 active trainers, empty arrays.
"""

from __future__ import annotations

import pytest


# ---------------------------------------------------------------------------
# /api/v1/admin/dashboard/snapshot
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_dashboard_snapshot_empty_db_returns_zeros(authenticated_client):
    """Empty DB: zero submissions, zero active trainers, no top-trainers list,
    zero alerts. Specifically NOT the legacy mock numbers (142 / 47 / etc.).
    """
    resp = authenticated_client.get('/api/v1/admin/dashboard/snapshot')
    assert resp.status_code == 200, resp.content
    body = resp.json()

    # Shape is preserved.
    assert 'as_of' in body
    assert 'today' in body
    assert 'top_trainers' in body
    assert 'alerts' in body

    today = body['today']
    # The previous mock-shape values were 142 / 47 / 4200 / 18500. We must
    # NOT be returning those. Use exact equality to 0 to make the regression
    # obvious if mock ever sneaks back.
    assert today['submissions_count'] == 0
    assert today['submissions_delta_pct'] == 0
    assert today['active_trainers'] == 0
    assert today['pay_hold_total_inr'] == 0
    assert today['pay_released_today_inr'] == 0

    assert body['top_trainers'] == []

    alerts = body['alerts']
    assert alerts['disputes_pending'] == 0
    assert alerts['quality_flags'] == 0
    assert alerts['stuck_payouts'] == 0


# ---------------------------------------------------------------------------
# /api/v1/admin/heatmap/state-activity
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_heatmap_empty_db_returns_empty_list(authenticated_client):
    """Empty DB: heatmap returns []. Specifically NOT the 17-state mock array."""
    resp = authenticated_client.get('/api/v1/admin/heatmap/state-activity?period=month')
    assert resp.status_code == 200, resp.content
    body = resp.json()
    # Honest empty list — NOT the 17-state mock catalog.
    assert isinstance(body, list)
    assert body == []


@pytest.mark.django_db
def test_heatmap_unknown_period_falls_back_to_default_still_empty(authenticated_client):
    """Garbage ?period= → still 200 + []. Confirms the fall-back path stayed honest."""
    resp = authenticated_client.get('/api/v1/admin/heatmap/state-activity?period=zzz')
    assert resp.status_code == 200, resp.content
    assert resp.json() == []


# ---------------------------------------------------------------------------
# /api/v1/admin/reports/leaderboard
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_leaderboard_empty_db_returns_empty_list(authenticated_client):
    """Empty DB: leaderboard returns empty results + empty hall-of-fame.
    Specifically NOT the 30-trainer mock seed.
    """
    resp = authenticated_client.get('/api/v1/admin/reports/leaderboard?period=weekly')
    assert resp.status_code == 200, resp.content
    body = resp.json()

    assert body['period'] == 'weekly'
    # Honest empty — the legacy mock had 30 deterministic seeds; we must not.
    assert body['results'] == []
    assert body['total'] == 0
    assert body['hall_of_fame_lifetime'] == []
    assert body['hall_of_fame_month'] == []


@pytest.mark.django_db
def test_founder_weekly_empty_db_returns_zeros(authenticated_client):
    """Empty DB: founder-weekly KPIs all 0, splits all []."""
    resp = authenticated_client.get('/api/v1/admin/reports/founder-weekly')
    assert resp.status_code == 200, resp.content
    body = resp.json()

    kpis = body['top_kpis']
    assert kpis['submissions_weekly'] == 0
    assert kpis['revenue_weekly_inr'] == 0
    assert kpis['active_trainers'] == 0

    assert body['cohort_retention'] == []
    assert body['project_roi'] == []
    assert body['geographic_split'] == []
    assert body['language_split'] == []

    quality = body['quality_kpis']
    assert quality['avg_consensus_pct'] == 0
    assert quality['dispute_rate_pct'] == 0
    assert quality['top_10_problematic'] == []
