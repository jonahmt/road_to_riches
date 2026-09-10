import { navigationDirection, nextControl } from "./uiNavigation";

const CONTROLS = 'button, a[href], input:not([type="hidden"]), select, textarea, summary, [role="button"][tabindex]';
const SCOPES = '[aria-modal="true"], .dev-panel, .square-picker, .action-panel, .connect-card, [data-ui-scope]';
const SPATIAL = '.square-picker, .stock-overlay, .venture-grid-overlay';

type UiControl = HTMLElement | SVGElement;
const isUiControl = (element: unknown): element is UiControl => element instanceof HTMLElement || element instanceof SVGElement;

function visible(element: UiControl): boolean {
  return element.getClientRects().length > 0 && element.checkVisibility({ checkVisibilityCSS: true }) &&
    !element.closest('[hidden], [inert], [aria-hidden="true"]');
}
function enabled(element: UiControl): boolean {
  return visible(element) && getComputedStyle(element).opacity !== '0' && !element.matches(':disabled, [aria-disabled="true"]') &&
    !element.closest('[aria-busy="true"], .is-resolving, [data-ui-pointer-only]');
}
function textField(element: UiControl): boolean {
  return (element instanceof HTMLElement && element.isContentEditable) || element instanceof HTMLTextAreaElement ||
    (element instanceof HTMLInputElement && !['number', 'range', 'checkbox', 'radio', 'file', 'button', 'submit'].includes(element.type));
}
function controls(scope: HTMLElement): UiControl[] {
  return [...scope.querySelectorAll<UiControl>(CONTROLS)].filter(enabled);
}

/** One early capture listener arbitrates menu input before individual game shortcuts. */
export function installUiKeyboardNavigation(root: HTMLElement, onHelp: (help: string) => void): () => void {
  let selected: UiControl | null = null;
  let selectedScope: HTMLElement | null = null;
  let browsingField: UiControl | null = null;
  let focusing = false;
  let keyboard = false;
  const remembered = new WeakMap<HTMLElement, UiControl>();
  const held = new Set<string>();
  let directionScope: string | null = null;

  function scope(): HTMLElement {
    const all = [...root.querySelectorAll<HTMLElement>(SCOPES)].filter(visible);
    const modal = all.filter(item => item.matches('[aria-modal="true"]')).at(-1);
    if (modal) return modal;
    const tools = all.find(item => item.matches('.dev-panel'));
    if (tools) return tools;
    const picker = all.find(item => item.matches('.square-picker'));
    if (picker) return picker;
    const focused = document.activeElement;
    if (isUiControl(focused) && focused.matches(CONTROLS) && root.contains(focused)) {
      const own = focused.closest<HTMLElement>(SCOPES);
      if (own && visible(own)) return own;
      // Tab and mouse can reach header, camera, inspector and report controls.
      return root;
    }
    return all.find(item => item.matches('.action-panel, .connect-card')) ?? root;
  }
  function spatialOwns(current: HTMLElement): boolean {
    if (!current.matches(SPATIAL)) return false;
    const active = document.activeElement;
    return !(isUiControl(active) && current.contains(active) && active.matches(CONTROLS));
  }
  function mark(element: UiControl | null, current: HTMLElement) {
    if (selected !== element) {
      selected?.removeAttribute('data-ui-selected');
      selected = element;
      element?.setAttribute('data-ui-selected', 'true');
    }
    selectedScope = current;
    if (element) remembered.set(current, element);
    if (!keyboard) { onHelp(''); return; }
    onHelp(spatialOwns(current) ? 'WASD / arrows: board selection · Tab: buttons'
      : element && textField(element) ? browsingField === element
        ? 'WASD / arrows: choose · Enter: edit text · Tab: next control'
        : 'Type to edit · Esc: return to menu navigation'
      : element instanceof HTMLInputElement && ['number', 'range'].includes(element.type)
        ? 'A/D or ←/→: amount · W/S or ↑/↓: choose control · Enter: confirm'
      : element instanceof HTMLSelectElement
        ? 'A/D or ←/→: option · W/S or ↑/↓: choose control'
      : 'WASD / arrows: choose · Enter / Space: confirm · Tab: next control');
  }
  function refresh() {
    const current = scope();
    if (spatialOwns(current)) { mark(null, current); return; }
    const movement = root.dataset.request === 'CHOOSE_PATH' || root.dataset.pacingType === 'piece_moved';
    if (movement && !current.matches('.dev-panel, [aria-modal="true"]') &&
        !(isUiControl(document.activeElement) && document.activeElement.matches(CONTROLS))) {
      mark(null, current); return;
    }
    const available = controls(current);
    const active = document.activeElement;
    const previous = remembered.get(current);
    const choice = selectedScope === current && selected && available.includes(selected) ? selected
      : isUiControl(active) && available.includes(active) ? active
      : previous && available.includes(previous) ? previous : available[0] ?? null;
    mark(choice, current);
  }
  function focus(element: UiControl, current: HTMLElement) {
    if (textField(element)) browsingField = element;
    focusing = true;
    element.focus({ preventScroll: true });
    focusing = false;
    element.scrollIntoView({ block: 'nearest', inline: 'nearest' });
    mark(element, current);
  }
  function consume(event: KeyboardEvent) { event.preventDefault(); event.stopImmediatePropagation(); }
  function keyDown(event: KeyboardEvent) {
    if (event.defaultPrevented || event.altKey || event.ctrlKey || event.metaKey || event.isComposing) return;
    const key = event.key.toLowerCase();
    const direction = navigationDirection(key);
    const confirm = key === 'enter' || key === ' ';
    if (root.classList.contains('is-playing') && root.dataset.boardReady === 'false' && !root.querySelector('.board3d-error button') && (direction || confirm)) {
      consume(event); return;
    }
    const current = scope();
    const active = isUiControl(document.activeElement) ? document.activeElement : null;
    if (confirm) {
      const repeated = event.repeat || held.has(key);
      held.add(key);
      if (repeated && !(active && textField(active) && browsingField !== active)) { consume(event); return; }
    }
    // A held direction must never spill into a different dialog after a response.
    if (direction) {
      const stamp = `${root.dataset.request}:${current.className}:${current.querySelector('h1, h2')?.textContent}`;
      if (event.repeat && directionScope !== stamp) { consume(event); return; }
      directionScope = stamp;
    }
    if (active && textField(active) && browsingField !== active) {
      if (key === 'escape') {
        consume(event); keyboard = true; browsingField = active; mark(active, current);
      }
      return;
    }
    if (key === 'escape' && current.matches('.dev-panel')) {
      consume(event); current.querySelector<HTMLButtonElement>('[data-ui-back]')?.click(); return;
    }
    if (!direction && !confirm && key !== 'tab') return;
    keyboard = true;
    if (spatialOwns(current)) {
      if (key === 'tab') {
        const available = controls(current);
        if (available.length) { consume(event); focus(event.shiftKey ? available.at(-1)! : available[0], current); }
      } else mark(null, current);
      return;
    }
    // Movement retains its buffering, including taps during a jump.
    const path = root.dataset.request === 'CHOOSE_PATH' || root.dataset.pacingType === 'piece_moved';
    if (path && !current.matches('.dev-panel, [aria-modal="true"]') &&
        (!active || !active.matches(CONTROLS) || active.closest('.movement-key-actions, .key-action-list'))) return;
    refresh();
    const available = controls(current);
    if (key === 'tab') {
      if (!current.matches('[aria-modal="true"], .square-picker, .dev-panel')) return;
      consume(event);
      const index = active ? available.indexOf(active) : -1;
      const next = index + (event.shiftKey ? -1 : 1);
      if (current.matches(SPATIAL) && (next < 0 || next >= available.length)) {
        current.tabIndex = -1; current.focus(); mark(null, current); return;
      }
      if (available.length) focus(available[(next + available.length) % available.length], current);
      return;
    }
    consume(event);
    if (!selected || !available.includes(selected)) return;
    if (direction) {
      if (direction === 'left' || direction === 'right') {
        const step = direction === 'left' ? -1 : 1;
        if (selected instanceof HTMLInputElement && ['number', 'range'].includes(selected.type)) {
          const input = selected;
          focus(input, current);
          if (input.readOnly) return;
          const before = input.value;
          try { step < 0 ? input.stepDown() : input.stepUp(); } catch { return; }
          const after = input.value;
          Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value')!.set!.call(input, before);
          Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value')!.set!.call(input, after);
          input.dispatchEvent(new Event('input', { bubbles: true }));
          input.dispatchEvent(new Event('change', { bubbles: true }));
          return;
        }
        if (selected instanceof HTMLSelectElement) {
          focus(selected, current);
          const options = [...selected.options].filter(option => !option.disabled);
          const actual = options.findIndex(option => option.value === (selected as HTMLSelectElement).value);
          const option = options[(Math.max(actual, 0) + step + options.length) % options.length];
          if (option) { selected.value = option.value; selected.dispatchEvent(new Event('change', { bubbles: true })); }
          return;
        }
      }
      const next = nextControl(available.map(item => item.getBoundingClientRect()), available.indexOf(selected), direction);
      if (next >= 0) focus(available[next], current);
    } else if (confirm) {
      if (textField(selected)) { browsingField = null; selected.focus(); mark(selected, current); return; }
      if (selected instanceof HTMLInputElement && ['number', 'range'].includes(selected.type)) {
        const submit = selected.form?.querySelector<HTMLButtonElement>('button[type="submit"]:not(:disabled)')
          ?? current.querySelector<HTMLButtonElement>('[data-ui-confirm]:not(:disabled)');
        if (submit && enabled(submit)) submit.click();
        else {
          const next = available[available.indexOf(selected) + 1];
          if (next) focus(next, current);
        }
      } else if (selected instanceof HTMLSelectElement) {
        selected.focus();
      } else {
        if (selected instanceof HTMLElement) selected.click();
        else selected.dispatchEvent(new MouseEvent('click', { bubbles: true }));
      }
    }
  }
  function onFocus(event: FocusEvent) {
    if (focusing) return;
    const target = event.target;
    if (isUiControl(target) && target.matches(CONTROLS)) {
      browsingField = null;
      const current = scope();
      if (current.contains(target) && enabled(target)) mark(target, current);
    }
  }
  function onPointer(event: PointerEvent) {
    if (!event.movementX && !event.movementY) return;
    const target = event.target instanceof Element ? event.target.closest<UiControl>(CONTROLS) : null;
    const current = scope();
    if (target && current.contains(target) && enabled(target)) mark(target, current);
  }
  const up = (event: KeyboardEvent) => { held.delete(event.key.toLowerCase()); };
  const blur = () => { held.clear(); directionScope = null; };
  let refreshFrame = 0;
  const scheduleRefresh = () => {
    refresh();
    cancelAnimationFrame(refreshFrame);
    // Visibility can change through an ancestor's CSS after the DOM mutation.
    refreshFrame = requestAnimationFrame(refresh);
  };
  const observer = new MutationObserver(scheduleRefresh);
  observer.observe(root, { subtree: true, childList: true, attributes: true,
    attributeFilter: ['disabled', 'hidden', 'class', 'aria-busy', 'aria-hidden', 'data-request', 'data-board-ready', 'data-pacing-type', 'data-tools-open'] });
  window.addEventListener('keydown', keyDown, true);
  window.addEventListener('keyup', up, true);
  window.addEventListener('blur', blur);
  root.addEventListener('focusin', onFocus);
  root.addEventListener('pointermove', onPointer);
  refresh();
  return () => {
    observer.disconnect(); cancelAnimationFrame(refreshFrame); selected?.removeAttribute('data-ui-selected');
    window.removeEventListener('keydown', keyDown, true); window.removeEventListener('keyup', up, true);
    window.removeEventListener('blur', blur); root.removeEventListener('focusin', onFocus);
    root.removeEventListener('pointermove', onPointer);
  };
}
