import { playbackNow } from "../playback";
import { Component, type ReactNode, useEffect, useMemo, useRef, useState } from "react";
import { Canvas, useFrame } from "@react-three/fiber";
import { Group, NeutralToneMapping } from "three";
import { RoundedBoxGeometry } from "three/addons/geometries/RoundedBoxGeometry.js";
import { DIE_PIPS, DICE_ROLL_DURATION_MS } from "../dicePresentation";
import { DIE_FACES, physicalDieFaceValue, physicalDieRotation, physicalDieSpin } from "./dieGeometry";

interface DieProps {
  value: number;
  rolling: boolean;
  spinning?: boolean;
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
        <DieMesh value={props.value} rolling={props.rolling && !reduced} startedAt={props.startedAt} spinning={props.spinning} />
      </Canvas>
    </div>
  </DieBoundary>;
}

function DieMesh({ value, rolling, startedAt, spinning }: Omit<DieProps, "fallback">) {
  const group = useRef<Group>(null);
  const geometry = useMemo(() => new RoundedBoxGeometry(2, 2, 2, 5, 0.10), []);
  const rotation = physicalDieRotation(value);
  useEffect(() => () => geometry.dispose(), [geometry]);
  useFrame(() => {
    if (!group.current) return;
    if (spinning) {
      const time = (playbackNow() - startedAt) / 1000;
      group.current.rotation.set(time * 4.8, time * 3.2, 0);
      return;
    }
    const progress = rolling ? Math.min(1, Math.max(0, (playbackNow() - startedAt) / DICE_ROLL_DURATION_MS)) : 1;
    group.current.rotation.set(...physicalDieSpin(value, progress));
  });
  return <group ref={group} rotation={rotation}>
    <mesh geometry={geometry}>
      <meshStandardMaterial color="#ffffff" roughness={0.35} metalness={0} />
    </mesh>
    {DIE_FACES.map((face) => <group key={face.value} position={face.position} rotation={face.rotation}>
      {(DIE_PIPS[physicalDieFaceValue(face.value, value)] ?? []).map((pip) =>
        <mesh key={pip} position={[((pip - 1) % 3 - 1) * 0.47, (1 - Math.floor((pip - 1) / 3)) * 0.47, 0]}>
          <circleGeometry args={[0.16, 24]} />
          <meshStandardMaterial color="#101010" roughness={0.58} />
        </mesh>)}
    </group>)}
  </group>;
}
