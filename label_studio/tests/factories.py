"""TrainPlex test factories (Phase 1 Step 9.1).

factory-boy factories for the most commonly used models in TrainPlex Studio tests.
Use these in unit tests so each test owns a deterministic but isolated set of
fixtures — avoid relying on the legacy `business_client` / `setup_project_*`
helpers from `label_studio/tests/conftest.py` for any new test that doesn't
actually need the heavy autouse mocks (S3, GCS, Azure, Redis, ML).

Example:

    from label_studio.tests.factories import UserFactory, ProjectFactory

    @pytest.mark.django_db
    def test_something(db):
        admin = UserFactory(role='admin')
        project = ProjectFactory(created_by=admin)
        assert project.organization.created_by == admin

Note: pytest-django gives us `db` for transactional rollback; factory-boy's
DjangoModelFactory uses `Model.objects.create` (or `manager.create`) so each
build hits the test DB which gets rolled back at the end of the test.
"""

import factory
from factory.django import DjangoModelFactory

from organizations.models import Organization
from projects.models import Project
from tasks.models import Annotation, Task
from users.models import User


class UserFactory(DjangoModelFactory):
    """Generate a unique TrainPlex User. Default role is 'trainer'.

    Override role via:  UserFactory(role='admin')

    Each call generates a unique email + username via factory.Sequence so multiple
    users created in the same test never collide on the unique-email index.
    """

    class Meta:
        model = User
        django_get_or_create = ('email',)

    email = factory.Sequence(lambda n: f'user{n}@trainplex.test')
    username = factory.Sequence(lambda n: f'user{n}')
    first_name = factory.Faker('first_name')
    last_name = factory.Faker('last_name')
    role = 'trainer'  # ROLE_CHOICES default — override in callers as needed
    is_active = True

    @classmethod
    def _create(cls, model_class, *args, **kwargs):
        """Use create_user so password hashing + post_save Token creation runs."""
        password = kwargs.pop('password', 'testpass123')
        return model_class.objects.create_user(password=password, **kwargs)


class OrganizationFactory(DjangoModelFactory):
    """Generate a unique TrainPlex Organization.

    `created_by` is auto-built as a fresh `UserFactory`. The factory uses
    `Organization.create_organization` (via the post-generation hook below) so
    the OrganizationMember row gets created and the JWT settings get initialized
    the same way the real signup flow does it.
    """

    class Meta:
        model = Organization
        skip_postgeneration_save = True

    title = factory.Sequence(lambda n: f'TrainPlex Org {n}')
    created_by = factory.SubFactory(UserFactory, role='admin')

    @classmethod
    def _create(cls, model_class, *args, **kwargs):
        """Route through `Organization.create_organization` to ensure membership + JWT init."""
        title = kwargs.pop('title')
        created_by = kwargs.pop('created_by')
        org = Organization.create_organization(title=title, created_by=created_by, **kwargs)
        # Wire active_organization on the owner so api endpoints that gate on it pass.
        created_by.active_organization = org
        created_by.save(update_fields=['active_organization'])
        return org


class ProjectFactory(DjangoModelFactory):
    """Generate a minimal valid Project.

    The default `label_config` is a no-op `<View></View>` so the validator doesn't
    complain; callers building label-config-sensitive tests should pass their own
    config explicitly.
    """

    class Meta:
        model = Project

    title = factory.Sequence(lambda n: f'Project {n}')
    description = ''
    label_config = '<View></View>'
    organization = factory.SubFactory(OrganizationFactory)
    created_by = factory.LazyAttribute(lambda obj: obj.organization.created_by)


class TaskFactory(DjangoModelFactory):
    """Generate a Task tied to a Project (subfactory)."""

    class Meta:
        model = Task

    data = factory.LazyFunction(lambda: {'text': 'sample input'})
    project = factory.SubFactory(ProjectFactory)


class AnnotationFactory(DjangoModelFactory):
    """Generate an Annotation tied to a Task + its Project + a User.

    `completed_by` defaults to the project's creator; override if a different
    annotator is needed for the scenario under test.
    """

    class Meta:
        model = Annotation

    task = factory.SubFactory(TaskFactory)
    project = factory.LazyAttribute(lambda obj: obj.task.project)
    completed_by = factory.LazyAttribute(lambda obj: obj.task.project.created_by)
    result = factory.LazyFunction(list)  # empty annotation result by default
    was_cancelled = False
    ground_truth = False
