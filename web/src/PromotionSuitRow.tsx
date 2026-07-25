import { type CSSProperties, type ReactNode } from "react";

const PROMOTION_SUITS = ["SPADE", "HEART", "DIAMOND", "CLUB"] as const;

export const PROMOTION_SUITS_ACCESSIBLE_LABEL =
  "Spade, Heart, Diamond, and Club complete";

export function PromotionSuitRow({
  getSuitColor,
  renderSuitIcon,
}: {
  getSuitColor: (suit: string) => string;
  renderSuitIcon: (suit: string) => ReactNode;
}) {
  return (
    <div
      className="promotion-suits"
      role="img"
      aria-label={PROMOTION_SUITS_ACCESSIBLE_LABEL}
    >
      {PROMOTION_SUITS.map((suit, index) => (
        <span
          key={suit}
          className="promotion-suit"
          style={
            {
              "--promotion-suit-color": getSuitColor(suit),
              "--promotion-suit-delay": `${index * 90}ms`,
            } as CSSProperties
          }
          aria-hidden="true"
        >
          {renderSuitIcon(suit)}
        </span>
      ))}
    </div>
  );
}
