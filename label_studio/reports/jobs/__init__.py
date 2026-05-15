"""TrainPlex auto-email report jobs — Phase 1 Step 7.

These are cron-callable functions that build the founder weekly / monthly
report and ship it to the founder mailbox.

Phase 1: deliberately NOT scheduled. The functions are callable + tested,
but the systemd / django_rq periodic tick lands in Phase 2 (same pattern
as ``peer_review.timeout_sweep``).
"""

from reports.jobs.email_weekly_summary import (
    build_weekly_summary_email,
    send_weekly_summary,
)
from reports.jobs.email_monthly_summary import (
    build_monthly_summary_email,
    send_monthly_summary,
)

__all__ = [
    'build_weekly_summary_email',
    'send_weekly_summary',
    'build_monthly_summary_email',
    'send_monthly_summary',
]
