/**
 * ProjectWizard — TrainPlex Admin 3-step Create Project flow.
 *
 * Phase 1 Step 4.2-2. Replaces the upstream LS "30+ field scary Create
 * Project form" with three small steps:
 *
 *   1. Choose Template — 60-card gallery (10 TrainPlex India + 50 LS native)
 *   2. Upload Data     — drag-drop CSV / JSON / image zip + project name
 *   3. Assign Trainers — multi-select roster with state / tier / language /
 *                        cert filter chips
 *
 * Goal: admin onboarding goes from 10 min to 2 min per plan.
 *
 * Backend wiring
 * --------------
 *   GET  /api/v1/admin/templates/catalog   → Step 1 grid data
 *   POST /api/v1/admin/projects/wizard     → final submit on Step 3
 *
 * Both endpoints are admin-only on the backend. This page is also wrapped in
 * `<RoleGate allow={['admin']}>` so a misrouted trainer never sees the form.
 */

import { Button, RoleGate, Spinner } from "@humansignal/ui";
import { useTranslation } from "@humansignal/app-common";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { useHistory } from "react-router-dom";
import { useAuth } from "@humansignal/core/providers/AuthProvider";
import { useAPI } from "../../../providers/ApiProvider";
import type { Page } from "../../types/Page";
import { ProgressStepper } from "./ProgressStepper";
import { Step1Template } from "./Step1_Template";
import { Step2Data } from "./Step2_Data";
import { Step3Assign } from "./Step3_Assign";
import type { TemplateCard, TemplateCatalog } from "./types";
import styles from "./ProjectWizard.module.css";

const CATALOG_QUERY_KEY = ["admin-template-catalog"];

export const ProjectWizard: Page = () => {
  const api = useAPI();
  const { t } = useTranslation();
  const { user } = useAuth();
  const history = useHistory();

  // Wizard state is intentionally local to the page — no global store. The
  // founder either finishes the flow (submit ⇒ /projects) or navigates away
  // (state is dropped). Persistence across reloads is a Phase 2 nicety.
  const [step, setStep] = useState<1 | 2 | 3>(1);
  const [selectedTemplate, setSelectedTemplate] = useState<TemplateCard | null>(null);
  const [projectName, setProjectName] = useState<string>("");
  const [dataFileUploadId, setDataFileUploadId] = useState<string | null>(null);
  const [trainerIds, setTrainerIds] = useState<number[]>([]);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  const catalogQuery = useQuery<TemplateCatalog>({
    queryKey: CATALOG_QUERY_KEY,
    queryFn: async () => {
      const res = await api.callApi("adminTemplateCatalog");
      return res as TemplateCatalog;
    },
    staleTime: 5 * 60_000, // catalog is essentially static, cache 5 min
    enabled: user?.role === "admin",
  });

  const labels: [string, string, string] = [
    t("admin.wizard.step1"),
    t("admin.wizard.step2"),
    t("admin.wizard.step3"),
  ];

  /** Step 1 → 2 needs a template; Step 2 → 3 needs a name (data file optional). */
  const canAdvance = (() => {
    if (step === 1) return selectedTemplate != null;
    if (step === 2) return projectName.trim().length > 0;
    return true;
  })();

  const handleSubmit = async () => {
    if (!selectedTemplate) return;
    setSubmitting(true);
    setSubmitError(null);
    try {
      const body: Record<string, unknown> = {
        template_id: selectedTemplate.id,
        project_name: projectName.trim(),
        trainer_ids: trainerIds,
      };
      if (dataFileUploadId) body.data_file_upload_id = dataFileUploadId;
      const res = (await api.callApi("adminProjectWizardCreate", { body })) as
        | { id: number; title: string }
        | undefined;
      if (res?.id) {
        history.push(`/projects/${res.id}`);
        return;
      }
      // Some api wrappers return {error: ...} on non-2xx — surface it.
      setSubmitError((res as any)?.error || t("admin.wizard.submit_failed"));
    } catch (err) {
      setSubmitError(
        (err as any)?.response?.error ||
          (err as any)?.message ||
          t("admin.wizard.submit_failed"),
      );
    } finally {
      setSubmitting(false);
    }
  };

  const body = (() => {
    if (catalogQuery.isLoading) {
      return (
        <div className={styles.loadingBox} role="status" aria-live="polite" data-testid="wizard-loading">
          <Spinner />
          <span>{t("admin.wizard.loading_catalog")}</span>
        </div>
      );
    }
    if (catalogQuery.isError || !catalogQuery.data) {
      return (
        <div className={styles.errorBox} data-testid="wizard-error">
          {t("admin.wizard.catalog_failed")}
        </div>
      );
    }
    const templates = catalogQuery.data.items;

    return (
      <>
        <ProgressStepper
          current={step}
          labels={labels}
          onStepClick={(s) => setStep(s)}
        />

        {step === 1 ? (
          <Step1Template
            templates={templates}
            selectedId={selectedTemplate?.id ?? null}
            onSelect={(tpl) => {
              setSelectedTemplate(tpl);
              if (!projectName) {
                // Prefill project name with the template title so the founder
                // can just hit Next twice for the happy path.
                setProjectName(tpl.title);
              }
            }}
          />
        ) : null}

        {step === 2 ? (
          <Step2Data
            projectName={projectName}
            onProjectNameChange={setProjectName}
            dataFileUploadId={dataFileUploadId}
            onFileSelected={(id) => setDataFileUploadId(id)}
            onFileCleared={() => setDataFileUploadId(null)}
          />
        ) : null}

        {step === 3 ? (
          <Step3Assign selectedIds={trainerIds} onSelectionChange={setTrainerIds} />
        ) : null}

        <div className={styles.wizardActions}>
          {step > 1 ? (
            <Button
              look="outlined"
              size="medium"
              data-testid="wizard-back"
              onClick={() => setStep((step - 1) as 1 | 2 | 3)}
            >
              {t("admin.wizard.back")}
            </Button>
          ) : (
            <span /> /* spacer */
          )}
          {step < 3 ? (
            <Button
              look="filled"
              size="medium"
              className={styles.ctaPrimary}
              data-testid="wizard-next"
              disabled={!canAdvance}
              onClick={() => setStep((step + 1) as 1 | 2 | 3)}
            >
              {t("admin.wizard.next")}
            </Button>
          ) : (
            <Button
              look="filled"
              size="medium"
              className={styles.ctaPrimary}
              data-testid="wizard-create"
              disabled={submitting || !selectedTemplate || !projectName.trim()}
              onClick={handleSubmit}
            >
              {submitting ? <Spinner /> : t("admin.wizard.create")}
            </Button>
          )}
        </div>

        {submitError ? (
          <div className={styles.errorBox} data-testid="wizard-submit-error">
            {submitError}
          </div>
        ) : null}
      </>
    );
  })();

  return (
    <main className={`p-6 ${styles.wizardRoot}`} data-testid="admin-project-wizard">
      <RoleGate
        allow={["admin"]}
        userRole={user?.role}
        fallback={
          <div className={styles.errorBox} data-testid="wizard-forbidden">
            403 — admin only
          </div>
        }
      >
        <header className={styles.wizardHeader}>
          <h1 className={styles.wizardTitle}>{t("admin.wizard.title")}</h1>
        </header>
        {body}
      </RoleGate>
    </main>
  );
};

ProjectWizard.title = "New Project";
ProjectWizard.path = "/admin/projects/new";
ProjectWizard.exact = true;

export default ProjectWizard;
