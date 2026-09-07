import { useEffect, useMemo, useRef } from "react";
import { useFrame, useThree } from "@react-three/fiber";
import { ExtrudeGeometry, Group, Shape, Vector3 } from "three";
import { getPathKeyActions } from "../controls";
import type { InputRequest } from "../protocol";
import { projectMovementRequest, type BoardProjector } from "./geometry";
import type { MovementGuide } from "./movementPresentation";

export type MovementButtons = Map<MovementGuide["value"], HTMLButtonElement>;

export function MovementGuideMeshes({ request, guides, buttons, projectorRef, reduced }: {
  request: InputRequest;
  guides: MovementGuide[];
  buttons: MovementButtons;
  projectorRef: { current: BoardProjector | null };
  reduced: boolean;
}) {
  const groups = useRef(new Map<MovementGuide["value"], Group>());
  const { camera, size } = useThree();
  const geometry = useMemo(() => {
    const shape = new Shape();
    shape.moveTo(-0.86, -0.31); shape.lineTo(0.07, -0.31); shape.lineTo(0.07, -0.63);
    shape.lineTo(0.96, 0); shape.lineTo(0.07, 0.63); shape.lineTo(0.07, 0.31);
    shape.lineTo(-0.86, 0.31); shape.closePath();
    return new ExtrudeGeometry(shape, { depth: 0.13, bevelEnabled: true,
      bevelSegments: 2, bevelThickness: 0.035, bevelSize: 0.04, steps: 1 });
  }, []);
  useEffect(() => () => geometry.dispose(), [geometry]);
  const projected = useMemo(() => new Vector3(), []);
  useFrame(({ clock }) => {
    const actions = getPathKeyActions(projectMovementRequest(request, projectorRef.current));
    for (const guide of guides) {
      const group = groups.current.get(guide.value);
      const button = buttons.get(guide.value);
      if (!group || !button) continue;
      group.position.y = guide.position[1] + (reduced ? 0 : Math.sin(clock.elapsedTime * 4) * 0.07);
      // Keep the hit target and caption still while the decorative mesh floats.
      projected.set(...guide.position).project(camera);
      button.style.visibility = projected.z >= -1 && projected.z <= 1 &&
        Math.abs(projected.x) < 1.1 && Math.abs(projected.y) < 1.1 ? "visible" : "hidden";
      button.style.transform = `translate(${(projected.x + 1) * size.width / 2}px, ${(1 - projected.y) * size.height / 2}px) translate(-50%, -50%)`;
      const key = actions.find((action) => action.value === guide.value)?.key.toUpperCase().split("").join(" + ") ?? "";
      const caption = guide.value === "undo" ? `Undo${key ? ` · ${key}` : ""}` : key;
      const text = button.firstElementChild;
      if (text && text.textContent !== caption) text.textContent = caption;
      const label = `${guide.label}${key ? `. Press ${key}` : ""}`;
      if (button.getAttribute("aria-label") !== label) {
        button.setAttribute("aria-label", label);
        button.title = label;
      }
    }
  });
  return <>{guides.map((guide) => <group key={guide.value} position={guide.position} rotation={[0, guide.rotation, 0]}
    ref={(node) => { if (node) groups.current.set(guide.value, node); else groups.current.delete(guide.value); }}>
    <group rotation={[-Math.PI / 2, 0, 0]}>
      <mesh geometry={geometry} renderOrder={1000}>
        <meshBasicMaterial attach="material-0" color="#f4fff2" depthTest={false} depthWrite={false} toneMapped={false} />
        <meshBasicMaterial attach="material-1" color={guide.value === "undo" ? "#78552a" : "#206143"} depthTest={false} depthWrite={false} toneMapped={false} />
      </mesh>
      <mesh geometry={geometry} position={[0, 0, 0.16]} scale={[0.83, 0.81, 0.35]} renderOrder={1001}>
        <meshBasicMaterial color={guide.value === "undo" ? "#ffd369" : "#42de70"} depthTest={false} depthWrite={false} toneMapped={false} />
      </mesh>
    </group>
  </group>)}</>;
}

export function MovementGuideButtons({ guides, buttons, onChoose }: {
  guides: MovementGuide[]; buttons: MovementButtons; onChoose: (value: number | "undo") => void;
}) {
  const down = useRef<{ x: number; y: number } | null>(null);
  if (!guides.length) return null;
  return <div className="board3d-movement-guides" role="group" aria-label="Movement choices">
    {guides.map((guide) => <button key={guide.value} type="button" className="board3d-route-button"
      aria-label={guide.label} data-movement-value={guide.value}
      ref={(node) => { if (node) buttons.set(guide.value, node); else buttons.delete(guide.value); }}
      onPointerDown={(event) => { down.current = { x: event.clientX, y: event.clientY }; }}
      onClick={(event) => {
        if (event.detail !== 0 && (!down.current || Math.hypot(event.clientX - down.current.x, event.clientY - down.current.y) > 6)) return;
        onChoose(guide.value);
      }}><span className="board3d-route-key">{guide.value === "undo" ? "Undo" : ""}</span></button>)}
  </div>;
}
