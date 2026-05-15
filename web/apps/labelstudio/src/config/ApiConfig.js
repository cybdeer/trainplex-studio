export const API_CONFIG = {
  gateway: `${window.APP_SETTINGS.hostname}/api`,
  endpoints: {
    // Users
    users: "/users",
    updateUser: "PATCH:/users/:pk",
    updateUserAvatar: "POST:/users/:pk/avatar",
    deleteUserAvatar: "DELETE:/users/:pk/avatar",
    me: "/current-user/whoami",
    hotkeys: "GET:/current-user/hotkeys/",
    updateHotkeys: "PATCH:/current-user/hotkeys/",

    // Organization
    memberships: "/organizations/:pk/memberships",
    userMemberships: "/organizations/:pk/memberships/:userPk",
    inviteLink: "/invite",
    resetInviteLink: "POST:/invite/reset-token",

    // Project
    projects: "/projects",
    project: "/projects/:pk",
    updateProject: "PATCH:/projects/:pk",
    createProject: "POST:/projects",
    deleteProject: "DELETE:/projects/:pk",
    projectResetCache: "POST:/projects/:pk/summary/reset",

    // Presigning
    presignUrlForTask: "/../tasks/:taskID/presign",
    presignUrlForProject: "/../projects/:projectId/presign",

    // Config and Import
    configTemplates: "/templates",
    validateConfig: "POST:/projects/:pk/validate",
    createSampleTask: "POST:/projects/:pk/sample-task",
    fileUploads: "/projects/:pk/file-uploads",
    deleteFileUploads: "DELETE:/projects/:pk/file-uploads",
    importFiles: "POST:/projects/:pk/import",
    reimportFiles: "POST:/projects/:pk/reimport",
    dataSummary: "/projects/:pk/summary",

    // DM
    deleteTabs: "DELETE:/dm/views/reset",

    // Storages
    listStorages: "/storages/:target?",
    storageTypes: "/storages/:target?/types",
    storageForms: "/storages/:target?/:type/form",
    createStorage: "POST:/storages/:target?/:type",
    deleteStorage: "DELETE:/storages/:target?/:type/:pk",
    updateStorage: "PATCH:/storages/:target?/:type/:pk",
    syncStorage: "POST:/storages/:target?/:type/:pk/sync",
    validateStorage: "POST:/storages/:target?/:type/validate",
    storageFiles: "POST:/storages/:target?/:type/files",

    // ML
    mlBackends: "GET:/ml",
    mlBackend: "GET:/ml/:pk",
    addMLBackend: "POST:/ml",
    updateMLBackend: "PATCH:/ml/:pk",
    deleteMLBackend: "DELETE:/ml/:pk",
    trainMLBackend: "POST:/ml/:pk/train",
    predictWithML: "POST:/ml/:pk/predict/test",
    projectModelVersions: "/projects/:pk/model-versions",
    deletePredictions: "DELETE:/projects/:pk/model-versions",
    modelVersions: "/ml/:pk/versions",
    mlInteractive: "POST:/ml/:pk/interactive-annotating",

    // Export
    export: "/projects/:pk/export",
    previousExports: "/projects/:pk/export/files",
    exportFormats: "/projects/:pk/export/formats",

    // Version
    version: "/version",

    // Webhook
    webhooks: "/webhooks",
    webhook: "/webhooks/:pk",
    updateWebhook: "PATCH:/webhooks/:pk",
    createWebhook: "POST:/webhooks",
    deleteWebhook: "DELETE:/webhooks/:pk",
    webhooksInfo: "/webhooks/info",

    // Product tours
    getProductTour: "GET:/current-user/product-tour",
    updateProductTour: "PATCH:/current-user/product-tour",

    // Tokens
    accessTokenList: "GET:/token",
    accessTokenGetRefreshToken: "POST:/token",
    accessTokenRevoke: "POST:/token/blacklist",

    accessTokenSettings: "GET:/jwt/settings",
    accessTokenUpdateSettings: "POST:/jwt/settings",

    // FSM
    fsmStateHistory: "GET:/fsm/entities/:entityType/:entityId/history",

    // TrainPlex — Phase 1 Step 4.2-1: Admin dashboard snapshot (mock data in Phase 1)
    adminDashboardSnapshot: "GET:/v1/admin/dashboard/snapshot",

    // TrainPlex — Phase 1 Step 4.2-2: Admin 3-step Project Wizard
    adminTemplateCatalog: "GET:/v1/admin/templates/catalog",
    adminProjectWizardCreate: "POST:/v1/admin/projects/wizard",

    // TrainPlex — Phase 1 Step 4.2-3: Admin Bulk Task Assign.
    // Filter trainers by state/tier/language/cert, assign tasks in bulk.
    // Phase 1 backend ships a mock plan; real LS task-write lands Phase 2.
    // POST is rate-limited to 5 bulk-assigns / hour / admin.
    adminTrainerFilter: "GET:/v1/admin/trainers/filter",
    adminBulkAssign: "POST:/v1/admin/tasks/bulk-assign",

    // TrainPlex — Phase 1 Step 4.2-4: Admin audit-log viewer.
    // Paginated read-only listing over users.AuditLog. Query params: action,
    // actor_email, target_type, success, start_date, end_date, page, page_size.
    adminAuditLog: "GET:/v1/admin/audit/log",

    // TrainPlex — Phase 1 Step 4.2-6: Admin India geographic heatmap.
    // Accepts ?period=today|week|month (default month). Mock data in Phase 1;
    // real DB aggregation lands in Phase 2 / Step 8.
    adminHeatmapStateActivity: "GET:/v1/admin/heatmap/state-activity",

    // TrainPlex — Phase 1 Step 4.2-7: Admin WhatsApp Broadcast.
    // Templates list, fan-out send (mock AiSensy in Phase 1), and history.
    adminWaTemplates: "GET:/v1/admin/wa/templates",
    adminWaBroadcast: "POST:/v1/admin/wa/broadcast",
    adminWaBroadcastHistory: "GET:/v1/admin/wa/broadcast/history",

    // TrainPlex — Phase 1 Step 4.2-8: Admin Quality Alert Center.
    // Lists auto-flagged reviewer-disagree / time-anomaly / duplicate-pattern
    // signals; severity bucket counts feed the dashboard widget; review POST
    // resolves an alert with admin notes. Detection mock in Phase 1; real
    // call-sites land Week 5 with peer-review native.
    adminQualityAlerts: "GET:/v1/admin/quality-alerts",
    adminQualityAlertsStats: "GET:/v1/admin/quality-alerts/stats",
    adminQualityAlertReview: "POST:/v1/admin/quality-alerts/:alert_id/review",

    // TrainPlex — Phase 1 Step 4.2-9: Admin Submissions Preview drawer.
    // Recent N submissions (default 10, cap 50) with task / answer / 3-reviewer
    // score preview so admin can spot-check fraud / quality at random.
    // Filters: project_id, trainer_id, status. Mock data in Phase 1; real DB
    // wiring lands in Phase 2 / Step 8.
    adminSubmissionsPreview: "GET:/v1/admin/submissions/preview",

    // TrainPlex — Phase 1 Step 12.4: TOTP 2FA endpoints (admin + qa_lead only).
    twoFactorEnrollStart: "POST:/v1/users/me/2fa/enroll/start",
    twoFactorEnrollConfirm: "POST:/v1/users/me/2fa/enroll/confirm",
    twoFactorDisable: "POST:/v1/users/me/2fa/disable",

    // TrainPlex — Phase 1 Step 6: Reviewer queue + 3-reviewer consensus + QA dispute.
    // /reviewer/* enforced via @require_role(['reviewer']); /qa/* via @require_role(['qa_lead']).
    // submit-review recomputes consensus; resolve flips Dispute.resolved_at.
    reviewerQueue: "GET:/v1/reviewer/queue",
    reviewerSubmitReview: "POST:/v1/reviewer/submit-review",
    qaDisputes: "GET:/v1/qa/disputes",
    qaDisputeResolve: "POST:/v1/qa/disputes/:dispute_id/resolve",

    // TrainPlex — Phase 1 Step 1.4-E: Trainer 10-task Batch.
    // Trainer-only GET; admin-only POST refresh. Mock data Phase 1.
    trainerBatch: "GET:/v1/trainer/batch",
    trainerBatchRefresh: "POST:/v1/trainer/batch/refresh",

    // TrainPlex — Phase 1 Step 13: Trainer self-service Profile + Settings.
    // role + email are READ-ONLY on PATCH (silent ignore on the backend).
    trainerProfile: "GET:/v1/users/me/profile",
    trainerProfileUpdate: "PATCH:/v1/users/me/profile",
    trainerProfileAvatar: "POST:/v1/users/me/avatar",
    trainerSessions: "GET:/v1/users/me/sessions",
    trainerSessionRevoke: "DELETE:/v1/users/me/sessions/:session_id",
    trainerLoginHistory: "GET:/v1/users/me/login-history",
    trainerPasswordChange: "POST:/v1/users/me/password/change",
  },
  alwaysExpectJSON: false,
};
