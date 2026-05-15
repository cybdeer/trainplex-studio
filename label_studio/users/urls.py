"""This file and its contents are licensed under the Apache License 2.0. Please see the included NOTICE for copyright information and LICENSE for a copy of the license."""

from os.path import join

from django.conf import settings
from django.conf.urls import include
from django.urls import path, re_path
from django.views.static import serve
from rest_framework import routers
from users import api, api_2fa, views
from users.product_tours import api as product_tours_api

router = routers.DefaultRouter()
router.register(r'users', api.UserAPI, basename='user')

urlpatterns = [
    re_path(r'^api/', include(router.urls)),
    # Authentication
    path('user/login/', views.user_login, name='user-login'),
    # TrainPlex Phase 1 Step 12.4 — 2FA second-step verifier. Same path
    # family as ``user-login`` so it's findable + same ratelimit_login
    # decorator caps total IP traffic.
    path('user/login/2fa', views.user_login_2fa_verify, name='user-login-2fa'),
    path('user/signup/', views.user_signup, name='user-signup'),
    path('user/account/', views.user_account, name='user-account'),
    path('user/account/<sub_path>', views.user_account, name='user-account-anything'),
    re_path(r'^logout/?$', views.logout, name='logout'),
    # Token
    path('api/current-user/reset-token/', api.UserResetTokenAPI.as_view(), name='current-user-reset-token'),
    path('api/current-user/token', api.UserGetTokenAPI.as_view(), name='current-user-token'),
    path('api/current-user/whoami', api.UserWhoAmIAPI.as_view(), name='current-user-whoami'),
    # Product tours
    path('api/current-user/product-tour', product_tours_api.ProductTourAPI.as_view(), name='product-tour'),
    path('api/current-user/hotkeys/', api.UserHotkeysAPI.as_view(), name='current-user-hotkeys'),
    # TrainPlex Phase 1 Step 12.4 — 2FA enrollment + disable. Gate is
    # admin + qa_lead only, enforced inside the views (see _gate_2fa_roles).
    path(
        'api/v1/users/me/2fa/enroll/start',
        api_2fa.TwoFactorEnrollStartAPI.as_view(),
        name='current-user-2fa-enroll-start',
    ),
    path(
        'api/v1/users/me/2fa/enroll/confirm',
        api_2fa.TwoFactorEnrollConfirmAPI.as_view(),
        name='current-user-2fa-enroll-confirm',
    ),
    path(
        'api/v1/users/me/2fa/disable',
        api_2fa.TwoFactorDisableAPI.as_view(),
        name='current-user-2fa-disable',
    ),
]

# When CLOUD_FILE_STORAGE_ENABLED is set, avatars are uploaded to cloud storage with a different URL pattern.
# This local serving pattern is unnecessary for environments with cloud storage enabled.
if not settings.CLOUD_FILE_STORAGE_ENABLED:
    urlpatterns += [
        # avatars
        re_path(
            r'^data/' + settings.AVATAR_PATH + '/(?P<path>.*)$',
            serve,
            kwargs={'document_root': join(settings.MEDIA_ROOT, settings.AVATAR_PATH)},
        ),
    ]
