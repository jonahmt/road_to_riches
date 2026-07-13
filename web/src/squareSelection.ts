export interface InvestmentSquareChoice {
  squareId: number;
  currentValue: number;
  maxCapital: number;
  districtId: number | null;
}

export function squareIdsFromOptions(value: unknown): number[] {
  if (!Array.isArray(value)) {
    return [];
  }
  return value.flatMap((entry) => {
    if (typeof entry !== "object" || entry === null || Array.isArray(entry)) {
      return [];
    }
    const squareId = finiteInteger((entry as Record<string, unknown>).square_id, -1);
    return squareId >= 0 ? [squareId] : [];
  });
}

function finiteInteger(value: unknown, fallback = 0): number {
  const number = typeof value === "number" ? value : Number(value);
  return Number.isFinite(number) ? Math.floor(number) : fallback;
}

export function investmentSquareChoices(value: unknown): InvestmentSquareChoice[] {
  if (!Array.isArray(value)) {
    return [];
  }

  return value.flatMap((entry) => {
    if (typeof entry !== "object" || entry === null || Array.isArray(entry)) {
      return [];
    }
    const record = entry as Record<string, unknown>;
    const squareId = finiteInteger(record.square_id, -1);
    const maxCapital = Math.max(0, finiteInteger(record.max_capital));
    if (squareId < 0 || maxCapital <= 0) {
      return [];
    }
    const rawDistrict = record.district;
    return [
      {
        squareId,
        currentValue: Math.max(0, finiteInteger(record.current_value)),
        maxCapital,
        districtId: rawDistrict === null || rawDistrict === undefined
          ? null
          : finiteInteger(rawDistrict),
      },
    ];
  });
}

export function maximumInvestment(choice: InvestmentSquareChoice, spendableCash: number): number {
  return Math.max(0, Math.min(choice.maxCapital, finiteInteger(spendableCash)));
}

export function clampInvestmentAmount(amount: number, maximum: number): number {
  if (!Number.isFinite(amount) || maximum <= 0) {
    return 0;
  }
  return Math.min(Math.floor(maximum), Math.max(1, Math.floor(amount)));
}
