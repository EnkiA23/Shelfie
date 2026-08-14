/**
 * Backend warning codes, translated for humans.
 *
 * The pipeline never fails a scan outright — it returns 200 with a `warnings`
 * list and routes affected spines to review. This map is the only place that
 * decides how each code reads to a user, and whether it is the user's problem
 * (retake the photo) or the operator's (fix the key).
 */

export type WarningSeverity = "error" | "warning" | "info";

export interface WarningCopy {
  message: string;
  severity: WarningSeverity;
}

const WARNING_COPY: Record<string, WarningCopy> = {
  zero_detections_fallback_full_image: {
    message: "No spines detected — we read the whole photo instead.",
    severity: "info",
  },
  detector_error: {
    message: "Spine detection failed, so we read the whole photo instead.",
    severity: "warning",
  },
  daily_vlm_cap_reached: {
    message: "Daily vision API limit reached. Try again tomorrow.",
    severity: "error",
  },
  // Operator misconfiguration: no amount of retaking the photo helps.
  vlm_not_configured: {
    message: "Vision API key is not set on the server, so no spines could be read.",
    severity: "error",
  },
  vlm_auth_failed: {
    message: "The server's vision API key was rejected. Check the key and try again.",
    severity: "error",
  },
  vlm_model_unavailable: {
    message: "The configured vision model no longer exists. Update GEMINI_MODEL on the server.",
    severity: "error",
  },
  vlm_rate_limited: {
    message: "The vision provider is rate limiting us. Wait a moment and rescan.",
    severity: "warning",
  },
  vlm_timeout: {
    message: "The vision provider timed out on some spines. They're in review below.",
    severity: "warning",
  },
  vlm_unreadable_response: {
    message: "Some spines came back unreadable. They're in review below.",
    severity: "warning",
  },
  vlm_provider_error: {
    message: "The vision provider errored on some spines. They're in review below.",
    severity: "warning",
  },
  vlm_error: {
    message: "Some spines could not be read. They're in review below.",
    severity: "warning",
  },
  matching_error: {
    message: "Some spines were read but could not be matched to the catalog.",
    severity: "warning",
  },
};

const SEVERITY_ORDER: WarningSeverity[] = ["error", "warning", "info"];

export function describeWarning(code: string): WarningCopy | null {
  if (WARNING_COPY[code]) return WARNING_COPY[code];
  // `vlm_calls_capped_at_10` and friends carry their limit in the code itself.
  const capped = code.match(/^vlm_calls_capped_at_(\d+)$/);
  if (capped) {
    return {
      message: `Only the first ${capped[1]} spines were read, to stay within the per-scan cost cap.`,
      severity: "info",
    };
  }
  return null;
}

/** The single most important thing to tell the user about this scan. */
export function primaryWarning(codes: string[] | undefined): WarningCopy | null {
  const described = (codes ?? [])
    .map(describeWarning)
    .filter((copy): copy is WarningCopy => copy !== null);

  for (const severity of SEVERITY_ORDER) {
    const match = described.find((copy) => copy.severity === severity);
    if (match) return match;
  }
  return null;
}
