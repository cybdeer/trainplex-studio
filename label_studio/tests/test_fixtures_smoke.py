"""Smoke tests for the TrainPlex pytest fixture infrastructure (Phase 1 Step 9.1).

These tests don't exercise business logic — they only verify that the fixtures
defined in `label_studio/conftest.py` and the factory-boy factories in
`label_studio/tests/factories.py` actually instantiate correctly and produce
objects with the expected role / type. If these break, every downstream test
relying on these fixtures will also break, so this file catches infra rot
early in CI.
"""

import pytest
from rest_framework.test import APIClient

from label_studio.tests.factories import (
    AnnotationFactory,
    OrganizationFactory,
    ProjectFactory,
    TaskFactory,
    UserFactory,
)


# ---------------------------------------------------------------------------
# Role fixture smoke tests (from label_studio/conftest.py)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
@pytest.mark.rbac
class TestRoleFixtures:
    """The four ROLE_CHOICES fixtures create users with the right role + sane defaults."""

    def test_admin_user_has_admin_role(self, admin_user):
        assert admin_user.role == 'admin'
        assert admin_user.is_active is True
        assert admin_user.email  # non-empty

    def test_trainer_user_has_trainer_role(self, trainer_user):
        assert trainer_user.role == 'trainer'

    def test_reviewer_user_has_reviewer_role(self, reviewer_user):
        assert reviewer_user.role == 'reviewer'

    def test_qa_lead_user_has_qa_lead_role(self, qa_lead_user):
        assert qa_lead_user.role == 'qa_lead'

    def test_role_fixtures_create_distinct_users(self, admin_user, trainer_user, reviewer_user, qa_lead_user):
        """All four role fixtures co-exist without colliding on the unique email index."""
        emails = {admin_user.email, trainer_user.email, reviewer_user.email, qa_lead_user.email}
        assert len(emails) == 4


# ---------------------------------------------------------------------------
# API client fixture smoke tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestApiClientFixtures:
    """`api_client` and `authenticated_client` produce usable DRF APIClient instances."""

    def test_api_client_is_drf_apiclient(self, api_client):
        assert isinstance(api_client, APIClient)

    def test_authenticated_client_is_drf_apiclient(self, authenticated_client):
        assert isinstance(authenticated_client, APIClient)

    def test_authenticated_client_can_hit_api_without_500(self, authenticated_client):
        """`GET /api/projects/` should NOT 500 — 200 (empty list) or 4xx is acceptable.

        The exact status depends on org / permissions state — the only thing that
        would indicate a busted fixture is a 500 (Django server error).
        """
        response = authenticated_client.get('/api/projects/')
        assert response.status_code < 500, f'authenticated_client got server error {response.status_code}'


# ---------------------------------------------------------------------------
# Organization fixture smoke test
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestOrganizationFixture:
    """`organization` fixture creates an Org owned by admin_user."""

    def test_organization_owned_by_admin(self, organization, admin_user):
        assert organization.created_by_id == admin_user.id
        assert organization.title  # non-empty
        # admin_user.active_organization should be wired up by the fixture
        admin_user.refresh_from_db()
        assert admin_user.active_organization_id == organization.id


# ---------------------------------------------------------------------------
# factory-boy smoke tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestFactories:
    """The factory-boy factories build valid model instances."""

    def test_user_factory_default_role_is_trainer(self):
        user = UserFactory()
        assert user.role == 'trainer'
        assert user.email
        assert user.pk is not None

    def test_user_factory_role_override(self):
        admin = UserFactory(role='admin')
        assert admin.role == 'admin'

    def test_user_factory_creates_unique_users(self):
        a, b = UserFactory(), UserFactory()
        assert a.email != b.email
        assert a.pk != b.pk

    def test_organization_factory_creates_org_with_member(self):
        org = OrganizationFactory()
        assert org.created_by is not None
        assert org.has_user(org.created_by)

    def test_project_factory_builds_minimal_project(self):
        project = ProjectFactory()
        assert project.organization is not None
        assert project.created_by == project.organization.created_by
        assert project.label_config == '<View></View>'

    def test_task_factory_builds_task_on_project(self):
        task = TaskFactory()
        assert task.project is not None
        assert task.data == {'text': 'sample input'}

    def test_annotation_factory_builds_annotation_on_task(self):
        ann = AnnotationFactory()
        assert ann.task is not None
        assert ann.project == ann.task.project
        assert ann.completed_by == ann.task.project.created_by
