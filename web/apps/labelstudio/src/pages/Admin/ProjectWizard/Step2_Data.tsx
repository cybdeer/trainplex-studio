/**
 * Step 2 — Upload Data.
 *
 * Phase 1 Step 4.2-2. Drag-drop zone built on HTML5 native drag events (no
 * extra dependency). Accepts CSV / JSON / image zip. The actual upload to LS
 * file storage is Phase 2 — for now we capture the filename + size locally
 * and pass a generated upload-id string to Step 3 / the create endpoint, so
 * the wizard flow is end-to-end testable.
 *
 * Accessibility: the drop zone is also a clickable label that triggers a
 * hidden `<input type="file">`, so keyboard + screen-reader users can upload
 * via the standard file dialog. Drop events fire `preventDefault` to avoid
 * the browser opening the file in a new tab.
 */

import { useCallback, useRef, useState } from "react";
import { useTranslation } from "@humansignal/app-common";
import styles from "./ProjectWizard.module.css";

export interface Step2DataProps {
  /** Current project name — bound input. */
  projectName: string;
  onProjectNameChange: (name: string) => void;
  /** Current upload id (or null). */
  dataFileUploadId: string | null;
  onFileSelected: (uploadId: string, file: File) => void;
  onFileCleared: () => void;
}

/** Generate a stable-ish upload id for Phase 1 — replaced by a real id in P2. */
function makeUploadId(): string {
  // Date.now() is plenty deterministic for a single-user wizard session;
  // Phase 2 swaps this for the LS file-upload API response id.
  return `wizard-upload-${Date.now()}`;
}

export function Step2Data({
  projectName,
  onProjectNameChange,
  dataFileUploadId,
  onFileSelected,
  onFileCleared,
}: Step2DataProps) {
  const { t } = useTranslation();
  const inputRef = useRef<HTMLInputElement | null>(null);
  const [dragActive, setDragActive] = useState(false);
  const [fileName, setFileName] = useState<string | null>(null);
  const [fileSize, setFileSize] = useState<number | null>(null);

  const acceptList = ".csv,.json,.zip,application/zip,text/csv,application/json";

  const handleFile = useCallback(
    (file: File) => {
      setFileName(file.name);
      setFileSize(file.size);
      const id = makeUploadId();
      onFileSelected(id, file);
    },
    [onFileSelected],
  );

  const handleDrop = useCallback(
    (e: React.DragEvent<HTMLLabelElement>) => {
      e.preventDefault();
      e.stopPropagation();
      setDragActive(false);
      const file = e.dataTransfer?.files?.[0];
      if (file) handleFile(file);
    },
    [handleFile],
  );

  const handleDragOver = useCallback((e: React.DragEvent<HTMLLabelElement>) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent<HTMLLabelElement>) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
  }, []);

  const handleInputChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      if (file) handleFile(file);
    },
    [handleFile],
  );

  const clear = () => {
    setFileName(null);
    setFileSize(null);
    if (inputRef.current) inputRef.current.value = "";
    onFileCleared();
  };

  return (
    <section
      className={styles.step2Root}
      aria-label={t("admin.wizard.step2")}
      data-testid="wizard-step2"
    >
      <h2 className={styles.stepHeading}>{t("admin.wizard.step2")}</h2>

      <label className={styles.projectNameField} htmlFor="wizard-project-name">
        <span className={styles.projectNameLabel}>
          {t("admin.wizard.project_name_label")}
        </span>
        <input
          id="wizard-project-name"
          data-testid="wizard-project-name-input"
          type="text"
          className={styles.projectNameInput}
          value={projectName}
          onChange={(e) => onProjectNameChange(e.target.value)}
          placeholder={t("admin.wizard.project_name_placeholder")}
          required
        />
      </label>

      <label
        htmlFor="wizard-file-input"
        data-testid="wizard-drop-zone"
        className={`${styles.dropZone} ${dragActive ? styles.dropZoneActive : ""}`}
        onDrop={handleDrop}
        onDragOver={handleDragOver}
        onDragEnter={handleDragOver}
        onDragLeave={handleDragLeave}
      >
        <input
          id="wizard-file-input"
          ref={inputRef}
          type="file"
          accept={acceptList}
          onChange={handleInputChange}
          className={styles.dropZoneFileInput}
          data-testid="wizard-file-input"
        />
        <div className={styles.dropZoneIcon} aria-hidden="true">
          ⬆
        </div>
        <div className={styles.dropZoneText}>{t("admin.wizard.drop_zone")}</div>
      </label>

      {fileName && dataFileUploadId ? (
        <div className={styles.uploadStatus} data-testid="wizard-upload-status">
          <span className={styles.uploadStatusName}>{fileName}</span>
          {fileSize != null ? (
            <span className={styles.uploadStatusSize}>
              ({Math.round(fileSize / 1024)} KB)
            </span>
          ) : null}
          <button
            type="button"
            className={styles.uploadClearBtn}
            data-testid="wizard-upload-clear"
            onClick={clear}
          >
            ✕
          </button>
        </div>
      ) : null}
    </section>
  );
}

export default Step2Data;
