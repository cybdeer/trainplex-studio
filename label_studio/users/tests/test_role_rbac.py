"""Unit tests for TrainPlex RBAC: User.role field + @require_role decorator.

Covers:
- Default role on new users is 'trainer'
- Each of the 4 valid role values can be assigned
- Invalid role rejected by model.full_clean() validation
- @require_role allows users in the allowed_roles set
- @require_role denies users outside the allowed_roles set
- @require_role denies unauthenticated requests
"""

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import ValidationError
from django.test import TestCase
from rest_framework.exceptions import PermissionDenied
from rest_framework.test import APIRequestFactory, force_authenticate
from users.decorators import require_role

User = get_user_model()


class _FakeView:
    """Bare-minimum view stub for invoking @require_role-decorated methods."""

    @require_role(['admin'])
    def admin_only(self, request):
        return 'ok'

    @require_role(['admin', 'qa_lead'])
    def admin_or_qa(self, request):
        return 'ok'


@pytest.mark.django_db
class TestUserRoleField(TestCase):
    """Tests for the User.role model field."""

    def test_default_role_is_trainer(self):
        """A new user without an explicit role defaults to 'trainer'."""
        user = User.objects.create_user(
            email='default-role@example.com',
            username='default-role',
            password='testpass123',
        )
        self.assertEqual(user.role, 'trainer')

    def test_role_can_be_set_to_each_valid_value(self):
        """Each of the four ROLE_CHOICES values is accepted and persisted."""
        valid_roles = ['trainer', 'reviewer', 'qa_lead', 'admin']
        for role in valid_roles:
            user = User.objects.create_user(
                email=f'{role}@example.com',
                username=role,
                password='testpass123',
                role=role,
            )
            user.refresh_from_db()
            self.assertEqual(user.role, role, f'Expected role={role}, got {user.role}')

    def test_invalid_role_rejected_by_full_clean(self):
        """An out-of-choices role value fails Django model validation."""
        user = User(
            email='bad-role@example.com',
            username='bad-role',
            role='superuser',  # not in ROLE_CHOICES
        )
        with self.assertRaises(ValidationError) as cm:
            user.full_clean()
        self.assertIn('role', cm.exception.message_dict)


@pytest.mark.django_db
class TestRequireRoleDecorator(TestCase):
    """Tests for the @require_role decorator."""

    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = _FakeView()

        self.admin = User.objects.create_user(
            email='rbac-admin@example.com',
            username='rbac-admin',
            password='testpass123',
            role='admin',
        )
        self.trainer = User.objects.create_user(
            email='rbac-trainer@example.com',
            username='rbac-trainer',
            password='testpass123',
            role='trainer',
        )
        self.qa_lead = User.objects.create_user(
            email='rbac-qa@example.com',
            username='rbac-qa',
            password='testpass123',
            role='qa_lead',
        )

    def test_allows_user_with_matching_role(self):
        """Admin user passes @require_role(['admin'])."""
        request = self.factory.get('/fake/')
        force_authenticate(request, user=self.admin)
        # APIRequestFactory + force_authenticate sets request.user only after
        # auth runs. For our bare-method test we attach the user directly:
        request.user = self.admin

        result = self.view.admin_only(request)
        self.assertEqual(result, 'ok')

    def test_allows_user_in_multi_role_set(self):
        """qa_lead user passes @require_role(['admin', 'qa_lead'])."""
        request = self.factory.get('/fake/')
        request.user = self.qa_lead

        result = self.view.admin_or_qa(request)
        self.assertEqual(result, 'ok')

    def test_denies_user_with_disallowed_role(self):
        """Trainer user is denied @require_role(['admin'])."""
        request = self.factory.get('/fake/')
        request.user = self.trainer

        with self.assertRaises(PermissionDenied) as cm:
            self.view.admin_only(request)
        # Error message should mention required role + user's role
        self.assertIn('admin', str(cm.exception))
        self.assertIn('trainer', str(cm.exception))

    def test_denies_unauthenticated_user(self):
        """Anonymous user is denied any @require_role-protected method."""
        request = self.factory.get('/fake/')
        request.user = AnonymousUser()

        with self.assertRaises(PermissionDenied) as cm:
            self.view.admin_only(request)
        self.assertIn('Login required', str(cm.exception))
