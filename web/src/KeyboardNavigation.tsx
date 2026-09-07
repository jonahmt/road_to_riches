import { useLayoutEffect, useRef, useState } from "react";
import { installUiKeyboardNavigation } from "./uiKeyboardNavigation";
import "./uiKeyboardNavigation.css";

export function UiKeyboardNavigation() {
  const anchor = useRef<HTMLDivElement>(null);
  const [help, setHelp] = useState("");
  useLayoutEffect(() => {
    const root = anchor.current?.closest<HTMLElement>('main');
    if (root) return installUiKeyboardNavigation(root, setHelp);
  }, []);
  return <div ref={anchor} className="ui-navigation-help" role="status" hidden={!help}>{help}</div>;
}
