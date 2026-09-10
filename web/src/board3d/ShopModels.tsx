import { playbackNow } from "../playback";
import { useEffect, useLayoutEffect, useMemo, useRef } from "react";
import { useFrame } from "@react-three/fiber";
import { Color, DoubleSide, ExtrudeGeometry, Group, Shape } from "three";
import { RoundedBoxGeometry } from "three/addons/geometries/RoundedBoxGeometry.js";
import { AI_ADJACENT_STEP_ANIMATION_MS, HUMAN_ADJACENT_STEP_ANIMATION_MS } from "../cameraTiming";
import { shopModelPose, TILE_TOP } from "./geometry";
import { useAwningTexture, useRoofTexture, useTileTexture } from "./textures";

export function ShopRentPlaque({ markup, dimmed, activeOccupant }: { markup: string; dimmed: boolean; activeOccupant: boolean }) {
  const texture = useTileTexture(markup);
  const base = useMemo(() => new RoundedBoxGeometry(3.3, 0.12, 1.08, 2, 0.05), []);
  useEffect(() => () => base.dispose(), [base]);
  return <group position={[0, TILE_TOP + 0.045, activeOccupant ? 1.4 : 1.12]}>
    <mesh geometry={base} receiveShadow>
      <meshStandardMaterial color={dimmed ? "#28303a" : "#32415b"} roughness={0.5} metalness={0.12} />
    </mesh>
    <mesh position={[0, 0.066, 0]} rotation={[-Math.PI / 2, 0, 0]}>
      <planeGeometry args={[3.2, 1]} />
      <meshBasicMaterial key={texture?.uuid ?? "loading"} map={texture} color={dimmed ? "#566274" : "#ffffff"} toneMapped={false} />
    </mesh>
  </group>;
}

export function ShopSign({ markup, dimmed }: { markup: string; dimmed: boolean }) {
  const texture = useTileTexture(markup);
  return <group position={[0, TILE_TOP, -0.42]}>
    {[-0.84, 0.84].map((x) => <group key={x} position={[x, 0, 0]}>
      <mesh position={[0, 0.47, 0]} castShadow>
        <boxGeometry args={[0.18, 0.94, 0.18]} /><meshStandardMaterial color="#63412b" roughness={0.9} />
      </mesh>
      <mesh position={[0, 0.06, 0]} receiveShadow>
        <boxGeometry args={[0.34, 0.12, 0.34]} /><meshStandardMaterial color="#9c8462" />
      </mesh>
    </group>)}
    <group position={[0, 1.06, 0]} rotation={[-0.24, 0, 0]}>
      <mesh castShadow><boxGeometry args={[2.68, 1.27, 0.2]} /><meshStandardMaterial color="#6c442b" roughness={0.8} /></mesh>
      {[0, Math.PI].map((angle) => <group key={angle} rotation={[0, angle, 0]}>
        <mesh position={[0, 0, 0.106]}>
          <planeGeometry args={[2.64, 1.23]} />
          <meshStandardMaterial key={texture?.uuid ?? "loading"} map={texture}
            color={dimmed ? "#505866" : "#ffffff"} roughness={0.85} />
        </mesh>
      </group>)}
    </group>
  </group>;
}

function ShopWindow({ x, y, z, rotation = 0, closed }: {
  x: number; y: number; z: number; rotation?: number; closed: boolean;
}) {
  return <group position={[x, y, z]} rotation={[0, rotation, 0]}>
    <mesh><boxGeometry args={[0.44, 0.5, 0.065]} /><meshStandardMaterial color="#7b5638" /></mesh>
    <mesh position={[0, 0, 0.038]}><planeGeometry args={[0.34, 0.39]} />
      <meshStandardMaterial color={closed ? "#36424a" : "#63a5c6"} roughness={0.3}
        emissive={closed ? "#000000" : "#164867"} emissiveIntensity={0.15} />
    </mesh>
    <mesh position={[0, 0, 0.048]}><boxGeometry args={[0.04, 0.4, 0.035]} /><meshStandardMaterial color="#fff0cd" /></mesh>
    <mesh position={[0, -0.02, 0.048]}><boxGeometry args={[0.34, 0.035, 0.035]} /><meshStandardMaterial color="#fff0cd" /></mesh>
    <mesh position={[0, -0.28, 0.045]} castShadow><boxGeometry args={[0.5, 0.07, 0.15]} /><meshStandardMaterial color="#ead7a7" /></mesh>
  </group>;
}

export function ShopModel({ color, closed, activeOccupant, reduced }: {
  color: string; closed: boolean; activeOccupant: boolean; reduced: boolean;
}) {
  const group = useRef<Group>(null);
  const pose = shopModelPose(activeOccupant);
  const initialPose = useRef(pose);
  const transition = useRef({ from: pose, start: 0, duration: 0 });
  // Install the new motion before a frame can apply the new target pose.
  useLayoutEffect(() => {
    if (!group.current) return;
    transition.current = {
      from: { position: [group.current.position.x, TILE_TOP, group.current.position.z], scale: group.current.scale.x },
      start: playbackNow() + (activeOccupant || reduced ? 0
        : Math.max(AI_ADJACENT_STEP_ANIMATION_MS, HUMAN_ADJACENT_STEP_ANIMATION_MS)),
      // Finish shrinking before an arriving figure completes its step.
      duration: reduced ? 0 : activeOccupant ? 80 : 160,
    };
  }, [activeOccupant, reduced]);
  useFrame(() => {
    if (!group.current) return;
    const motion = transition.current;
    const progress = motion.duration ? Math.max(0, Math.min(1, (playbackNow() - motion.start) / motion.duration)) : 1;
    const blend = progress * progress * (3 - 2 * progress);
    group.current.position.x = motion.from.position[0] + (pose.position[0] - motion.from.position[0]) * blend;
    group.current.position.z = motion.from.position[2] + (pose.position[2] - motion.from.position[2]) * blend;
    group.current.scale.setScalar(motion.from.scale + (pose.scale - motion.from.scale) * blend);
  });
  const shingles = useRoofTexture();
  const awning = useAwningTexture(color, closed);
  const roofColor = useMemo(() => new Color(closed ? "#69717c" : color).multiplyScalar(0.78), [color, closed]);
  const roof = useMemo(() => {
    const gable = new Shape();
    gable.moveTo(-1.08, 0); gable.lineTo(1.08, 0); gable.lineTo(0, 0.77); gable.closePath();
    return new ExtrudeGeometry(gable, { depth: 1.82, bevelEnabled: true,
      bevelSegments: 1, steps: 1, bevelSize: 0.025, bevelThickness: 0.025 });
  }, []);
  useEffect(() => () => roof.dispose(), [roof]);
  return <group ref={group} position={initialPose.current.position} scale={initialPose.current.scale}>
    <mesh position={[0, 0.08, 0]} receiveShadow><boxGeometry args={[1.97, 0.16, 1.7]} /><meshStandardMaterial color="#b8a27b" /></mesh>
    <mesh position={[0, 0.72, 0]} castShadow receiveShadow>
      <boxGeometry args={[1.8, 1.28, 1.5]} /><meshStandardMaterial color={closed ? "#a5aaa6" : "#f4d9a2"} roughness={0.9} />
    </mesh>
    {[-0.85, 0.85].flatMap((x) => [-0.72, 0.72].map((z) => <mesh key={`${x}:${z}`} position={[x, 0.71, z]} castShadow>
      <boxGeometry args={[0.09, 1.24, 0.09]} /><meshStandardMaterial color="#856241" />
    </mesh>))}
    <mesh position={[0, 0.17, 0.767]}><boxGeometry args={[1.8, 0.12, 0.065]} /><meshStandardMaterial color="#96704a" /></mesh>
    <mesh position={[0, 1.36, -0.91]} geometry={roof} castShadow>
      <meshStandardMaterial key={shingles.uuid} color={roofColor} map={shingles} roughness={0.76} />
    </mesh>
    <mesh position={[0, 2.14, 0]} castShadow><boxGeometry args={[0.12, 0.09, 1.96]} /><meshStandardMaterial color={roofColor} /></mesh>
    {[-1.07, 1.07].map((x) => <mesh key={x} position={[x, 1.36, 0]} castShadow>
      <boxGeometry args={[0.1, 0.09, 1.93]} /><meshStandardMaterial color="#e9d3a4" />
    </mesh>)}
    <mesh position={[0.59, 1.95, -0.49]} castShadow>
      <boxGeometry args={[0.27, 0.66, 0.28]} /><meshStandardMaterial color="#d4b58e" roughness={0.9} />
    </mesh>
    <mesh position={[0.59, 2.29, -0.49]} castShadow>
      <boxGeometry args={[0.36, 0.09, 0.37]} /><meshStandardMaterial color="#80634b" />
    </mesh>
    <mesh position={[0, 0.53, 0.765]}><boxGeometry args={[0.49, 0.84, 0.07]} /><meshStandardMaterial color="#805a3a" /></mesh>
    <mesh position={[0, 0.53, 0.81]}><planeGeometry args={[0.36, 0.7]} /><meshStandardMaterial color="#31546b" /></mesh>
    <mesh position={[0.105, 0.43, 0.845]}><sphereGeometry args={[0.035, 8, 6]} /><meshStandardMaterial color="#efd17c" metalness={0.5} roughness={0.25} /></mesh>
    <ShopWindow x={-0.55} y={0.7} z={0.77} closed={closed} />
    <ShopWindow x={0.55} y={0.7} z={0.77} closed={closed} />
    <ShopWindow x={-0.92} y={0.72} z={-0.15} rotation={-Math.PI / 2} closed={closed} />
    <ShopWindow x={0.92} y={0.72} z={-0.15} rotation={Math.PI / 2} closed={closed} />
    <ShopWindow x={0} y={0.72} z={-0.77} rotation={Math.PI} closed={closed} />
    <mesh position={[0, 1.18, 0.91]} rotation={[-Math.PI / 2 + 0.2, 0, 0]} castShadow>
      <planeGeometry args={[1.97, 0.64]} /><meshStandardMaterial key={awning.uuid} map={awning} roughness={0.95} side={DoubleSide} />
    </mesh>
    <mesh position={[0, 1.03, 1.215]}>
      <planeGeometry args={[1.97, 0.2]} /><meshStandardMaterial key={awning.uuid} map={awning} roughness={0.95} />
    </mesh>
  </group>;
}
