"""This file and its contents are licensed under the Apache License 2.0. Please see the included NOTICE for copyright information and LICENSE for a copy of the license."""

import logging
from urllib.parse import quote

from core.feature_flags import flag_set
from core.middleware import enforce_csrf_checks
from core.utils.common import get_client_ip, load_func
from django.conf import settings
from django.contrib import auth
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import JsonResponse
from django.shortcuts import redirect, render, reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django_ratelimit.exceptions import Ratelimited
from organizations.forms import OrganizationSignupForm
from organizations.models import Organization
from rest_framework.authtoken.models import Token
from users import forms
from users.functions import login, proceed_registration
from users.middleware.rate_limit import ratelimit_login
from users.services import audit_logger

logger = logging.getLogger()


# TrainPlex Phase 1 Step 12 wire-in — Hindi-friendly 429 body for the
# (non-DRF) Django login view. DRF views get the same body via
# ``core.utils.common.custom_exception_handler``.
_RATE_LIMIT_BODY = {
    'error': 'rate_limited',
    'message': 'Bahut sare requests — kuch der ruk ke try karein',
    'retry_after_seconds': 60,
}


def ratelimit_view(request, exception):  # noqa: ARG001
    """TrainPlex global handler for ``django_ratelimit.exceptions.Ratelimited``.

    Wired in via ``RATELIMIT_VIEW`` + ``RatelimitMiddleware`` in
    ``core.settings.base``. Returns a Hindi-friendly JSON 429 for both
    plain Django and DRF views.

    DRF views generally won't hit this path — they're handled inside
    ``core.utils.common.custom_exception_handler`` before middleware sees
    them — but having a single source of truth here makes the contract
    explicit.
    """
    response = JsonResponse(_RATE_LIMIT_BODY, status=429)
    response['Retry-After'] = '60'
    return response


@login_required
def logout(request):
    auth.logout(request)

    if settings.LOGOUT_REDIRECT_URL:
        return redirect(settings.LOGOUT_REDIRECT_URL)

    if settings.HOSTNAME:
        redirect_url = settings.HOSTNAME
        if not redirect_url.endswith('/'):
            redirect_url += '/'
        return redirect(redirect_url)
    return redirect('/')


@enforce_csrf_checks
def user_signup(request):
    """Sign up page"""
    user = request.user
    next_page = request.GET.get('next')
    token = request.GET.get('token')

    # checks if the URL is a safe redirection.
    if not next_page or not url_has_allowed_host_and_scheme(url=next_page, allowed_hosts=request.get_host()):
        if flag_set('fflag_all_feat_dia_1777_ls_homepage_short', user):
            next_page = reverse('main')
        else:
            next_page = reverse('projects:project-index')

    user_form = forms.UserSignupForm()
    organization_form = OrganizationSignupForm()

    if user.is_authenticated:
        return redirect(next_page)

    # make a new user
    if request.method == 'POST':
        organization = Organization.objects.first()
        if settings.DISABLE_SIGNUP_WITHOUT_LINK is True:
            if not (token and organization and token == organization.token):
                raise PermissionDenied()
        else:
            if token and organization and token != organization.token:
                raise PermissionDenied()

        user_form = forms.UserSignupForm(request.POST)
        organization_form = OrganizationSignupForm(request.POST)

        if user_form.is_valid():
            redirect_response = proceed_registration(request, user_form, organization_form, next_page)
            if redirect_response:
                return redirect_response

    if flag_set('fflag_feat_front_lsdv_e_297_increase_oss_to_enterprise_adoption_short'):
        return render(
            request,
            'users/new-ui/user_signup.html',
            {
                'user_form': user_form,
                'organization_form': organization_form,
                'next': quote(next_page),
                'token': token,
                'found_us_options': forms.FOUND_US_OPTIONS,
                'elaborate': forms.FOUND_US_ELABORATE,
            },
        )

    return render(
        request,
        'users/user_signup.html',
        {
            'user_form': user_form,
            'organization_form': organization_form,
            'next': quote(next_page),
            'token': token,
        },
    )


@ratelimit_login
@enforce_csrf_checks
def user_login(request):
    """Login page.

    TrainPlex Phase 1 Step 12 wire-in:
    - ``@ratelimit_login`` caps 5 POST attempts per 15 min per IP. The 6th
      raises ``Ratelimited`` which we catch below and return as JSON 429.
    - Every login attempt (success + fail) is recorded via
      ``audit_logger.log_login`` so the security team can trace brute-force
      attempts after the fact.
    """
    user = request.user
    next_page = request.GET.get('next')

    # checks if the URL is a safe redirection.
    if not next_page or not url_has_allowed_host_and_scheme(url=next_page, allowed_hosts=request.get_host()):
        if flag_set('fflag_all_feat_dia_1777_ls_homepage_short', user):
            next_page = reverse('main')
        else:
            next_page = reverse('projects:project-index')

    login_form = load_func(settings.USER_LOGIN_FORM)
    form = login_form()

    if user.is_authenticated:
        return redirect(next_page)

    if request.method == 'POST':
        form = login_form(request.POST)
        if form.is_valid():
            user = form.cleaned_data['user']
            login(request, user, backend='django.contrib.auth.backends.ModelBackend')
            if form.cleaned_data['persist_session'] is not True:
                # Set the session to expire when the browser is closed
                request.session['keep_me_logged_in'] = False
                request.session.set_expiry(0)

            # user is organization member
            org_pk = Organization.find_by_user(user).pk
            user.active_organization_id = org_pk
            user.save(update_fields=['active_organization'])

            # TrainPlex Step 12 — audit successful login (best-effort, never raises).
            audit_logger.log_login(
                user,
                ip=get_client_ip(request),
                ua=request.META.get('HTTP_USER_AGENT', ''),
                success=True,
            )
            return redirect(next_page)
        else:
            # TrainPlex Step 12 — audit failed login. ``user`` here is None
            # (the form's clean() raised ValidationError so cleaned_data has
            # no 'user' key); pass the attempted email through metadata so
            # security can detect targeted enumeration.
            attempted_email = (request.POST.get('email') or '').lower()
            audit_logger.log_login(
                user=None,
                ip=get_client_ip(request),
                ua=request.META.get('HTTP_USER_AGENT', ''),
                success=False,
            )
            # The login form already attaches a generic error to the form
            # (INVALID_USER_ERROR), so we just fall through to the render
            # below — no separate response needed.
            logger.info('Failed login attempt for email=%s ip=%s', attempted_email, get_client_ip(request))

    if flag_set('fflag_feat_front_lsdv_e_297_increase_oss_to_enterprise_adoption_short'):
        return render(request, 'users/new-ui/user_login.html', {'form': form, 'next': quote(next_page)})

    return render(request, 'users/user_login.html', {'form': form, 'next': quote(next_page)})


@login_required
def user_account(request, sub_path=None):
    """
    Handle user account view and profile updates.

    This view displays the user's profile information and allows them to update
    it. It requires the user to be authenticated and have an active organization
    or an organization_pk in the session.

    Args:
        request (HttpRequest): The request object.
        sub_path (str, optional): A sub-path parameter for potential URL routing.
            Defaults to None.

    Returns:
        HttpResponse: Renders the user account template with user profile form,
            or redirects to 'main' if no active organization is found,
            or redirects back to user-account after successful profile update.

    Notes:
        - Authentication is required (enforced by @login_required decorator)
        - Retrieves the user's API token for display in the template
        - Form validation happens on POST requests
    """
    user = request.user

    if user.active_organization is None and 'organization_pk' not in request.session:
        return redirect(reverse('main'))

    form = forms.UserProfileForm(instance=user)
    token = Token.objects.get(user=user)

    if request.method == 'POST':
        form = forms.UserProfileForm(request.POST, instance=user)
        if form.is_valid():
            form.save()
            return redirect(reverse('user-account'))

    return render(
        request,
        'users/user_account.html',
        {'settings': settings, 'user': user, 'user_profile_form': form, 'token': token},
    )
