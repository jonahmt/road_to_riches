import { useEffect, useMemo } from "react";
import { DoubleSide } from "three";
import { RoundedBoxGeometry } from "three/addons/geometries/RoundedBoxGeometry.js";
import { TILE_TOP, type Point3 } from "./geometry";

export type MechanicalObjectKind = "cannon" | "die" | "switch";

export function MechanicalObject({ kind, dimmed }: { kind: MechanicalObjectKind; dimmed: boolean }) {
  return <group position={[0, TILE_TOP, -0.4]}>
    {kind === "cannon" ? <Cannon dimmed={dimmed} />
      : kind === "die" ? <RollOnDie dimmed={dimmed} /> : <SwitchButton dimmed={dimmed} />}
  </group>;
}

function Cannon({ dimmed }: { dimmed: boolean }) {
  const color = (normal: string) => dimmed ? "#495562" : normal;
  return <group position={[0, 0, -0.35]} rotation={[0, -0.2, 0]}>
    <mesh position={[0, 0.39, 0]} castShadow receiveShadow>
      <boxGeometry args={[1.78, 0.25, 0.86]} /><meshStandardMaterial color={color("#aeb5b7")} metalness={0.22} roughness={0.5} />
    </mesh>
    {[-0.63, 0.63].flatMap((x) => [-0.55, 0.55].map((z) => <group key={`${x}:${z}`} position={[x, 0.35, z]}>
      <mesh rotation={[Math.PI / 2, 0, 0]} castShadow receiveShadow>
        <cylinderGeometry args={[0.34, 0.34, 0.22, 28]} /><meshStandardMaterial color={color("#f2c94c")} roughness={0.42} />
      </mesh>
      <mesh position={[0, 0, Math.sign(z) * 0.12]}>
        <torusGeometry args={[0.25, 0.025, 6, 28]} /><meshStandardMaterial color={color("#ffeb8a")} metalness={0.2} roughness={0.35} />
      </mesh>
      <mesh position={[0, 0, Math.sign(z) * 0.13]} rotation={[Math.PI / 2, 0, 0]}>
        <cylinderGeometry args={[0.105, 0.105, 0.065, 16]} /><meshStandardMaterial color={color("#344755")} metalness={0.45} roughness={0.35} />
      </mesh>
    </group>))}
    {[-0.34, 0.34].map((z) => <mesh key={z} position={[-0.13, 0.67, z]} castShadow>
      <boxGeometry args={[0.61, 0.46, 0.17]} /><meshStandardMaterial color={color("#7d8d96")} metalness={0.2} roughness={0.5} />
    </mesh>)}
    <group position={[0, 0.97, 0]} rotation={[0, 0, 0.24]}>
      <mesh rotation={[0, 0, -Math.PI / 2]} castShadow receiveShadow>
        <cylinderGeometry args={[0.37, 0.4, 1.68, 32, 1, true]} /><meshStandardMaterial color={color("#62ad68")} metalness={0.1} roughness={0.38} />
      </mesh>
      <mesh position={[-0.81, 0, 0]} scale={[0.37, 1, 1]} castShadow>
        <sphereGeometry args={[0.4, 24, 16]} /><meshStandardMaterial color={color("#62ad68")} metalness={0.1} roughness={0.38} />
      </mesh>
      <mesh position={[0.86, 0, 0]} rotation={[0, 0, -Math.PI / 2]} castShadow>
        <cylinderGeometry args={[0.445, 0.445, 0.25, 32, 1, true]} /><meshStandardMaterial color={color("#c9ced0")} metalness={0.42} roughness={0.32} />
      </mesh>
      <mesh position={[0.99, 0, 0]} rotation={[0, Math.PI / 2, 0]}>
        <ringGeometry args={[0.285, 0.445, 32]} /><meshStandardMaterial color={color("#e1e4df")} metalness={0.4} roughness={0.3} />
      </mesh>
      <mesh position={[0.83, 0, 0]} rotation={[0, 0, -Math.PI / 2]}>
        <cylinderGeometry args={[0.285, 0.285, 0.31, 32, 1, true]} /><meshStandardMaterial color={color("#344752")} roughness={0.9} side={DoubleSide} />
      </mesh>
      <mesh position={[0.67, 0, 0]} rotation={[0, Math.PI / 2, 0]}>
        <circleGeometry args={[0.285, 32]} /><meshStandardMaterial color={color("#102632")} roughness={1} />
      </mesh>
      <mesh position={[-0.24, 0, 0]} rotation={[0, Math.PI / 2, 0]} castShadow>
        <torusGeometry args={[0.395, 0.035, 8, 32]} /><meshStandardMaterial color={color("#95c187")} metalness={0.15} roughness={0.4} />
      </mesh>
    </group>
  </group>;
}

const DIE_PIPS: Array<Array<[number, number]>> = [
  [[0, 0]],
  [[-0.31, 0.31], [0.31, -0.31]],
  [[-0.31, 0.31], [0, 0], [0.31, -0.31]],
  [[-0.31, -0.31], [-0.31, 0.31], [0.31, -0.31], [0.31, 0.31]],
  [[-0.31, -0.31], [-0.31, 0.31], [0, 0], [0.31, -0.31], [0.31, 0.31]],
  [[-0.31, -0.36], [-0.31, 0], [-0.31, 0.36], [0.31, -0.36], [0.31, 0], [0.31, 0.36]],
];
const DIE_FACES: Array<{ number: number; position: Point3; rotation: Point3 }> = [
  { number: 1, position: [0, 0.826, 0], rotation: [-Math.PI / 2, 0, 0] },
  { number: 2, position: [0, 0, 0.826], rotation: [0, 0, 0] },
  { number: 3, position: [0.826, 0, 0], rotation: [0, Math.PI / 2, 0] },
  { number: 4, position: [-0.826, 0, 0], rotation: [0, -Math.PI / 2, 0] },
  { number: 5, position: [0, 0, -0.826], rotation: [0, Math.PI, 0] },
  { number: 6, position: [0, -0.826, 0], rotation: [Math.PI / 2, 0, 0] },
];

function RollOnDie({ dimmed }: { dimmed: boolean }) {
  const geometry = useMemo(() => new RoundedBoxGeometry(1.65, 1.65, 1.65, 3, 0.11), []);
  useEffect(() => () => geometry.dispose(), [geometry]);
  // Leave the front of the tile clear for a full-size player figure.
  return <group position={[-0.7, 0.83 * 0.82, -0.45]} scale={0.82} rotation={[0, -Math.PI / 4, 0]}>
    <mesh geometry={geometry} castShadow receiveShadow>
      <meshStandardMaterial color={dimmed ? "#68727b" : "#fff9e8"} roughness={0.32} />
    </mesh>
    {DIE_FACES.map((face) => <group key={face.number} position={face.position} rotation={face.rotation}>
      {DIE_PIPS[face.number - 1].map(([x, y]) => <mesh key={`${x}:${y}`} position={[x, y, 0]}>
        <circleGeometry args={[0.105, 20]} /><meshStandardMaterial color={dimmed ? "#3b4753" : "#173341"} roughness={0.55} />
      </mesh>)}
    </group>)}
  </group>;
}

function SwitchButton({ dimmed }: { dimmed: boolean }) {
  const color = (normal: string) => dimmed ? "#495562" : normal;
  return <group position={[-0.62, 0, -0.44]} scale={0.8}>
    <mesh position={[0, 0.1, 0]} castShadow receiveShadow>
      <cylinderGeometry args={[0.98, 1.02, 0.2, 48]} /><meshStandardMaterial color={color("#aeb5b7")} metalness={0.35} roughness={0.42} />
    </mesh>
    <mesh position={[0, 0.21, 0]} rotation={[-Math.PI / 2, 0, 0]} castShadow>
      <torusGeometry args={[0.935, 0.045, 8, 48]} /><meshStandardMaterial color={color("#d7dcda")} metalness={0.45} roughness={0.3} />
    </mesh>
    <mesh position={[0, 0.21, 0]} receiveShadow>
      <cylinderGeometry args={[0.88, 0.88, 0.1, 48]} /><meshStandardMaterial color={color("#152c38")} roughness={0.72} />
    </mesh>
    <mesh position={[0, 0.27, 0]} castShadow receiveShadow>
      <cylinderGeometry args={[0.805, 0.835, 0.13, 48]} /><meshStandardMaterial color={color("#ffd84d")} roughness={0.36} />
    </mesh>
    <mesh position={[0, 0.325, 0]} rotation={[-Math.PI / 2, 0, 0]}>
      <torusGeometry args={[0.79, 0.018, 6, 48]} /><meshStandardMaterial color={color("#ffeb9a")} roughness={0.3} />
    </mesh>
  </group>;
}
