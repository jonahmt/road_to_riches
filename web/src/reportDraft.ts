import type { ReportAttachment } from "./protocol";

export const MAX_REPORT_IMAGE_BYTES = 10 * 1024 * 1024;

export const REPORT_IMAGE_TYPES = ["image/png", "image/jpeg", "image/webp"] as const;
export type ReportImageType = (typeof REPORT_IMAGE_TYPES)[number];

export interface ReportImageCandidate {
  name: string;
  size: number;
  type: string;
}

export function canSubmitReport(
  summary: string,
  description: string,
  submissionStatus: string,
): boolean {
  return Boolean(
    summary.trim() && description.trim() && submissionStatus !== "submitting",
  );
}

export function validateReportImage(candidate: ReportImageCandidate): string | null {
  if (!REPORT_IMAGE_TYPES.includes(candidate.type as ReportImageType)) {
    return "Choose a PNG, JPEG, or WebP image.";
  }
  if (candidate.size > MAX_REPORT_IMAGE_BYTES) {
    return "Images must be 10 MiB or smaller.";
  }
  return null;
}

export function attachmentFromDataUrl(
  candidate: ReportImageCandidate,
  dataUrl: string,
): ReportAttachment | null {
  const match = /^data:(image\/(?:png|jpeg|webp));base64,([A-Za-z0-9+/=]+)$/.exec(dataUrl);
  if (!match || match[1] !== candidate.type) {
    return null;
  }
  return {
    filename: candidate.name,
    mime_type: match[1] as ReportImageType,
    data_base64: match[2],
  };
}
