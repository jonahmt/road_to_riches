export interface PaymentPayout {
  playerId: number;
  amount: number;
}

export interface RentPaymentFacts {
  payerId: number;
  ownerId: number;
  squareId: number;
  districtId: number | null;
  rentAmount: number;
  dividends: PaymentPayout[];
}

export interface PlayerCashDelta {
  playerId: number;
  amount: number;
}

function finiteInteger(value: unknown, fallback: number): number {
  return typeof value === "number" && Number.isFinite(value) ? Math.trunc(value) : fallback;
}

function parsePayouts(value: unknown): PaymentPayout[] {
  if (!Array.isArray(value)) {
    return [];
  }
  return value.flatMap((entry) => {
    if (typeof entry !== "object" || entry === null) {
      return [];
    }
    const record = entry as Record<string, unknown>;
    const playerId = finiteInteger(record.player_id, -1);
    const amount = finiteInteger(record.amount, 0);
    return playerId >= 0 && amount > 0 ? [{ playerId, amount }] : [];
  });
}

export function rentPaymentFacts(
  data: Record<string, unknown>,
  fallbackPlayerId: number,
): RentPaymentFacts {
  const districtId = finiteInteger(data.district_id, -1);
  return {
    payerId: finiteInteger(data.payer_id, fallbackPlayerId),
    ownerId: finiteInteger(data.owner_id, -1),
    squareId: finiteInteger(data.square_id, -1),
    districtId: districtId >= 0 ? districtId : null,
    rentAmount: Math.max(0, finiteInteger(data.rent_amount, 0)),
    dividends: parsePayouts(data.dividends),
  };
}

export function rentPaymentCashDeltas(payment: RentPaymentFacts): PlayerCashDelta[] {
  const deltas = new Map<number, number>();
  const add = (playerId: number, amount: number) => {
    if (playerId < 0 || amount === 0) {
      return;
    }
    deltas.set(playerId, (deltas.get(playerId) ?? 0) + amount);
  };

  add(payment.payerId, -payment.rentAmount);
  add(payment.ownerId, payment.rentAmount);
  payment.dividends.forEach((payout) => add(payout.playerId, payout.amount));

  return [...deltas.entries()]
    .filter(([, amount]) => amount !== 0)
    .map(([playerId, amount]) => ({ playerId, amount }))
    .sort((left, right) => left.playerId - right.playerId);
}
