"""TrainPlex cron-job documentation modules.

Each file in this package documents one cron-fired job — the schedule, the
ops registration recipe (systemd timer + crontab + django-q / celery beat
equivalents), and the management command it shells out to. These modules
are intentionally documentation-only in Phase 1; production registration
is a founder-env task tracked in the relevant module's TODO.
"""
