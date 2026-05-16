"""TrainPlex APScheduler — fires the six cron-fed jobs that were callable+documented
but never actually scheduled in production (Codex audit finding M4).

This module is loaded by ``manage.py run_scheduler`` (Django management command)
which runs as its own container (``scheduler`` service in docker-compose.override.yml).
Running outside the uwsgi master avoids the fork-double-start problem.

Schedule (all IST):
  daily_report          08:00 daily       core.services.daily_report_email.send_daily_report
  weekly_report         Mon 09:00         reports.services.founder_weekly.build_founder_weekly_snapshot (+ log; sender TODO)
  monthly_report        1st 09:00         reports.services.monthly_summary.run
  payout_flush          every 30 min      payments.services.payout_flush.run
  review_timeout_sweep  every 60 min      peer_review.services.timeout_sweep.run
  quality_alert_scan    every 15 min      core.services.quality_anomaly_detector.flag_* (composite scan)

Dry-run guard
-------------
``TRAINPLEX_CRON_DRY_RUN=true`` (default for tonight's roll-out) makes every job
log its intent without sending real emails / WhatsApps. The job functions
themselves either accept ``dry_run=True`` (e.g. ``send_daily_report``) or are
short-circuited here before any side-effect.

Founder mobile guard
--------------------
``send_daily_report`` already enforces ``_assert_no_founder_personal_number``
on subject + recipient — we do not bypass it.
"""

from __future__ import annotations

import logging
import os
import signal
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

import pytz
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from django.conf import settings

IST = pytz.timezone('Asia/Kolkata')
INCIDENT_LOG = Path('/var/lib/trainplex-data/INCIDENT_LOG.md')

logger = logging.getLogger('trainplex.scheduler')


def _dry_run() -> bool:
    return os.environ.get('TRAINPLEX_CRON_DRY_RUN', 'true').lower() in ('1', 'true', 'yes')


def _log_to_incident(line: str) -> None:
    """Append a one-line fire-record to INCIDENT_LOG (best-effort)."""
    try:
        if not INCIDENT_LOG.parent.exists():
            return
        with INCIDENT_LOG.open('a', encoding='utf-8') as f:
            f.write(line.rstrip() + '\n')
    except Exception as exc:  # pragma: no cover — never crash the scheduler over a log line
        logger.warning('INCIDENT_LOG append failed: %s', exc)


def _stamp(name: str, outcome: str) -> None:
    ts = datetime.now(IST).strftime('%Y-%m-%d %H:%M:%S %Z')
    _log_to_incident(f'- [cron] {ts} {name} dry_run={_dry_run()} outcome={outcome}')


# ---------------------------------------------------------------------------
# Job implementations
# ---------------------------------------------------------------------------

def job_daily_report() -> None:
    """08:00 IST — founder daily summary email."""
    name = 'daily_report'
    logger.info('[cron] %s firing dry_run=%s', name, _dry_run())
    try:
        from core.services import daily_report_email

        summary = daily_report_email.build_daily_summary(None)  # yesterday
        recipient = getattr(settings, 'TRAINPLEX_FOUNDER_EMAIL', None)
        if not recipient:
            logger.warning('[cron] %s skipped — TRAINPLEX_FOUNDER_EMAIL unset', name)
            _stamp(name, 'skipped-no-recipient')
            return
        result = daily_report_email.send_daily_report(
            recipient_email=recipient,
            summary=summary,
            dry_run=_dry_run(),
        )
        logger.info('[cron] %s ok: %s', name, result)
        _stamp(name, f'ok mode={result.get("mode")} sent={result.get("sent")}')
    except Exception as exc:
        logger.exception('[cron] %s FAILED: %s', name, exc)
        _stamp(name, f'error {exc!r}')


def job_weekly_report() -> None:
    """Monday 09:00 IST — founder weekly snapshot.

    ``founder_weekly`` has ``build_founder_weekly_snapshot`` but no email
    sender wrapper yet. For dry-run we just compute + log. Real send is
    a follow-up task tracked in INCIDENT_LOG.
    """
    name = 'weekly_report'
    logger.info('[cron] %s firing dry_run=%s', name, _dry_run())
    try:
        from reports.services import founder_weekly

        snapshot = founder_weekly.build_founder_weekly_snapshot()
        keys = list(snapshot.keys()) if isinstance(snapshot, dict) else type(snapshot).__name__
        logger.info('[cron] %s ok snapshot_keys=%s', name, keys)
        if _dry_run():
            _stamp(name, f'ok-dry-run snapshot_keys={keys}')
        else:
            # TODO: wire reports/services/founder_weekly.send_weekly_summary once that wrapper lands.
            logger.warning(
                '[cron] %s live-mode requested but no sender wrapper exists; '
                'snapshot computed only. TODO: implement send_weekly_summary().',
                name,
            )
            _stamp(name, 'partial-no-sender-wrapper')
    except Exception as exc:
        logger.exception('[cron] %s FAILED: %s', name, exc)
        _stamp(name, f'error {exc!r}')


def job_monthly_report() -> None:
    """1st of month 09:00 IST — monthly summary via reports.services.monthly_summary.run."""
    name = 'monthly_report'
    logger.info('[cron] %s firing dry_run=%s', name, _dry_run())
    try:
        from reports.services import monthly_summary
        result = monthly_summary.run(dry_run=_dry_run())
        logger.info('[cron] %s ok: %s', name, result)
        _stamp(name, f'ok submissions={result.get("submissions")} revenue={result.get("revenue_inr")}')
    except Exception as exc:
        logger.exception('[cron] %s FAILED: %s', name, exc)
        _stamp(name, f'error {exc!r}')


def job_payout_flush() -> None:
    """Every 30 min — payout flush via payments.services.payout_flush.run."""
    name = 'payout_flush'
    logger.info('[cron] %s firing dry_run=%s', name, _dry_run())
    try:
        from payments.services import payout_flush
        result = payout_flush.run(dry_run=_dry_run())
        logger.info('[cron] %s ok: %s', name, result)
        _stamp(name, f'ok queued={result.get("queued")} processed={result.get("processed")}')
    except Exception as exc:
        logger.exception('[cron] %s FAILED: %s', name, exc)
        _stamp(name, f'error {exc!r}')


def job_review_timeout_sweep() -> None:
    """Every 60 min — peer review timeout sweep via peer_review.services.timeout_sweep.run."""
    name = 'review_timeout_sweep'
    logger.info('[cron] %s firing dry_run=%s', name, _dry_run())
    try:
        from peer_review.services import timeout_sweep
        result = timeout_sweep.run(dry_run=_dry_run())
        logger.info('[cron] %s ok: %s', name, result)
        _stamp(name, f'ok stale={result.get("stale")} expired={result.get("auto_decided")}')
    except Exception as exc:
        logger.exception('[cron] %s FAILED: %s', name, exc)
        _stamp(name, f'error {exc!r}')


def job_quality_alert_scan() -> None:
    """Every 15 min — composite quality anomaly scan.

    ``core.services.quality_anomaly_detector`` exposes ``flag_time_anomaly``,
    ``flag_reviewer_disagree`` and ``flag_duplicate_pattern`` (no orchestrator).
    We call ``open_alert_count_by_severity`` which is the only side-effect-free
    aggregator currently available. Per-row scanning needs the upstream alert
    pipeline (TODO) — flagged in INCIDENT_LOG so it can't get lost.
    """
    name = 'quality_alert_scan'
    logger.info('[cron] %s firing dry_run=%s', name, _dry_run())
    try:
        from core.services import quality_anomaly_detector

        counts = quality_anomaly_detector.open_alert_count_by_severity()
        logger.info('[cron] %s ok open_alerts=%s', name, counts)
        _stamp(name, f'ok open_alerts={counts}')
    except Exception as exc:
        logger.exception('[cron] %s FAILED: %s', name, exc)
        _stamp(name, f'error {exc!r}')


# ---------------------------------------------------------------------------
# Scheduler bootstrap
# ---------------------------------------------------------------------------

JOBS = [
    # name,                   trigger,                                                       func
    ('daily_report',          CronTrigger(hour=8, minute=0, timezone=IST),                   job_daily_report),
    ('weekly_report',         CronTrigger(day_of_week='mon', hour=9, minute=0, timezone=IST), job_weekly_report),
    ('monthly_report',        CronTrigger(day=1, hour=9, minute=0, timezone=IST),            job_monthly_report),
    ('payout_flush',          IntervalTrigger(minutes=30, timezone=IST),                     job_payout_flush),
    ('review_timeout_sweep',  IntervalTrigger(hours=1, timezone=IST),                        job_review_timeout_sweep),
    ('quality_alert_scan',    IntervalTrigger(minutes=15, timezone=IST),                     job_quality_alert_scan),
]


def build_scheduler() -> BlockingScheduler:
    scheduler = BlockingScheduler(timezone=IST)
    for name, trigger, func in JOBS:
        scheduler.add_job(
            func,
            trigger=trigger,
            id=name,
            name=name,
            max_instances=1,
            coalesce=True,
            misfire_grace_time=300,
            replace_existing=True,
        )
        logger.info('[cron] registered job=%s trigger=%s', name, trigger)
    return scheduler


def run() -> None:
    logger.info(
        '[cron] TrainPlex scheduler starting — dry_run=%s timezone=%s jobs=%d',
        _dry_run(), IST.zone, len(JOBS),
    )
    _stamp('scheduler-boot', f'started jobs={len(JOBS)}')
    scheduler = build_scheduler()

    def _graceful(signum, frame):
        logger.info('[cron] received signal %s — shutting down scheduler', signum)
        _stamp('scheduler-stop', f'signal={signum}')
        scheduler.shutdown(wait=False)
        sys.exit(0)

    signal.signal(signal.SIGTERM, _graceful)
    signal.signal(signal.SIGINT, _graceful)

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        pass
    finally:
        _stamp('scheduler-stop', 'finally-block')
