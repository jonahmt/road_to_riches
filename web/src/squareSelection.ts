export interface InvestmentSquareChoice {
  squareId: number;
  currentValue: number;
  maxCapital: number;
  districtId: number | null;
}

export interface SelectionScrimBounds {
  minX: number;
  minY: number;
  width: number;
  height: number;
}

export interface SelectionScrimSquare {
  id: number;
  position: readonly [number, number];
}

export function boardSelectionScrimPath(
  bounds: SelectionScrimBounds,
  squares: SelectionScrimSquare[],
  eligibleSquareIds: ReadonlySet<number>,
  tileSize = 4,
  strokeWidth = 0.14,
): string | null {
  if (squares.length === 0) {
    return null;
  }
  const eligibleSquares = squares.filter((square) => eligibleSquareIds.has(square.id));
  if (eligibleSquares.length === squares.length) {
    return null;
  }

  const outer = rectanglePath(bounds.minX, bounds.minY, bounds.width, bounds.height);
  const cutoutSize = tileSize + strokeWidth;
  const cutoutRadius = cutoutSize / 2;
  const cutouts = eligibleSquares
    .map((square) =>
      rectanglePath(
        square.position[0] - cutoutRadius,
        square.position[1] - cutoutRadius,
        cutoutSize,
        cutoutSize,
      ),
    )
    .join("");
  return `${outer}${cutouts}`;
}

function rectanglePath(x: number, y: number, width: number, height: number): string {
  return `M${x} ${y}h${width}v${height}h-${width}Z`;
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
