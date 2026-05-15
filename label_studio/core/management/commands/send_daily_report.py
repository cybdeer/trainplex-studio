"""TrainPlex daily founder report — Django management command.

Phase 1 Step 4.2-10.

Usage
-----
::

    python manage.py send_daily_report                       # yesterday, default recipient
    python manage.py send_daily_report --recipient EMAIL     # override recipient
    python manage.py send_daily_report --date 2026-05-14     # historical
    python manage.py send_daily_report --dry-run             # render only, no send

Defaults
--------
* ``--recipient`` defaults to ``settings.TRAINPLEX_FOUNDER_EMAIL`` (env-driven).
* ``--date`` defaults to yesterday (server TZ).

Cron registration
-----------------
See ``label_studio/core/cron/daily_report.py`` for the systemd-timer and
crontab examples. Production cron registration (django-q / celery beat)
is a Phase 2 founder-env task — flagged TODO at the top of that module.
"""

from __future__ import annotations

import logging
from datetime import datetime

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = (
        'Build + send the TrainPlex daily founder report email. '
        'Phase 1 ships with mock KPI numbers; quality alert + audit log '
        'signals are already real. See core/services/daily_report_email.py.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--recipient',
            type=str,
            default=None,
            help=(
                'Recipient email address. Defaults to '
                'settings.TRAINPLEX_FOUNDER_EMAIL (env-driven). Refuses '
                'to send if neither is set.'
            ),
        )
        parser.add_argument(
            '--date',
            type=str,
            default=None,
            help=(
                'Report date in ISO YYYY-MM-DD. Defaults to yesterday in '
                'the server timezone.'
            ),
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help=(
                'Render the email + log a summary, but DO NOT call '
                'send(). Useful for cron smoke tests.'
            ),
        )

    def handle(self, *args, **options):
        # Late import so Django finishes booting before we touch ORM models.
        from core.services import daily_report_email

        date_arg = options.get('date')
        if date_arg:
            try:
                # Surface a friendly error rather than the raw ValueError
                # from datetime.strptime — easier to diagnose on a cron log.
                datetime.strptime(date_arg, '%Y-%m-%d')
            except ValueError as exc:
                raise CommandError(
                    f'Invalid --date {date_arg!r}; expected YYYY-MM-DD.'
                ) from exc

        try:
            summary = daily_report_email.build_daily_summary(date_arg)
        except Exception as exc:
            raise CommandError(f'Failed to build daily summary: {exc}') from exc

        recipient = options.get('recipient') or getattr(
            settings, 'TRAINPLEX_FOUNDER_EMAIL', None
        )
        if not recipient:
            raise CommandError(
                'No recipient resolved. Pass --recipient EMAIL or set '
                'TRAINPLEX_FOUNDER_EMAIL in the environment.'
            )

        dry_run = bool(options.get('dry_run'))

        try:
            result = daily_report_email.send_daily_report(
                recipient_email=recipient,
                summary=summary,
                dry_run=dry_run,
            )
        except Exception as exc:
            raise CommandError(f'Failed to send daily report: {exc}') from exc

        self.stdout.write(
            self.style.SUCCESS(
                f'Daily report {"rendered (dry-run)" if dry_run else "sent"}: '
                f'recipient={result["recipient"]} '
                f'subject={result["subject"]!r} '
                f'mode={result["mode"]} '
                f'preview_len={result["preview_len"]}'
            )
        )
