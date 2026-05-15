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

    // TrainPlex — Phase 1 Step 12.4: TOTP 2FA endpoints (admin + qa_lead only).
    twoFactorEnrollStart: "POST:/v1/users/me/2fa/enroll/start",
    twoFactorEnrollConfirm: "POST:/v1/users/me/2fa/enroll/confirm",
    twoFactorDisable: "POST:/v1/users/me/2fa/disable",
  },
  alwaysExpectJSON: false,
};
