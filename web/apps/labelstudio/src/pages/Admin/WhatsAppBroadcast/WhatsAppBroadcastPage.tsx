/**
 * WhatsAppBroadcastPage — TrainPlex Admin WA Broadcast composer.
 *
 * Phase 1 Step 4.2-7. Top: template picker. Middle: trainer selector
 * (filter chips). Bottom: WhatsApp-styled preview + send button.
 *
 * Backend wiring
 * --------------
 *   GET  /api/v1/admin/wa/templates          → fills the picker
 *   POST /api/v1/admin/wa/broadcast          → fan-out send
 *   GET  /api/v1/admin/wa/broadcast/history  → past broadcasts (drawer)
 *
 * Phase 1 caveats
 * ---------------
 * The trainer roster is mocked (same data as the Project Wizard Step 3 —
 * we reuse `MOCK_TRAINERS`). Real roster API lands in Phase 2. The send
 * itself is also mocked at the backend — see `core/services/wa_broadcast.py`.
 */

import { Button, RoleGate, Spinner } from "@humansignal/ui";
import { useTranslation } from "@humansignal/app-common";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { useAuth } from "@humansignal/core/providers/AuthProvider";
import { useAPI } from "../../../providers/ApiProvider";
import type { Page } from "../../types/Page";
import { MOCK_TRAINERS } from "../ProjectWizard/Step3_Assign";
import { BroadcastHistoryDrawer } from "./BroadcastHistoryDrawer";
import { TemplatePicker } from "./TemplatePicker";
import { TemplatePreviewPane } from "./TemplatePreviewPane";
import { TrainerSelector } from "./TrainerSelector";
import type { WaBroadcastResponse, WaTemplate, WaTemplateList } from "./types";
import styles from "./WhatsAppBroadcast.module.css";

const TEMPLATES_QUERY_KEY = ["admin-wa-templates"];

export const WhatsAppBroadcastPage: Page = () => {
  const api = useAPI();
  const { t } = useTranslation();
  const { user } = useAuth();
  const queryClient = useQueryClient();

  const [selectedTemplateId, setSelectedTemplateId] = useState<string | null>(null);
  const [selectedTrainerIds, setSelectedTrainerIds] = useState<number[]>([]);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [resultBanner, setResultBanner] = useState<
    { kind: "success" | "error"; text: string } | null
  >(null);

  const templatesQuery = useQuery<WaTemplateList>({
    queryKey: TEMPLATES_QUERY_KEY,
    queryFn: async () => {
      const res = await api.callApi("adminWaTemplates");
      return res as WaTemplateList;
    },
    staleTime: 5 * 60_000,
    enabled: user?.role === "admin",
  });

  const templates: WaTemplate[] = templatesQuery.data?.items ?? [];
  const selectedTemplate = useMemo(
    () => templates.find((tpl) => tpl.id === selectedTemplateId) || null,
    [templates, selectedTemplateId],
  );

  // First-trainer sample for the preview (Geeta P. if she's in the selection,
  // else the first selected trainer, else nothing).
  const previewParams = useMemo<Record<string, string | number>>(() => {
    const firstId = selectedTrainerIds[0];
    if (firstId == null) return {};
    const trainer = MOCK_TRAINERS.find((tr) => tr.id === firstId);
    if (!trainer) return {};
    return { name: trainer.name, amount: 4350 };
  }, [selectedTrainerIds]);

  const broadcastMutation = useMutation<WaBroadcastResponse | undefined, Error, void>({
    mutationFn: async () => {
      if (!selectedTemplateId) return undefined;
      const body: Record<string, unknown> = {
        template_id: selectedTemplateId,
        trainer_ids: selectedTrainerIds,
      };
      const res = (await api.callApi("adminWaBroadcast", { body })) as
        | WaBroadcastResponse
        | undefined;
      return res;
    },
    onSuccess: (res) => {
      if (!res) {
        setResultBanner({ kind: "error", text: t("admin.wa.send_failed") });
        return;
      }
      // Some api wrappers return {error:...} on non-2xx — surface it.
      const errLike = (res as any)?.error;
      if (errLike) {
        const code = (res as any)?.code;
        if (code === "rate_limited") {
          setResultBanner({ kind: "error", text: t("admin.wa.rate_limited") });
        } else {
          setResultBanner({ kind: "error", text: String(errLike) });
        }
        return;
      }
      const sent = res.counts?.sent ?? 0;
      const skipped = res.counts?.skipped ?? 0;
      const failed = res.counts?.failed ?? 0;
      setResultBanner({
        kind: "success",
        text: `${t("admin.wa.status_sent")}: ${sent} · ${t(
          "admin.wa.status_skipped",
        )}: ${skipped} · ${t("admin.wa.status_failed")}: ${failed}`,
      });
      queryClient.invalidateQueries({ queryKey: ["admin-wa-broadcast-history"] });
    },
    onError: (err) => {
      setResultBanner({ kind: "error", text: err.message || t("admin.wa.send_failed") });
    },
  });

  const canSend =
    !!selectedTemplateId &&
    selectedTrainerIds.length > 0 &&
    !broadcastMutation.isPending;

  const onSend = () => {
    setResultBanner(null);
    broadcastMutation.mutate();
  };

  const body = (() => {
    if (templatesQuery.isLoading) {
      return (
        <div className={styles.loadingBox} role="status" aria-live="polite" data-testid="wa-loading">
          <Spinner />
          <span>{t("admin.wa.loading_templates")}</span>
        </div>
      );
    }
    if (templatesQuery.isError) {
      return (
        <div className={styles.errorBox} data-testid="wa-templates-error">
          {t("admin.wa.templates_failed")}
        </div>
      );
    }

    return (
      <>
        {/* Top: template picker */}
        <section className={styles.section} aria-label={t("admin.wa.choose_template")}>
          <h2 className={styles.sectionHeading}>{t("admin.wa.choose_template")}</h2>
          <TemplatePicker
            templates={templates}
            value={selectedTemplateId}
            onChange={(id) => {
              setSelectedTemplateId(id);
              setResultBanner(null);
            }}
          />
        </section>

        {/* Middle: trainer selector */}
        <section className={styles.section} aria-label={t("admin.wa.choose_trainers")}>
          <h2 className={styles.sectionHeading}>{t("admin.wa.choose_trainers")}</h2>
          <TrainerSelector
            selectedIds={selectedTrainerIds}
            onSelectionChange={setSelectedTrainerIds}
          />
        </section>

        {/* Bottom: preview + send */}
        <section className={styles.section} aria-label={t("admin.wa.preview")}>
          {selectedTemplate ? (
            <TemplatePreviewPane template={selectedTemplate} sampleParams={previewParams} />
          ) : (
            <span className={styles.previewMeta}>{t("admin.wa.preview")}</span>
          )}

          <div className={styles.sendRow}>
            <span className={styles.selectedCount} data-testid="wa-selected-summary">
              {t("admin.wa.send_to_n", { count: selectedTrainerIds.length })}
            </span>
            <Button
              look="filled"
              size="medium"
              className={styles.sendBtn}
              data-testid="wa-send-button"
              disabled={!canSend}
              onClick={onSend}
            >
              {broadcastMutation.isPending ? (
                <Spinner />
              ) : (
                t("admin.wa.send_to_n", { count: selectedTrainerIds.length })
              )}
            </Button>
          </div>

          {resultBanner ? (
            <div
              className={
                resultBanner.kind === "success" ? styles.successBanner : styles.errorBanner
              }
              data-testid={`wa-banner-${resultBanner.kind}`}
            >
              {resultBanner.text}
            </div>
          ) : null}
        </section>
      </>
    );
  })();

  return (
    <main className={`p-6 ${styles.waRoot}`} data-testid="admin-wa-broadcast">
      <RoleGate
        allow={["admin"]}
        userRole={user?.role}
        fallback={
          <div className={styles.errorBox} data-testid="wa-forbidden">
            403 — admin only
          </div>
        }
      >
        <header className={styles.waHeader}>
          <div>
            <h1 className={styles.waTitle}>{t("admin.wa.title")}</h1>
            <div className={styles.waSubtitle}>WhatsApp template broadcast</div>
          </div>
          <div className={styles.headerActions}>
            <button
              type="button"
              className={styles.historyToggle}
              data-testid="wa-open-history"
              onClick={() => setHistoryOpen(true)}
            >
              {t("admin.wa.history")}
            </button>
          </div>
        </header>
        {body}
        <BroadcastHistoryDrawer open={historyOpen} onClose={() => setHistoryOpen(false)} />
      </RoleGate>
    </main>
  );
};

WhatsAppBroadcastPage.title = "WhatsApp Broadcast";
WhatsAppBroadcastPage.path = "/admin/wa/broadcast";
WhatsAppBroadcastPage.exact = true;

export default WhatsAppBroadcastPage;
