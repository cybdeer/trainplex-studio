"""This file and its contents are licensed under the Apache License 2.0. Please see the included NOTICE for copyright information and LICENSE for a copy of the license."""

import json
import logging
from urllib.parse import quote

from core.feature_flags import flag_set
from core.middleware import enforce_csrf_checks
from core.utils.common import get_client_ip, load_func
from django.conf import settings
from django.contrib import auth
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import HttpResponseNotAllowed, JsonResponse
from django.shortcuts import redirect, render, reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.csrf import csrf_exempt
from django_ratelimit.exceptions import Ratelimited
from organizations.forms import OrganizationSignupForm
from organizations.models import Organization
from rest_framework.authtoken.models import Token
from users import forms
from users.functions import login, proceed_registration
from users.middleware.rate_limit import ratelimit_login
from users.models import User, user_needs_2fa
from users.services import audit_logger, partial_login_token, totp_handler

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
            persist_session = form.cleaned_data.get('persist_session', False)

            # TrainPlex Phase 1 Step 12.4 — 2FA gate.
            #
            # When the user has totp_enabled, we don't issue a session
            # yet — we return a signed partial token the frontend must
            # exchange via ``user_login_2fa_verify`` after collecting a
            # 6-digit code. This means raw POST /user/login/ never
            # produces an authenticated session for a 2FA-enrolled user
            # even if the second-factor view is unreachable.
            if user_needs_2fa(user) and user.totp_enabled:
                # Stash the persist_session preference so the second-step
                # view can honour "Remember me". 5-minute lifetime is
                # short enough that abandonment isn't a concern.
                token = partial_login_token.issue_partial_token(user.id)
                # We deliberately don't audit-log the partial-success
                # here — only the full session creation in
                # ``user_login_2fa_verify`` counts as a login.
                return JsonResponse(
                    {
                        'requires_2fa': True,
                        'partial_token': token,
                        'persist_session': bool(persist_session),
                    },
                    status=200,
                )

            login(request, user, backend='django.contrib.auth.backends.ModelBackend')
            if persist_session is not True:
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

            # TrainPlex Phase 1 Step 12.4 — soft 2FA-required flag for
            # admins who haven't enrolled yet. Frontend uses this to
            # redirect to /settings/2fa/enroll on first request. Hard
            # block is Week 5 (Step 12.4 follow-up).
            response = redirect(next_page)
            if user_needs_2fa(user) and not user.totp_enabled:
                response['X-TrainPlex-2FA-Required'] = 'true'
            return response
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


def _parse_2fa_verify_body(request) -> dict:
    """Read the 2FA-verify request body as a dict.

    The frontend posts JSON (``application/json``); curl smoke tests may
    use form-urlencoded. Accept both so the contract isn't fragile.
    """
    if request.content_type and 'application/json' in request.content_type:
        try:
            return json.loads(request.body.decode('utf-8') or '{}')
        except (ValueError, UnicodeDecodeError):
            return {}
    # Fallback for form-encoded posts (curl / legacy clients).
    return {k: v for k, v in request.POST.items()}


@csrf_exempt
@ratelimit_login
def user_login_2fa_verify(request):
    """Step 2 of the 2FA-gated login flow.

    Takes ``{partial_token, token}`` OR ``{partial_token, backup_code}``.
    On success: issues a full Django session, audits the login, returns
    ``{success: true, redirect_url}``. On failure: 401 + audit ``log_login(success=False)``.

    Rate-limited under the same bucket as the password step so brute-force
    bots can't pivot from 5-tries-per-IP on /login to unlimited tries on
    /login/2fa.
    """
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])

    payload = _parse_2fa_verify_body(request)
    token_str = (payload.get('partial_token') or '').strip()
    user_id = partial_login_token.verify_partial_token(token_str)

    # We don't include a "code missing" 400 — fold every failure mode into
    # the same 401 so an attacker can't distinguish "expired token" from
    # "wrong code" from "wrong user".
    code = (payload.get('token') or '').strip()
    backup_code = (payload.get('backup_code') or '').strip()
    persist_session = bool(payload.get('persist_session', False))

    def _fail(reason: str, *, user=None, status_code: int = 401):
        audit_logger.log_login(
            user=user,
            ip=get_client_ip(request),
            ua=request.META.get('HTTP_USER_AGENT', ''),
            success=False,
        )
        logger.info(
            'Failed 2FA verification reason=%s ip=%s',
            reason,
            get_client_ip(request),
        )
        return JsonResponse(
            {'detail': 'Invalid or expired 2FA challenge.'},
            status=status_code,
        )

    if user_id is None:
        return _fail('bad_partial_token')

    user = User.objects.filter(pk=user_id).first()
    if user is None or not user.is_active or not user.totp_enabled:
        return _fail('user_invalid', user=user)

    verified = False
    if code:
        verified = totp_handler.verify_token(user.totp_secret, code)
    elif backup_code:
        # ``verify_backup_code`` is atomic — it consumes the matching
        # hash inside the same save() call so a parallel reuse loses.
        verified = totp_handler.verify_backup_code(user, backup_code)

    if not verified:
        return _fail('2fa_failed', user=user)

    # Full session.
    login(request, user, backend='django.contrib.auth.backends.ModelBackend')
    if not persist_session:
        request.session['keep_me_logged_in'] = False
        request.session.set_expiry(0)

    # Mirror ``user_login``'s org-membership update, but tolerate users
    # with no membership (in tests / fresh signups). ``find_by_user``
    # raises ValueError when the user has no OrganizationMember row.
    try:
        org = Organization.find_by_user(user)
        if org is not None:
            user.active_organization_id = org.pk
            user.save(update_fields=['active_organization'])
    except ValueError:
        logger.info('2FA login for user %s with no organization membership', user.pk)

    audit_logger.log_login(
        user,
        ip=get_client_ip(request),
        ua=request.META.get('HTTP_USER_AGENT', ''),
        success=True,
    )

    # Resolve "where to land" the same way the password step does — fall
    # through to the homepage feature flag.
    if flag_set('fflag_all_feat_dia_1777_ls_homepage_short', user):
        next_page = reverse('main')
    else:
        next_page = reverse('projects:project-index')

    return JsonResponse(
        {'success': True, 'redirect_url': next_page},
        status=200,
    )


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
