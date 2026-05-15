"""
Root conftest for the label_studio package.

Provides:
- `clear_current_context_after_test` autouse — clears thread-local CurrentContext
  after every test to prevent FK violations on Postgres (User rows are rolled back
  but the thread-local can still hold a stale User instance, which the next test's
  FSM trigger would write as triggered_by_id and blow up with IntegrityError).
- TrainPlex RBAC role fixtures (`admin_user`, `trainer_user`, `reviewer_user`,
  `qa_lead_user`) — one user per ROLE_CHOICES value, for Phase 1 Step 1.4-A RBAC tests.
- `organization` — a single test Organization owned by `admin_user`.
- `api_client` — an unauthenticated DRF APIClient.
- `authenticated_client` — DRF APIClient logged in as `admin_user`.

These fixtures live in the root conftest (NOT in `label_studio/tests/conftest.py`)
so unit tests under `label_studio/<app>/tests/` can use them without inheriting the
heavy autouse mocks (S3/GCS/Azure/Redis/ML) that the legacy integration suite
in `label_studio/tests/conftest.py` sets up.
"""

import pytest


@pytest.fixture(autouse=True)
def clear_current_context_after_test():
    """Clear thread-local CurrentContext after each test to prevent FK violations on Postgres."""
    yield
    from core.current_request import CurrentContext

    CurrentContext.clear()


# ---------------------------------------------------------------------------
# TrainPlex RBAC role fixtures (Phase 1 Step 9.1)
# ---------------------------------------------------------------------------


def _make_user(role: str, email: str | None = None, username: str | None = None):
    """Create a User with the given TrainPlex role.

    Kept private (underscore) so test code goes through the named fixtures below.
    """
    from django.contrib.auth import get_user_model

    User = get_user_model()
    return User.objects.create_user(
        email=email or f'{role}@trainplex.test',
        username=username or role,
        password='testpass123',
        role=role,
    )


@pytest.fixture
def admin_user(db):
    """Create a User with role='admin'."""
    return _make_user('admin')


@pytest.fixture
def trainer_user(db):
    """Create a User with role='trainer' (the default role)."""
    return _make_user('trainer')


@pytest.fixture
def reviewer_user(db):
    """Create a User with role='reviewer'."""
    return _make_user('reviewer')


@pytest.fixture
def qa_lead_user(db):
    """Create a User with role='qa_lead'."""
    return _make_user('qa_lead')


@pytest.fixture
def organization(db, admin_user):
    """Create a test Organization owned by `admin_user`."""
    from organizations.models import Organization

    org = Organization.create_organization(created_by=admin_user, title='TrainPlex Test Org')
    admin_user.active_organization = org
    admin_user.save(update_fields=['active_organization'])
    return org


@pytest.fixture
def api_client():
    """Return an unauthenticated DRF APIClient."""
    from rest_framework.test import APIClient

    return APIClient()


@pytest.fixture
def authenticated_client(db, admin_user, organization):
    """Return a DRF APIClient already logged in as `admin_user` (admin role).

    Pulls in the `organization` fixture so the admin has an active_organization,
    which most API endpoints assert on.
    """
    from rest_framework.test import APIClient

    client = APIClient()
    client.force_authenticate(user=admin_user)
    return client
