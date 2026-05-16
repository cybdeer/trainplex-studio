"""TrainPlex scheduler entry point — fires the 6 cron jobs flagged in Codex M4.

Usage
-----
::

    python manage.py run_scheduler

Lives inside its own container (``scheduler`` service in
docker-compose.override.yml) — separate process from the uwsgi master so
APScheduler doesn't double-start per worker fork.
"""

from __future__ import annotations

import logging

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Start the TrainPlex APScheduler that fires daily/weekly/monthly/etc cron jobs.'

    def handle(self, *args, **options):
        # Configure root logging early so APScheduler + our jobs land in stdout.
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s %(name)s %(levelname)s %(message)s',
        )
        # Late import — let Django finish booting before we touch services.
        from core import scheduler as trainplex_scheduler
        trainplex_scheduler.run()
