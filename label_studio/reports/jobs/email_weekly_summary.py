"""Weekly summary auto-email — Phase 1 Step 7.

Schedule (Phase 2, not wired yet): every Monday 9:00 AM IST. The handler:

1. Builds the founder weekly snapshot via ``founder_weekly``.
2. Renders the snapshot as a PDF via ``pdf_renderer``.
3. Sends a single email to the founder mailbox with the PDF attached and an
   inline summary block (so the founder can read the gist on phone without
   opening the attachment).

Builds on the existing daily_report from Step 4.2-10 — same recipient list,
same SMTP backend, just a different cadence.

Phase 1
-------
The cron isn't scheduled yet. ``send_weekly_summary`` is callable + has unit
tests; the systemd / django_rq periodic tick lands in Phase 2.

Founder rules honoured
----------------------
* No founder personal mobile (per ``MEMORY.md → feedback_no_founder_personal_number``)
  appears in the email body. The recipient list comes from
  ``settings.TRAINPLEX_FOUNDER_REPORTS_TO`` env / settings, defaulting to the
  founder business email only.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from reports.services import founder_weekly, pdf_renderer

logger = logging.getLogger(__name__)


_DEFAULT_RECIPIENTS = ('founder@trainplex.test',)


def _resolve_recipients() -> List[str]:
    """Pull recipient list from settings, with a safe default.

    Setting name: ``TRAINPLEX_FOUNDER_REPORTS_TO`` (tuple or list of emails).
    Phase 2 will replace this with a proper FounderRecipientList model.
    """
    try:
        from django.conf import settings

        configured = getattr(settings, 'TRAINPLEX_FOUNDER_REPORTS_TO', None)
        if configured:
            return list(configured)
    except Exception:
        pass
    return list(_DEFAULT_RECIPIENTS)


def build_weekly_summary_email(
    snapshot: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Build the email envelope for a weekly summary.

    Returns a dict (not sent yet) so tests can assert the envelope before
    plumbing the SMTP backend.

    Parameters
    ----------
    snapshot:
        Optional pre-built snapshot. If omitted, builds one now.

    Returns
    -------
    Dict with keys:
        * ``subject``      - subject line
        * ``body_text``    - plain-text body (shown inline)
        * ``recipients``   - list of email addresses
        * ``pdf_filename`` - what the attachment should be called
        * ``pdf_bytes``    - the rendered PDF
    """
    snap = snapshot if snapshot is not None else founder_weekly.build_founder_weekly_snapshot()
    kpis = snap['top_kpis']
    q = snap['quality_kpis']

    body_lines = [
        f'TrainPlex Founder Weekly — {snap["week_start"]} to {snap["week_end"]}',
        '',
        f'  Submissions this week     : {kpis["submissions_weekly"]:,} '
        f'({kpis["submissions_delta_pct"]:+}%)',
        f'  Revenue this week         : INR {kpis["revenue_weekly_inr"]:,} '
        f'({kpis["revenue_delta_pct"]:+}%)',
        f'  Active trainers           : {kpis["active_trainers"]} '
        f'({kpis["active_trainers_delta_pct"]:+}%)',
        f'  Avg payout per trainer    : INR {kpis["avg_payout_per_trainer_inr"]:,}',
        '',
        f'  Avg consensus             : {q["avg_consensus_pct"]}%',
        f'  Dispute rate              : {q["dispute_rate_pct"]}%',
        '',
        'Top 3 projects by ROI:',
    ]
    sorted_projects = sorted(snap['project_roi'], key=lambda r: -r['roi_pct'])[:3]
    for p in sorted_projects:
        body_lines.append(
            f'  #{p["project_id"]}  {p["project_name"]:<32}  ROI {p["roi_pct"]}%'
        )
    body_lines.append('')
    body_lines.append('Full breakdown attached as PDF.')
    body_text = '\n'.join(body_lines)

    pdf_bytes = pdf_renderer.render_founder_weekly_pdf(snap)

    return {
        'subject': f'[TrainPlex] Founder weekly — week of {snap["week_start"]}',
        'body_text': body_text,
        'recipients': _resolve_recipients(),
        'pdf_filename': f'founder-weekly-{snap["week_start"]}.pdf',
        'pdf_bytes': pdf_bytes,
    }


def send_weekly_summary(
    snapshot: Optional[Dict[str, Any]] = None,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """Top-level cron entry point.

    Parameters
    ----------
    snapshot:
        Optional pre-built snapshot — if omitted, builds a fresh one.
    dry_run:
        If True, returns the envelope without invoking the SMTP backend.
        Tests pass ``dry_run=True`` so they don't hit the network.

    Returns
    -------
    Dict
        ``{'sent': bool, 'recipients': [...], 'subject': ..., 'pdf_size': int}``
    """
    envelope = build_weekly_summary_email(snapshot)

    if dry_run:
        return {
            'sent': False,
            'recipients': envelope['recipients'],
            'subject': envelope['subject'],
            'pdf_size': len(envelope['pdf_bytes']),
            'dry_run': True,
        }

    # Phase 2 wiring — real send via django.core.mail. Wrap so the cron
    # doesn't crash if SMTP isn't configured in this env.
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
        logger.warning('Weekly summary send failed: %s', exc)
        sent = False

    return {
        'sent': sent,
        'recipients': envelope['recipients'],
        'subject': envelope['subject'],
        'pdf_size': len(envelope['pdf_bytes']),
        'dry_run': False,
    }
