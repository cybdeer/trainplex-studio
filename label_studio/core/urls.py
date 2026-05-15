"""This file and its contents are licensed under the Apache License 2.0. Please see the included NOTICE for copyright information and LICENSE for a copy of the license.

URL Configurations

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/2.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from core import views
from core.utils.static_serve import serve
from core.views_alerts import (
    AdminQualityAlertReviewAPI,
    AdminQualityAlertsListAPI,
    AdminQualityAlertsStatsAPI,
)
from core.views_audit import AdminAuditLogAPI
from core.views_search import AdminGlobalSearchAPI
from core.views_broadcast import (
    AdminWhatsAppBroadcastAPI,
    AdminWhatsAppBroadcastHistoryAPI,
    AdminWhatsAppTemplatesAPI,
)
from core.views_bulk_assign import (
    AdminBulkAssignAPI,
    AdminTrainerFilterAPI,
)
from core.views_dashboard import AdminDashboardSnapshotAPI
from core.views_heatmap import AdminHeatmapStateActivityAPI
from core.views_submissions_preview import AdminSubmissionsPreviewAPI
from core.views_template_gallery import (
    AdminProjectWizardCreateAPI,
    AdminTemplateCatalogAPI,
)
from tasks.api_batch import TrainerBatchAPI, TrainerBatchRefreshAPI
from users.api_profile import (
    TrainerLoginHistoryAPI,
    TrainerPasswordChangeAPI,
    TrainerProfileAPI,
    TrainerSessionRevokeAPI,
    TrainerSessionsAPI,
)
from django.conf import settings
from django.conf.urls import include
from django.contrib import admin
from django.http import HttpResponseRedirect
from django.urls import path, re_path
from django.views.generic.base import RedirectView
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularJSONAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
    SpectacularYAMLAPIView,
)

urlpatterns = [
    re_path(r'^$', views.main, name='main'),
    re_path(r'^sw\.js$', views.static_file_with_host_resolver('js/sw.js', content_type='text/javascript')),
    re_path(
        r'^sw-fallback\.js$',
        views.static_file_with_host_resolver('js/sw-fallback.js', content_type='text/javascript'),
    ),
    re_path(r'^favicon\.ico$', RedirectView.as_view(url='/static/images/favicon.ico', permanent=True)),
    re_path(
        r'^label-studio-frontend/(?P<path>.*)$',
        serve,
        kwargs={'document_root': settings.EDITOR_ROOT, 'show_indexes': True},
    ),
    re_path(r'^dm/(?P<path>.*)$', serve, kwargs={'document_root': settings.DM_ROOT, 'show_indexes': True}),
    re_path(
        r'^react-app/(?P<path>.*)$',
        serve,
        kwargs={
            'document_root': settings.REACT_APP_ROOT,
            'show_indexes': True,
            'manifest_asset_prefix': 'react-app',
        },
    ),
    re_path(r'^static/(?P<path>.*)$', serve, kwargs={'document_root': settings.STATIC_ROOT, 'show_indexes': True}),
    re_path(r'^', include('organizations.urls')),
    re_path(r'^', include('projects.urls')),
    re_path(r'^', include('data_import.urls')),
    re_path(r'^', include('data_manager.urls')),
    re_path(r'^', include('data_export.urls')),
    re_path(r'^', include('users.urls')),
    re_path(r'^', include('tasks.urls')),
    re_path(r'^', include('io_storages.urls')),
    re_path(r'^', include('ml.urls')),
    re_path(r'^', include('webhooks.urls')),
    re_path(r'^', include('labels_manager.urls')),
    re_path(r'^', include('fsm.urls')),
    # TrainPlex Phase 1 Step 6 — reviewer queue + consensus engine + QA dispute.
    # Endpoints under /api/v1/reviewer/* (role=reviewer) and /api/v1/qa/*
    # (role=qa_lead) enforced via @require_role. Models live in peer_review app.
    re_path(r'^', include('peer_review.urls')),
    # TrainPlex Phase 1 Step 6.4 + 4.2-5 — Payment Release Flow.
    # /api/v1/payments/wallet (trainer-only, self)
    # /api/v1/payments/payout-queue (admin-only)
    # /api/v1/payments/payout-queue/<id>/retry (admin-only)
    # /api/v1/admin/payment-status (admin-only)
    # Connects to peer_review via ConsensusResult.post_save signal.
    re_path(r'^', include('payments.urls')),
    # TrainPlex Phase 1 Step 7 — Reports + BI suite.
    # All endpoints admin-only (@require_role(['admin'])); data MOCK in Phase 1.
    # /api/v1/admin/reports/founder-weekly[.pdf]
    # /api/v1/admin/reports/leaderboard[.csv]
    # /api/v1/admin/reports/cohorts
    # /api/v1/admin/reports/project-roi[/<id>[.pdf]]
    re_path(r'^', include('reports.urls')),
    re_path(r'version/', views.version_page, name='version'),  # html page
    re_path(r'api/version/', views.version_page, name='api-version'),  # json response
    # TrainPlex — Phase 1 Step 4.2-1: Admin dashboard snapshot (mock data, real wiring in Phase 2)
    path(
        'api/v1/admin/dashboard/snapshot',
        AdminDashboardSnapshotAPI.as_view(),
        name='admin-dashboard-snapshot',
    ),
    # TrainPlex — Phase 1 Step 4.2-2: Admin Project Wizard
    # Step 1 catalog (50 LS native + 10 TrainPlex India custom) + create endpoint.
    path(
        'api/v1/admin/templates/catalog',
        AdminTemplateCatalogAPI.as_view(),
        name='admin-template-catalog',
    ),
    path(
        'api/v1/admin/projects/wizard',
        AdminProjectWizardCreateAPI.as_view(),
        name='admin-project-wizard-create',
    ),
    # TrainPlex — Phase 1 Step 4.2-3: Admin Bulk Task Assign.
    # Filter trainers by state / tier / language / cert, then assign tasks
    # to all matched trainers in one POST. Phase 1 ships a mock plan that
    # logs the per-trainer task count; real LS task creation lands Phase 2.
    # POST is rate-limited to 5 bulk-assigns / hour / admin.
    path(
        'api/v1/admin/trainers/filter',
        AdminTrainerFilterAPI.as_view(),
        name='admin-trainers-filter',
    ),
    path(
        'api/v1/admin/tasks/bulk-assign',
        AdminBulkAssignAPI.as_view(),
        name='admin-bulk-assign',
    ),
    # TrainPlex — Phase 1 Step 4.2-4: Admin Audit Log viewer
    # Paginated read-only view over users.AuditLog. Filters: action, actor email,
    # target_type, success, date range. Admin role only.
    path(
        'api/v1/admin/audit/log',
        AdminAuditLogAPI.as_view(),
        name='admin-audit-log',
    ),
    # TrainPlex — Phase 1 Step 14: Admin Global Search (Cmd+K command palette).
    # Searches trainers, projects, submissions, audit logs, tasks. Admin-only.
    # Mock data in Phase 1; real Postgres FTS (GIN indexes via migration
    # 0006_fulltext_search_indexes) lands in Phase 2 / Step 8.
    path(
        'api/v1/admin/search',
        AdminGlobalSearchAPI.as_view(),
        name='admin-global-search',
    ),
    # TrainPlex — Phase 1 Step 4.2-6: Admin India geographic heatmap.
    # Per-state active trainers + submissions + earnings for the requested period.
    # Mock data in Phase 1; real aggregation lands in Phase 2 (Step 8).
    path(
        'api/v1/admin/heatmap/state-activity',
        AdminHeatmapStateActivityAPI.as_view(),
        name='admin-heatmap-state-activity',
    ),
    # TrainPlex — Phase 1 Step 4.2-7: Admin WhatsApp Broadcast.
    # Templates list, fan-out send (mock AiSensy in Phase 1), and history log.
    # All three are admin-only via @require_role(['admin']). Send is rate-limited
    # to 3 broadcasts per hour per admin.
    path(
        'api/v1/admin/wa/templates',
        AdminWhatsAppTemplatesAPI.as_view(),
        name='admin-wa-templates',
    ),
    path(
        'api/v1/admin/wa/broadcast',
        AdminWhatsAppBroadcastAPI.as_view(),
        name='admin-wa-broadcast',
    ),
    path(
        'api/v1/admin/wa/broadcast/history',
        AdminWhatsAppBroadcastHistoryAPI.as_view(),
        name='admin-wa-broadcast-history',
    ),
    # TrainPlex — Phase 1 Step 4.2-8: Admin Quality Alert Center.
    # Auto-flagged reviewer-disagree / time-anomaly / duplicate-pattern signals
    # are listed, drillable, and resolvable by an admin. Detection mock in
    # Phase 1; real wiring lands Week 5 with peer-review native.
    path(
        'api/v1/admin/quality-alerts',
        AdminQualityAlertsListAPI.as_view(),
        name='admin-quality-alerts-list',
    ),
    path(
        'api/v1/admin/quality-alerts/stats',
        AdminQualityAlertsStatsAPI.as_view(),
        name='admin-quality-alerts-stats',
    ),
    path(
        'api/v1/admin/quality-alerts/<int:alert_id>/review',
        AdminQualityAlertReviewAPI.as_view(),
        name='admin-quality-alert-review',
    ),
    # TrainPlex — Phase 1 Step 4.2-9: Admin Submissions Preview drawer.
    # Recent N submissions (default 10, cap 50) with task/answer/reviewer
    # preview so admin can spot-check fraud / quality at random. Filterable
    # by project_id, trainer_id, status. Mock data in Phase 1; real DB
    # wiring lands in Phase 2 / Step 8.
    path(
        'api/v1/admin/submissions/preview',
        AdminSubmissionsPreviewAPI.as_view(),
        name='admin-submissions-preview',
    ),
    # TrainPlex — Phase 1 Step 1.4-E: Trainer 10-task Batch.
    # Trainer-only GET of the current batch; admin-only POST to refresh.
    # Phase 1: deterministic mock data (10 tasks per trainer); real
    # assignment engine lands in Phase 2 / Step 8.
    path(
        'api/v1/trainer/batch',
        TrainerBatchAPI.as_view(),
        name='trainer-batch',
    ),
    path(
        'api/v1/trainer/batch/refresh',
        TrainerBatchRefreshAPI.as_view(),
        name='trainer-batch-refresh',
    ),
    # TrainPlex — Phase 1 Step 13: Trainer self-service Profile + Settings.
    # GET/PATCH /me/profile + sessions + login-history + password change.
    # Role is intentionally read-only on PATCH so trainers can't self-promote.
    path(
        'api/v1/users/me/profile',
        TrainerProfileAPI.as_view(),
        name='users-me-profile',
    ),
    # Avatar upload mounts the same APIView; routing on URL keeps the
    # multipart parser narrow to one endpoint without a separate class.
    path(
        'api/v1/users/me/avatar',
        TrainerProfileAPI.as_view(),
        name='users-me-avatar',
    ),
    path(
        'api/v1/users/me/sessions',
        TrainerSessionsAPI.as_view(),
        name='users-me-sessions',
    ),
    path(
        'api/v1/users/me/sessions/<int:session_id>',
        TrainerSessionRevokeAPI.as_view(),
        name='users-me-sessions-revoke',
    ),
    path(
        'api/v1/users/me/login-history',
        TrainerLoginHistoryAPI.as_view(),
        name='users-me-login-history',
    ),
    path(
        'api/v1/users/me/password/change',
        TrainerPasswordChangeAPI.as_view(),
        name='users-me-password-change',
    ),
    re_path(r'health/', views.health, name='health'),
    re_path(r'metrics/', views.metrics, name='metrics'),
    re_path(r'trigger500/', views.TriggerAPIError.as_view(), name='metrics'),
    re_path(r'samples/time-series.csv', views.samples_time_series, name='static_time_series'),
    re_path(r'samples/paragraphs.json', views.samples_paragraphs, name='samples_paragraphs'),
    # Legacy swagger URLs redirect to new drf-spectacular URLs
    re_path(r'^swagger\.json$', lambda request: HttpResponseRedirect('/docs/api/schema/json/'), name='schema-json'),
    re_path(r'^swagger\.yaml$', lambda request: HttpResponseRedirect('/docs/api/schema/yaml/'), name='schema-yaml'),
    re_path(
        r'^swagger/$', lambda request: HttpResponseRedirect('/docs/api/schema/swagger-ui/'), name='schema-swagger-ui'
    ),
    # Again for legacy reasons, docs/api?format=openapi redirects to docs/api/schema/json/
    path(
        'docs/api/',
        lambda request: (
            HttpResponseRedirect('/docs/api/schema/json/')
            if request.GET.get('format') == 'openapi'
            else HttpResponseRedirect('/docs/api/schema/redoc/')
        ),
        name='docs-api',
    ),
    path(
        'docs/',
        RedirectView.as_view(url='/static/docs/public/guide/introduction.html', permanent=False),
        name='docs-redirect',
    ),
    path('admin/', admin.site.urls),
    path('django-rq/', include('django_rq.urls')),
    path('feature-flags/', views.feature_flags, name='feature_flags'),
    path('heidi-tips/', views.heidi_tips, name='heidi_tips'),
    path('__lsa/', views.collect_metrics, name='collect_metrics'),
    re_path(r'^api-auth/', include('rest_framework.urls', namespace='rest_framework')),
    re_path(r'^', include('jwt_auth.urls')),
    re_path(r'^', include('session_policy.urls')),
    path('docs/api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('docs/api/schema/swagger-ui/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('docs/api/schema/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),
    path('docs/api/schema/json/', SpectacularJSONAPIView.as_view(), name='schema-json'),
    path('docs/api/schema/yaml/', SpectacularYAMLAPIView.as_view(), name='schema-yaml'),
]

if settings.DEBUG:
    try:
        import debug_toolbar

        urlpatterns = [path('__debug__/', include(debug_toolbar.urls))] + urlpatterns
    except ImportError:
        pass
