import { useEffect, useMemo } from "react";
import { CanvasTexture, EquirectangularReflectionMapping, SRGBColorSpace } from "three";

// Static panoramic sky; used only as the scene background, not as an extra
// environment-lighting pass. No remote images, animated clouds or sky geometry.
export function SkyBackdrop() {
  const texture = useMemo(() => {
    const canvas = document.createElement("canvas"); canvas.width = 2048; canvas.height = 1024;
    const ctx = canvas.getContext("2d")!;
    const sky = ctx.createLinearGradient(0, 0, 0, 1024);
    sky.addColorStop(0, "#6499c1"); sky.addColorStop(0.40, "#a6cbdc");
    sky.addColorStop(0.48, "#d4e0d6"); sky.addColorStop(0.55, "#d4e0d6");
    sky.addColorStop(1, "#b9c9b9"); ctx.fillStyle = sky; ctx.fillRect(0, 0, 2048, 1024);
    // Repeat edge clouds across the panorama seam. All positions are deterministic.
    for (const [x, y, width] of [[140, 385, 190], [510, 430, 235], [945, 350, 170], [1360, 415, 240], [1850, 380, 215]]) {
      for (const offset of [-2048, 0, 2048]) {
        for (let puff = 0; puff < 5; puff++) {
          const px = x + offset + (puff - 2) * width * 0.19;
          const py = y - Math.sin(puff * 1.1) * 17;
          ctx.save(); ctx.translate(px, py); ctx.scale(width * 0.42, 29 + (puff % 3) * 8);
          const cloud = ctx.createRadialGradient(0, 0, 0.2, 0, 0, 1);
          cloud.addColorStop(0, "#fffdf0a0"); cloud.addColorStop(0.6, "#fffdf04a"); cloud.addColorStop(1, "#fffdf000");
          ctx.fillStyle = cloud; ctx.fillRect(-1, -1, 2, 2); ctx.restore();
        }
      }
    }
    const result = new CanvasTexture(canvas); result.colorSpace = SRGBColorSpace;
    result.mapping = EquirectangularReflectionMapping; return result;
  }, []);
  useEffect(() => () => texture.dispose(), [texture]);
  return <>
    <primitive attach="background" object={texture} />
    <fog attach="fog" args={["#d4e0d6", 150, 280]} />
  </>;
}
