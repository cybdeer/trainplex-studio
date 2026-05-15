"""Monthly summary auto-email — Phase 1 Step 7.

Schedule (Phase 2, not wired yet): 1st of every month at 09:00 IST. Builds
the founder weekly snapshot for the most-recently-closed week + a per-project
ROI table covering the past calendar month, ships both as a single PDF
attachment to the founder mailbox.

Phase 1: callable + tested. Cron not scheduled yet.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from reports.services import founder_weekly, pdf_renderer, project_roi
from reports.jobs.email_weekly_summary import _resolve_recipients

logger = logging.getLogger(__name__)


def build_monthly_summary_email(
    snapshot: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Build the email envelope for a monthly summary.

    Returns a dict (not sent yet) so tests can assert the envelope. The body
    text shows a tighter view than the weekly body — focus on the per-project
    ROI table since the founder uses the monthly cadence for pricing reviews.
    """
    snap = snapshot if snapshot is not None else founder_weekly.build_founder_weekly_snapshot()
    kpis = snap['top_kpis']
    roi_rows = project_roi.compute_all_project_roi()

    body_lines = [
        f'TrainPlex Founder Monthly — month of {snap["week_start"][:7]}',
        '',
        f'  Submissions this week     : {kpis["submissions_weekly"]:,}',
        f'  Revenue this week         : INR {kpis["revenue_weekly_inr"]:,}',
        f'  Active trainers           : {kpis["active_trainers"]}',
        '',
        'Per-project ROI (sorted by ROI%):',
    ]
    for r in roi_rows:
        body_lines.append(
            f'  #{r["project_id"]:<3} {r["project_name"]:<32}  '
            f'cost INR {r["total_cost_inr"]:,}  rev INR {r["external_revenue_inr"]:,}  '
            f'ROI {r["roi_pct"]}%'
        )
    body_lines.append('')
    body_lines.append('Full breakdown attached as PDF.')
    body_text = '\n'.join(body_lines)

    pdf_bytes = pdf_renderer.render_founder_weekly_pdf(snap)

    return {
        'subject': f'[TrainPlex] Founder monthly — month of {snap["week_start"][:7]}',
        'body_text': body_text,
        'recipients': _resolve_recipients(),
        'pdf_filename': f'founder-monthly-{snap["week_start"][:7]}.pdf',
        'pdf_bytes': pdf_bytes,
    }


def send_monthly_summary(
    snapshot: Optional[Dict[str, Any]] = None,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """Cron entry point for monthly summary."""
    envelope = build_monthly_summary_email(snapshot)

    if dry_run:
        return {
            'sent': False,
            'recipients': envelope['recipients'],
            'subject': envelope['subject'],
            'pdf_size': len(envelope['pdf_bytes']),
            'dry_run': True,
        }

    try:
        from django.core.mail import EmailMessage

        msg = EmailMessage(
            subject=envelope['subject'],
            body=envelope['body_text'],
            to=envelope['recipients'],
        )
        msg.attach(
            envelope['pdf_filename'],
            envelope['pdf_bytes'],
            'application/pdf',
        )
        msg.send(fail_silently=True)
        sent = True
    except Exception as exc:
        logger.warning('Monthly summary send failed: %s', exc)
        sent = False

    return {
        'sent': sent,
        'recipients': envelope['recipients'],
        'subject': envelope['subject'],
        'pdf_size': len(envelope['pdf_bytes']),
        'dry_run': False,
    }
