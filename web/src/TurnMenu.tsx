import { useEffect, useRef, useState } from "react";

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
  const [selected, setSelected] = useState(0);
  const selectedRef = useRef(0);
  const menuRef = useRef<HTMLDivElement>(null);
  const buttons = useRef<(HTMLButtonElement | null)[]>([]);
  const select = (index: number) => {
    selectedRef.current = index;
    setSelected(index);
  };

  useEffect(() => {
    const handleKey = (event: KeyboardEvent) => {
      const target = event.target;
      if (event.defaultPrevented || event.altKey || event.ctrlKey || event.metaKey ||
          document.body.dataset.gameplayHotkeysSuppressed === "true" ||
          document.body.dataset.squarePickerActive === "true" ||
          (target instanceof HTMLElement && (target.isContentEditable ||
            ["INPUT", "TEXTAREA", "SELECT"].includes(target.tagName)))) return;

      const key = event.key.toLowerCase();
      const previous = ["w", "a", "arrowup", "arrowleft"].includes(key);
      const next = ["s", "d", "arrowdown", "arrowright"].includes(key);
      const confirm = key === "enter" || key === " ";
      if (!previous && !next && !confirm) return;
      // Keep native confirmation on other controls (Tools, camera, etc.).
      if (confirm && target instanceof HTMLElement && target !== document.body &&
          !menuRef.current?.contains(target)) return;

      event.preventDefault();
      event.stopImmediatePropagation();
      if (responsePending) return;
      if (previous || next) {
        const index = (selectedRef.current + (previous ? -1 : 1) + ACTIONS.length) % ACTIONS.length;
        select(index);
        buttons.current[index]?.focus({ preventScroll: true });
      } else if (!event.repeat) {
        onSubmit(ACTIONS[selectedRef.current][0]);
      }
    };
    window.addEventListener("keydown", handleKey, true);
    return () => window.removeEventListener("keydown", handleKey, true);
  }, [onSubmit, responsePending]);

  return (
    <div className="turn-menu" ref={menuRef} role="group" aria-label="Turn actions">
      <div className="action-grid">
        {ACTIONS.map(([value, label], index) => (
          <button key={value} type="button"
            ref={(button) => { buttons.current[index] = button; }}
            className={selected === index ? "is-selected" : "secondary"}
            disabled={responsePending}
            onFocus={() => select(index)}
            onPointerMove={() => { if (!responsePending) select(index); }}
            onClick={() => { select(index); onSubmit(value); }}
          >{label}</button>
        ))}
      </div>
      <p className="turn-menu-help">WASD / arrows to choose · Enter / Space to confirm</p>
    </div>
  );
}
