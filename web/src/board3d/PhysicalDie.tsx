import { Component, type ReactNode, useEffect, useMemo, useRef, useState } from "react";
import { Canvas, useFrame } from "@react-three/fiber";
import { Group, NeutralToneMapping } from "three";
import { RoundedBoxGeometry } from "three/addons/geometries/RoundedBoxGeometry.js";
import { DIE_PIPS, DICE_ROLL_DURATION_MS } from "../dicePresentation";
import { DIE_FACES, physicalDieFaceValue, physicalDieRotation } from "./dieGeometry";

interface DieProps {
  value: number;
  rolling: boolean;
  startedAt: number;
  fallback: ReactNode;
}

class DieBoundary extends Component<{ children: ReactNode; fallback: ReactNode }, { failed: boolean }> {
  state = { failed: false };
  static getDerivedStateFromError() { return { failed: true }; }
  render() { return this.state.failed ? this.props.fallback : this.props.children; }
}

export default function PhysicalDie(props: DieProps) {
  const root = useRef<HTMLDivElement>(null);
  const [failed, setFailed] = useState(false);
  const [reduced, setReduced] = useState(() => window.matchMedia("(prefers-reduced-motion: reduce)").matches);
  useEffect(() => {
    const query = window.matchMedia("(prefers-reduced-motion: reduce)");
    const update = () => setReduced(query.matches);
    query.addEventListener("change", update);
    return () => query.removeEventListener("change", update);
  }, []);
  useEffect(() => {
    const canvas = root.current?.querySelector("canvas");
    const lost = (event: Event) => { event.preventDefault(); setFailed(true); };
    canvas?.addEventListener("webglcontextlost", lost);
    return () => canvas?.removeEventListener("webglcontextlost", lost);
  }, []);
  if (failed) return props.fallback;
  return <DieBoundary fallback={props.fallback}>
    <div className="solid-die-canvas" ref={root}>
      <Canvas orthographic dpr={[1, 1.75]}
        camera={{ left: -1.55, right: 1.55, top: 1.55, bottom: -1.55,
          position: [0, 0, 8], near: 0.1, far: 30 }}
        frameloop={props.rolling && !reduced ? "always" : "demand"}
        gl={{ alpha: true, antialias: true, toneMapping: NeutralToneMapping }} fallback={props.fallback}>
        <ambientLight intensity={1.5} />
        <directionalLight position={[-3, 5, 6]} intensity={2.4} />
        <directionalLight position={[4, -2, -2]} intensity={0.5} color="#8bbdce" />
        <group rotation={[0.18, -0.28, -0.04]}>
          <DieMesh value={props.value} rolling={props.rolling && !reduced} startedAt={props.startedAt} />
        </group>
      </Canvas>
    </div>
  </DieBoundary>;
}

function DieMesh({ value, rolling, startedAt }: Omit<DieProps, "fallback">) {
  const group = useRef<Group>(null);
  const geometry = useMemo(() => new RoundedBoxGeometry(2, 2, 2, 5, 0.16), []);
  const rotation = physicalDieRotation(value);
  useEffect(() => () => geometry.dispose(), [geometry]);
  useFrame(() => {
    if (!group.current) return;
    const progress = rolling ? Math.min(1, Math.max(0, (performance.now() - startedAt) / DICE_ROLL_DURATION_MS)) : 1;
    const remaining = Math.pow(1 - progress, 2);
    group.current.rotation.set(rotation[0] + remaining * Math.PI * 6,
      rotation[1] + remaining * Math.PI * 8, rotation[2] + remaining * Math.PI * 2);
    group.current.position.y = Math.sin(progress * Math.PI) * 0.18;
    group.current.scale.setScalar(0.84 + progress * 0.16);
  });
  return <group ref={group} rotation={rotation}>
    <mesh geometry={geometry}>
      <meshStandardMaterial color="#fffdf5" roughness={0.28} metalness={0.03} />
    </mesh>
    {DIE_FACES.map((face) => <group key={face.value} position={face.position} rotation={face.rotation}>
      {(DIE_PIPS[physicalDieFaceValue(face.value, value)] ?? []).map((pip) =>
        <mesh key={pip} position={[((pip - 1) % 3 - 1) * 0.47, (1 - Math.floor((pip - 1) / 3)) * 0.47, 0]}>
          <circleGeometry args={[0.14, 24]} />
          <meshStandardMaterial color="#14212c" roughness={0.58} />
        </mesh>)}
    </group>)}
  </group>;
}
