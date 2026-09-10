// A monotonic presentation clock. Network timeouts and game rules use real time.
let speed = 1, origin = 0, accumulated = 0;
export function playbackNow(real = performance.now()) { return accumulated + (real - origin) * speed; }
export function playbackSpeed() { return speed; }
export function setPlaybackSpeed(value: number) {
  const next = [1, 1.5, 2].includes(value) ? value : 1;
  const now = performance.now(); accumulated = playbackNow(now); origin = now; speed = next;
}
export function syncAnimationSpeed() {
  for (const animation of document.getAnimations()) {
    if (animation.playbackRate !== speed) animation.updatePlaybackRate(speed);
  }
}
