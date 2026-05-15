"""TrainPlex reports URL routes — Phase 1 Step 7.

Mounted by ``core/urls.py`` via ``include('reports.urls')``.

Endpoints
---------
    GET /api/v1/admin/reports/founder-weekly                          (admin)
    GET /api/v1/admin/reports/founder-weekly.pdf                      (admin)
    GET /api/v1/admin/reports/leaderboard                             (admin)
    GET /api/v1/admin/reports/leaderboard.csv                         (admin)
    GET /api/v1/admin/reports/cohorts                                 (admin)
    GET /api/v1/admin/reports/project-roi                             (admin)
    GET /api/v1/admin/reports/project-roi/<project_id>                (admin)
    GET /api/v1/admin/reports/project-roi/<project_id>.pdf            (admin)
"""

from django.urls import path

from reports.api import (
    CohortsAPI,
    FounderWeeklyAPI,
    FounderWeeklyPDFAPI,
    LeaderboardAPI,
    LeaderboardCSVAPI,
    ProjectROIDetailAPI,
    ProjectROIListAPI,
    ProjectROIPDFAPI,
)

urlpatterns = [
    path(
        'api/v1/admin/reports/founder-weekly',
        FounderWeeklyAPI.as_view(),
        name='reports-founder-weekly',
    ),
    path(
        'api/v1/admin/reports/founder-weekly.pdf',
        FounderWeeklyPDFAPI.as_view(),
        name='reports-founder-weekly-pdf',
    ),
    path(
        'api/v1/admin/reports/leaderboard',
        LeaderboardAPI.as_view(),
        name='reports-leaderboard',
    ),
    path(
        'api/v1/admin/reports/leaderboard.csv',
        LeaderboardCSVAPI.as_view(),
        name='reports-leaderboard-csv',
    ),
    path(
        'api/v1/admin/reports/cohorts',
        CohortsAPI.as_view(),
        name='reports-cohorts',
    ),
    path(
        'api/v1/admin/reports/project-roi',
        ProjectROIListAPI.as_view(),
        name='reports-project-roi-list',
    ),
    path(
        'api/v1/admin/reports/project-roi/<int:project_id>',
        ProjectROIDetailAPI.as_view(),
        name='reports-project-roi-detail',
    ),
    path(
        'api/v1/admin/reports/project-roi/<int:project_id>.pdf',
        ProjectROIPDFAPI.as_view(),
        name='reports-project-roi-pdf',
    ),
]
