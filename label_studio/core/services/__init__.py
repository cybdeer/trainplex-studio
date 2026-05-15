"""TrainPlex core services package.

Phase 1 Step 4.2-7. Houses service-layer modules used by `core/views_*.py`
endpoints — broadcast, outbound integrations, etc. Keeping the
business-logic separate from the DRF view layer means the same primitives
can be reused from management commands, RQ jobs, or unit tests without
spinning up an HTTP client.
"""
