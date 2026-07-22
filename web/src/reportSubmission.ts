export type ReportSubmissionState =
  | { status: "idle" }
  | { status: "submitting" }
  | { status: "success"; issueId: string }
  | { status: "error"; error: string };

export function reportResultState(result: {
  success: boolean;
  issue_id?: string;
  error?: string;
}): ReportSubmissionState {
  if (result.success && result.issue_id) {
    return { status: "success", issueId: result.issue_id };
  }
  return {
    status: "error",
    error: result.error ?? "The server could not create this report.",
  };
}
