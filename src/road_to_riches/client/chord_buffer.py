"""Two-key chord buffering with a short timeout.

Used by any input mode that wants to support chord combos (e.g. WASD
diagonals like "wa") on top of single keypresses. The buffer holds one
key for `timeout` seconds; if a second key arrives the caller resolves
the combo, otherwise the single key fires.

The caller supplies callbacks per `feed()` call so a single ChordBuffer
instance can be shared across mutually-exclusive input modes.
"""

from __future__ import annotations

from typing import Callable, Protocol

from textual.timer import Timer


class _TimerHost(Protocol):
    def set_timer(self, delay: float, callback: Callable[[], None]) -> Timer: ...


class ChordBuffer:
    """Generic two-key chord buffer with a single pending-key slot.

    Behavior on `feed(key, ...)`:
      - If the buffer is empty and `may_combo(key)` is True, store `key`
        and start a timer; on timeout, call `on_single(key)`.
      - If the buffer is empty and `may_combo(key)` is False, call
        `on_single(key)` immediately.
      - If a key is already buffered, cancel the timer, then try
        `on_combo(buffered + key)` and `on_combo(key + buffered)` in
        order. If either returns True, stop. Otherwise call
        `on_single(key)` (the second key wins as a fallback — matches
        the original keypress-mode behavior).
    """

    def __init__(self, host: _TimerHost, timeout: float = 0.25) -> None:
        self._host = host
        self._timeout = timeout
        self._buffered: str = ""
        self._timer: Timer | None = None
        self._pending_on_single: Callable[[str], None] | None = None

    def reset(self) -> None:
        """Cancel any pending timer and clear the buffer."""
        if self._timer is not None:
            self._timer.stop()
            self._timer = None
        self._buffered = ""
        self._pending_on_single = None

    def feed(
        self,
        key: str,
        on_combo: Callable[[str], bool],
        on_single: Callable[[str], None],
        may_combo: Callable[[str], bool],
    ) -> None:
        """Process one keypress through the chord buffer."""
        # A new key always invalidates any pending timer.
        if self._timer is not None:
            self._timer.stop()
            self._timer = None

        if self._buffered:
            first = self._buffered
            self._buffered = ""
            self._pending_on_single = None
            if on_combo(first + key):
                return
            if on_combo(key + first):
                return
            on_single(key)
            return

        if may_combo(key):
            self._buffered = key
            self._pending_on_single = on_single
            self._timer = self._host.set_timer(self._timeout, self._on_timeout)
        else:
            on_single(key)

    def _on_timeout(self) -> None:
        self._timer = None
        key = self._buffered
        self._buffered = ""
        callback = self._pending_on_single
        self._pending_on_single = None
        if key and callback is not None:
            callback(key)
