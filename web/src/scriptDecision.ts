export interface ScriptDecisionOption {
  label: string;
  value: unknown;
}

export function scriptDecisionOptions(value: unknown): ScriptDecisionOption[] {
  if (value === null || typeof value !== "object" || Array.isArray(value)) {
    return [];
  }
  return Object.entries(value as Record<string, unknown>).map(([label, optionValue]) => ({
    label,
    value: optionValue,
  }));
}
