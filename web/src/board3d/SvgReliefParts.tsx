import { useEffect, useMemo } from "react";
import { type BufferGeometry, Color, Curve, ExtrudeGeometry, TubeGeometry, Vector3 } from "three";
import { SVGLoader } from "three/addons/loaders/SVGLoader.js";

export function SvgReliefParts({ markup, dimmed, depth = 0.16, bevel = 0.018, roughness = 0.46, metalness = 0.08 }: {
  markup: string; dimmed: boolean; depth?: number; bevel?: number; roughness?: number; metalness?: number;
}) {
  const parts = useMemo(() => {
    // SVGLoader does not resolve CSS currentColor inherited from nested groups.
    const document = new DOMParser().parseFromString(markup, "image/svg+xml");
    for (const element of document.querySelectorAll('[fill="currentColor"], [stroke="currentColor"]')) {
      let ancestor: Element | null = element;
      let color = "#f7f7f2";
      while (ancestor) {
        const match = ancestor.getAttribute("style")?.match(/(?:^|;)\s*color:\s*([^;]+)/);
        const attributeColor = ancestor.getAttribute("color");
        if (match || attributeColor) { color = match?.[1] ?? attributeColor!; break; }
        ancestor = ancestor.parentElement;
      }
      for (const attribute of ["fill", "stroke"]) {
        if (element.getAttribute(attribute) === "currentColor") element.setAttribute(attribute, color);
      }
    }
    const data = new SVGLoader().parse(new XMLSerializer().serializeToString(document));
    return data.paths.flatMap<{ geometry: BufferGeometry; color: Color }>((path) => {
      const style = path.userData?.style as { fill?: string; stroke?: string; strokeWidth?: number } | undefined;
      if (style?.fill === "none") {
        if (!style.stroke || style.stroke === "none") return [];
        return path.subPaths.map((subPath) => {
          const curve = new class extends Curve<Vector3> {
            constructor() { super(); }
            getPoint(t: number) { const point = subPath.getPoint(t); return new Vector3(point.x, point.y, 0); }
          }();
          return { geometry: new TubeGeometry(curve, 48, (style.strokeWidth ?? 0.06) / 2, 6, subPath.autoClose),
            color: new Color(style.stroke) };
        });
      }
      return path.toShapes().map((shape) => ({
        geometry: new ExtrudeGeometry(shape, { depth, bevelEnabled: true,
          bevelSegments: bevel > 0.02 ? 3 : 1, steps: 1, bevelSize: bevel, bevelThickness: bevel, curveSegments: bevel > 0.02 ? 16 : 10 }),
        color: path.color.clone(),
      }));
    });
  }, [markup, depth, bevel]);
  useEffect(() => () => parts.forEach((part) => part.geometry.dispose()), [parts]);
  return <>{parts.map((part, index) => <mesh key={index} geometry={part.geometry} position={[0, 0, index * 0.003]} castShadow receiveShadow>
    <meshStandardMaterial color={dimmed ? "#43505b" : part.color} roughness={roughness} metalness={metalness} />
  </mesh>)}</>;
}
