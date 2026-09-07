import "./TurnMenu.css";

const ACTIONS = [
  ["roll", "Roll"],
  ["sell_stock", "Sell Stock"],
  ["buy_shop", "Buy Shop"],
  ["sell_shop", "Sell Shop"],
  ["trade", "Trade"],
  ["auction", "Auction"],
] as const;

export function TurnMenu({ responsePending, onSubmit }: {
  responsePending: boolean;
  onSubmit: (value: unknown) => void;
}) {
  return (
    <div className="turn-menu" role="group" aria-label="Turn actions">
      <div className="action-grid">
        {ACTIONS.map(([value, label]) => (
          <button key={value} type="button"
            className="secondary"
            disabled={responsePending}
            onClick={() => onSubmit(value)}
          >{label}</button>
        ))}
      </div>
      <p className="turn-menu-help">WASD / arrows to choose · Enter / Space to confirm</p>
    </div>
  );
}
