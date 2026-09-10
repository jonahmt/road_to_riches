import { createContext, useContext, useEffect, useMemo, useState } from "react";
import { CanvasTexture, RepeatWrapping, SRGBColorSpace, Texture } from "three";

export const TextureReadinessContext = createContext<Set<object> | null>(null);

export function useTileTexture(svg: string) {
  const pending = useContext(TextureReadinessContext);
  const [texture, setTexture] = useState<Texture | null>(null);
  useEffect(() => {
    const ticket = {};
    pending?.add(ticket);
    let cancelled = false;
    let created: Texture | null = null;
    const image = new Image();
    image.onload = () => {
      if (cancelled) return;
      created = new Texture(image);
      created.colorSpace = SRGBColorSpace;
      created.anisotropy = 8;
      created.needsUpdate = true;
      setTexture(created);
      pending?.delete(ticket);
    };
    image.onerror = () => { pending?.delete(ticket); };
    image.src = `data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg)}`;
    return () => { cancelled = true; pending?.delete(ticket); image.onload = null; image.onerror = null; created?.dispose(); };
  }, [svg]);
  return texture;
}

function paintedTexture(width: number, height: number, draw: (context: CanvasRenderingContext2D) => void) {
  const canvas = document.createElement("canvas");
  canvas.width = width; canvas.height = height;
  const context = canvas.getContext("2d");
  if (context) draw(context);
  const texture = new CanvasTexture(canvas);
  texture.colorSpace = SRGBColorSpace;
  texture.anisotropy = 8;
  return texture;
}

export function useRoofTexture() {
  const texture = useMemo(() => {
    const result = paintedTexture(256, 256, (context) => {
      context.fillStyle = "#89949e"; context.fillRect(0, 0, 256, 256);
      for (let row = 0; row < 8; row++) {
        for (let column = -1; column < 8; column++) {
          const x = column * 40 + (row % 2) * 20;
          const y = row * 32;
          const shade = 170 + ((column * 7 + row * 11 + 37) % 5) * 9;
          context.fillStyle = `rgb(${shade},${shade + 3},${shade + 5})`;
          context.fillRect(x + 1, y + 1, 38, 29);
          context.fillStyle = "#ffffff55"; context.fillRect(x + 2, y + 2, 36, 2);
          context.fillStyle = "#25354550"; context.fillRect(x + 1, y + 28, 38, 3);
        }
      }
    });
    result.wrapS = result.wrapT = RepeatWrapping;
    return result;
  }, []);
  useEffect(() => () => texture.dispose(), [texture]);
  return texture;
}

export function useAwningTexture(color: string, closed: boolean) {
  const texture = useMemo(() => paintedTexture(256, 64, (context) => {
    context.fillStyle = closed ? "#b4b4a7" : "#fff2d4";
    context.fillRect(0, 0, 256, 64);
    context.fillStyle = closed ? "#626b73" : color;
    for (let stripe = 0; stripe < 8; stripe += 2) context.fillRect(stripe * 32, 0, 32, 64);
    const shade = context.createLinearGradient(0, 0, 0, 64);
    shade.addColorStop(0, "#ffffff40"); shade.addColorStop(0.7, "#ffffff00"); shade.addColorStop(1, "#18232e33");
    context.fillStyle = shade; context.fillRect(0, 0, 256, 64);
  }), [color, closed]);
  useEffect(() => () => texture.dispose(), [texture]);
  return texture;
}
