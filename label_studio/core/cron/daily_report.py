"""Cron registration recipe for the TrainPlex daily founder email.

Phase 1 Step 4.2-10.

This module is intentionally **documentation-only**. It lives next to the
service it describes (``core/services/daily_report_email.py``) so the ops
recipe doesn't drift from the code that actually does the work.

Schedule
--------
Every day at **08:00 Asia/Kolkata (IST)** — the founder gets the brief
before opening the dashboard.

Why 08:00 IST? The brief summarises *yesterday*'s data; the cron has to
fire *after* day-end (00:00 IST). 08:00 is the sweet spot between
"founder-checks-phone time" and "give the DB a few hours to settle".

Management command
------------------
::

    python manage.py send_daily_report \
        --recipient $TRAINPLEX_FOUNDER_EMAIL

The command defaults ``--recipient`` from settings.TRAINPLEX_FOUNDER_EMAIL
(itself env-driven) so the explicit ``--recipient`` flag is only needed
for ad-hoc resends from the shell.


Option A — systemd timer (recommended for VPS deploys)
------------------------------------------------------
``/etc/systemd/system/trainplex-daily-report.service``::

    [Unit]
    Description=TrainPlex daily founder report (8:00 IST)
    Wants=network-online.target
    After=network-online.target

    [Service]
    Type=oneshot
    User=trainplex
    WorkingDirectory=/opt/trainplex-studio/label_studio
    Environment=TRAINPLEX_FOUNDER_EMAIL=vk.vinodparihar1@gmail.com
    ExecStart=/opt/trainplex-studio/.venv/bin/python manage.py send_daily_report

``/etc/systemd/system/trainplex-daily-report.timer``::

    [Unit]
    Description=Fire trainplex-daily-report.service every morning at 08:00 IST

    [Timer]
    OnCalendar=*-*-* 08:00:00 Asia/Kolkata
    Persistent=true
    Unit=trainplex-daily-report.service

    [Install]
    WantedBy=timers.target

Enable + start::

    sudo systemctl daemon-reload
    sudo systemctl enable --now trainplex-daily-report.timer
    sudo systemctl list-timers | grep trainplex


Option B — classic crontab (Docker / quick deploys)
---------------------------------------------------
Container/host must already have ``TZ=Asia/Kolkata`` (or convert manually
to UTC — 08:00 IST == 02:30 UTC).

``crontab -e`` adds the line::

    0 8 * * * cd /opt/trainplex-studio/label_studio && \
        TRAINPLEX_FOUNDER_EMAIL=vk.vinodparihar1@gmail.com \
        /opt/trainplex-studio/.venv/bin/python manage.py send_daily_report \
        >> /var/log/trainplex/daily-report.log 2>&1

If the host runs in UTC, change to::

    30 2 * * * ...    # 02:30 UTC == 08:00 IST


Option C — django-q (Phase 2 — production)
------------------------------------------
TODO Phase 2 (founder-env): register a schedule once django-q (or celery
beat) is wired in. The shape::

    from django_q.models import Schedule
    Schedule.objects.update_or_create(
        name='trainplex-daily-report',
        defaults={
            'func': 'core.cron.daily_report.run',
            'schedule_type': Schedule.CRON,
            'cron': '0 8 * * *',          # 08:00 daily (IST when TZ set)
            'repeats': -1,
        },
    )

The schedule calls :func:`run` below, which is the in-process equivalent
of the management command — no subprocess overhead inside the worker.


Recipient policy
----------------
* Production: ``TRAINPLEX_FOUNDER_EMAIL`` env var → founder inbox.
* Staging / dev: leave the env var unset so the dummy email backend
  short-circuits; `send_daily_report` logs the rendered preview length
  + recipient + subject without actually sending.

Founder-personal-number rule
----------------------------
The founder's personal mobile is NEVER in the email body, the subject,
the recipient string, or any log row this cron writes. The defensive
check lives in ``core/services/daily_report_email._assert_no_founder_personal_number``.
"""

from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger(__name__)


def run(recipient_email: Optional[str] = None) -> dict:
    """Cron entry-point — in-process equivalent of the management command.

    Lets Phase 2's django-q (or celery beat) point at this directly:
    ``schedule.func = 'core.cron.daily_report.run'``. No subprocess
    spawn — runs inside the worker.

    Parameters
    ----------
    recipient_email : str | None
        Recipient override; ``None`` → ``settings.TRAINPLEX_FOUNDER_EMAIL``.

    Returns
    -------
    dict
        Same shape that ``send_daily_report`` returns. Logged at INFO.
    """
    # Late import so Django bootstrapping runs before we touch the ORM
    # (matches the management-command import discipline).
    from core.services import daily_report_email

    summary = daily_report_email.build_daily_summary(None)
    result = daily_report_email.send_daily_report(
        recipient_email=recipient_email,
        summary=summary,
    )
    logger.info(
        'TrainPlex daily report cron result: recipient=%s sent=%s mode=%s '
        'preview_len=%s',
        result.get('recipient'),
        result.get('sent'),
        result.get('mode'),
        result.get('preview_len'),
    )
    return result


__all__ = ['run']
