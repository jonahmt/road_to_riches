import {
  type ChangeEvent,
  type DragEvent,
  type FormEvent,
  useEffect,
  useRef,
  useState,
} from "react";
import type {
  ReportAttachment,
  ReportCategory,
  SubmitReportMessage,
} from "./protocol";
import {
  MAX_REPORT_IMAGE_BYTES,
  attachmentFromDataUrl,
  canSubmitReport,
  validateReportImage,
} from "./reportDraft";
import type { ReportSubmissionState } from "./useGameClient";

interface BugReportControlProps {
  submission: ReportSubmissionState;
  onSubmit: (report: Omit<SubmitReportMessage, "msg" | "player_id" | "game_id">) => boolean;
  onClearSubmission: () => void;
  onOpenChange?: (open: boolean) => void;
}

const ACCEPTED_IMAGE_TYPES = "image/png,image/jpeg,image/webp";

export function BugReportControl({
  submission,
  onSubmit,
  onClearSubmission,
  onOpenChange,
}: BugReportControlProps) {
  const [open, setOpen] = useState(false);
  const [category, setCategory] = useState<ReportCategory>("bug");
  const [priority, setPriority] = useState<0 | 1 | 2 | 3>(2);
  const [summary, setSummary] = useState("");
  const [description, setDescription] = useState("");
  const [includeGameState, setIncludeGameState] = useState(false);
  const [restartRequested, setRestartRequested] = useState(false);
  const [attachment, setAttachment] = useState<ReportAttachment | null>(null);
  const [attachmentPreview, setAttachmentPreview] = useState<string | null>(null);
  const [attachmentError, setAttachmentError] = useState<string | null>(null);
  const [dragActive, setDragActive] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const summaryRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    document.body.dataset.gameplayHotkeysSuppressed = open ? "true" : "false";
    onOpenChange?.(open);
    if (open) {
      window.requestAnimationFrame(() => summaryRef.current?.focus());
    }
    return () => {
      delete document.body.dataset.gameplayHotkeysSuppressed;
    };
  }, [onOpenChange, open]);

  useEffect(() => {
    if (!open) {
      return;
    }
    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape" && submission.status !== "submitting") {
        event.preventDefault();
        setOpen(false);
      }
    }
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [open, submission.status]);

  function openReporter() {
    onClearSubmission();
    setOpen(true);
  }

  function closeReporter() {
    if (submission.status === "submitting") {
      return;
    }
    setOpen(false);
  }

  function resetDraft() {
    setCategory("bug");
    setPriority(2);
    setSummary("");
    setDescription("");
    setIncludeGameState(false);
    setRestartRequested(false);
    removeAttachment();
    onClearSubmission();
  }

  function removeAttachment() {
    setAttachment(null);
    setAttachmentPreview(null);
    setAttachmentError(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  }

  function loadAttachment(file: File | undefined) {
    if (!file) {
      return;
    }
    const validationError = validateReportImage(file);
    if (validationError) {
      setAttachmentError(validationError);
      return;
    }
    const reader = new FileReader();
    reader.addEventListener("load", () => {
      const dataUrl = typeof reader.result === "string" ? reader.result : "";
      const nextAttachment = attachmentFromDataUrl(file, dataUrl);
      if (!nextAttachment) {
        setAttachmentError("This image could not be read. Try exporting it again.");
        return;
      }
      setAttachment(nextAttachment);
      setAttachmentPreview(dataUrl);
      setAttachmentError(null);
    });
    reader.addEventListener("error", () => {
      setAttachmentError("This image could not be read.");
    });
    reader.readAsDataURL(file);
  }

  function handleFileChange(event: ChangeEvent<HTMLInputElement>) {
    loadAttachment(event.target.files?.[0]);
  }

  function handleDrop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    setDragActive(false);
    loadAttachment(event.dataTransfer.files?.[0]);
  }

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!canSubmitReport(summary, description, submission.status)) {
      return;
    }
    onSubmit({
      category,
      priority,
      summary: summary.trim(),
      description: description.trim(),
      include_game_state: includeGameState,
      restart_requested: restartRequested,
      attachment: attachment ?? undefined,
    });
  }

  return (
    <>
      <button
        type="button"
        className="bug-report-fab"
        aria-label="Report a bug or request"
        title="Report a bug or request"
        onClick={openReporter}
      >
        <ReportBugIcon />
      </button>

      {open && (
        <div className="bug-report-overlay" role="presentation" onMouseDown={(event) => {
          if (event.target === event.currentTarget) {
            closeReporter();
          }
        }}>
          <section
            className="bug-report-modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="bug-report-title"
          >
            {submission.status === "success" ? (
              <div className="bug-report-success">
                <div className="bug-report-success-mark" aria-hidden="true">✓</div>
                <p className="eyebrow">Report queued</p>
                <h2 id="bug-report-title">Thanks — it’s in Beads.</h2>
                <p>
                  Created <strong>{submission.issueId}</strong>. The repair orchestrator will pick it
                  up on its next run.
                </p>
                <div className="bug-report-actions">
                  <button type="button" className="secondary" onClick={() => {
                    resetDraft();
                    setOpen(false);
                  }}>
                    Close
                  </button>
                  <button type="button" onClick={resetDraft}>Report another</button>
                </div>
              </div>
            ) : (
              <form className="bug-report-form" onSubmit={submit}>
                <header className="bug-report-header">
                  <div>
                    <p className="eyebrow">Development feedback</p>
                    <h2 id="bug-report-title">Report a bug or request</h2>
                    <p>Describe what you saw. This creates a local Beads issue for automatic repair.</p>
                  </div>
                  <button
                    type="button"
                    className="bug-report-close"
                    aria-label="Close report form"
                    disabled={submission.status === "submitting"}
                    onClick={closeReporter}
                  >
                    ×
                  </button>
                </header>

                <div className="bug-report-pair">
                  <label>
                    Category
                    <select value={category} onChange={(event) => setCategory(event.target.value as ReportCategory)}>
                      <option value="bug">Bug</option>
                      <option value="minor_fix">Minor fix</option>
                      <option value="suggestion">Suggestion</option>
                    </select>
                  </label>
                  <label>
                    Urgency
                    <select value={priority} onChange={(event) => setPriority(Number(event.target.value) as 0 | 1 | 2 | 3)}>
                      <option value={0}>Critical</option>
                      <option value={1}>High</option>
                      <option value={2}>Normal</option>
                      <option value={3}>Low</option>
                    </select>
                  </label>
                </div>

                <label>
                  Short summary
                  <input
                    ref={summaryRef}
                    value={summary}
                    maxLength={120}
                    required
                    placeholder="Example: Stock table stays open after buying"
                    onChange={(event) => setSummary(event.target.value)}
                  />
                  <span className="bug-report-counter">{summary.length}/120</span>
                </label>

                <label>
                  What happened, or what should change?
                  <textarea
                    value={description}
                    maxLength={5000}
                    required
                    rows={6}
                    placeholder="Include what you were doing, what you expected, and what happened instead."
                    onChange={(event) => setDescription(event.target.value)}
                  />
                </label>

                <div className="bug-report-options">
                  <label className="bug-report-checkbox">
                    <input
                      type="checkbox"
                      checked={includeGameState}
                      onChange={(event) => setIncludeGameState(event.target.checked)}
                    />
                    <span>
                      <strong>Attach current game state</strong>
                      <small>Includes the authoritative board and turn state for reproduction.</small>
                    </span>
                  </label>
                  <label className="bug-report-checkbox is-warning">
                    <input
                      type="checkbox"
                      checked={restartRequested}
                      onChange={(event) => setRestartRequested(event.target.checked)}
                    />
                    <span>
                      <strong>Restart development services after the fix</strong>
                      <small>This can interrupt the current match. Leave it off to restart manually.</small>
                    </span>
                  </label>
                </div>

                <div
                  className={`bug-report-dropzone ${dragActive ? "is-dragging" : ""} ${attachment ? "has-image" : ""}`}
                  onDragEnter={(event) => {
                    event.preventDefault();
                    setDragActive(true);
                  }}
                  onDragOver={(event) => event.preventDefault()}
                  onDragLeave={(event) => {
                    if (!event.currentTarget.contains(event.relatedTarget as Node | null)) {
                      setDragActive(false);
                    }
                  }}
                  onDrop={handleDrop}
                >
                  <input
                    ref={fileInputRef}
                    type="file"
                    accept={ACCEPTED_IMAGE_TYPES}
                    aria-label="Attach a screenshot"
                    onChange={handleFileChange}
                  />
                  {attachment && attachmentPreview ? (
                    <div className="bug-report-preview">
                      <img src={attachmentPreview} alt="Attachment preview" />
                      <div>
                        <strong>{attachment.filename}</strong>
                        <span>Ready to attach</span>
                        <button type="button" className="secondary" onClick={removeAttachment}>Remove</button>
                      </div>
                    </div>
                  ) : (
                    <button type="button" className="bug-report-drop-prompt" onClick={() => fileInputRef.current?.click()}>
                      <span aria-hidden="true">＋</span>
                      <strong>Drop an image here, or choose a file</strong>
                      <small>Optional · PNG, JPEG, or WebP · up to {MAX_REPORT_IMAGE_BYTES / 1024 / 1024} MiB</small>
                    </button>
                  )}
                </div>
                {attachmentError && <p className="bug-report-error" role="alert">{attachmentError}</p>}
                {submission.status === "error" && (
                  <p className="bug-report-error" role="alert">
                    {submission.error} Your draft is still here—adjust it or try again.
                  </p>
                )}

                <footer className="bug-report-actions">
                  <button type="button" className="secondary" disabled={submission.status === "submitting"} onClick={closeReporter}>
                    Cancel
                  </button>
                  <button type="submit" disabled={!canSubmitReport(summary, description, submission.status)}>
                    {submission.status === "submitting" ? "Creating report…" : "Create report"}
                  </button>
                </footer>
              </form>
            )}
          </section>
        </div>
      )}
    </>
  );
}

function ReportBugIcon() {
  return (
    <svg viewBox="0 0 48 48" role="img" aria-hidden="true">
      <path className="report-icon-bubble" d="M7 7.5h34v25H24l-9.5 8v-8H7z" />
      <path className="report-icon-bug" d="M18 22.5c0-5 2.4-8 6-8s6 3 6 8v4.5c0 3.7-2.6 6-6 6s-6-2.3-6-6z" />
      <path className="report-icon-line" d="M18 20h-4m4 7h-5m17-7h4m-4 7h5M20 14l-2.5-3m10.5 3 2.5-3M18 23h12M24 16v16" />
      <circle cx="21.5" cy="19" r="1.2" />
      <circle cx="26.5" cy="19" r="1.2" />
    </svg>
  );
}
