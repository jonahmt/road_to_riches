import { useEffect, useMemo } from "react";
import { ExtrudeGeometry, Shape } from "three";
import { TILE_TOP, type Point3 } from "./geometry";
import { useRoofTexture, useTileTexture } from "./textures";

function CivicWindow({ position, rotation = 0, trim }: { position: Point3; rotation?: number; trim: string }) {
  return <group position={position} rotation={[0, rotation, 0]}>
    <mesh><boxGeometry args={[0.51, 0.72, 0.07]} /><meshStandardMaterial color={trim} /></mesh>
    <mesh position={[0, 0, 0.045]}><planeGeometry args={[0.37, 0.57]} /><meshStandardMaterial color="#3c6e87" roughness={0.32} /></mesh>
    <mesh position={[0, 0, 0.06]}><boxGeometry args={[0.04, 0.59, 0.03]} /><meshStandardMaterial color="#fff2d1" /></mesh>
    <mesh position={[0, 0.04, 0.06]}><boxGeometry args={[0.4, 0.035, 0.03]} /><meshStandardMaterial color="#fff2d1" /></mesh>
    <mesh position={[0, -0.39, 0.06]} castShadow><boxGeometry args={[0.59, 0.09, 0.2]} /><meshStandardMaterial color="#f4e2b8" /></mesh>
  </group>;
}

export function CivicBuilding({ color, stockbroker }: { color: string; stockbroker: boolean }) {
  const shingles = useRoofTexture();
  const [roof, door] = useMemo(() => {
    const triangle = new Shape();
    triangle.moveTo(-1.42, 0); triangle.lineTo(1.42, 0); triangle.lineTo(0, 0.7); triangle.closePath();
    const arch = new Shape();
    arch.moveTo(-0.3, 0); arch.lineTo(0.3, 0); arch.lineTo(0.3, 0.72);
    arch.bezierCurveTo(0.3, 1.12, -0.3, 1.12, -0.3, 0.72); arch.closePath();
    return [new ExtrudeGeometry(triangle, { depth: 1.94, bevelEnabled: true,
      bevelSegments: 1, bevelSize: 0.025, bevelThickness: 0.025 }),
    new ExtrudeGeometry(arch, { depth: 0.065, bevelEnabled: true,
      bevelSegments: 2, bevelSize: 0.025, bevelThickness: 0.025 })];
  }, []);
  useEffect(() => () => { roof.dispose(); door.dispose(); }, [roof, door]);
  const emblem = useTileTexture(stockbroker
    ? '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 128 128" width="128" height="128"><path d="M20 29V103H110" fill="none" stroke="#f5db97" stroke-width="7"/><path d="M32 86L54 62L72 74L102 36M79 36H102V60" fill="none" stroke="#fff5d1" stroke-width="10" stroke-linecap="round" stroke-linejoin="round"/></svg>'
    : '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 128 128" width="128" height="128"><circle cx="64" cy="64" r="57" fill="#fff4d6" stroke="#b5893b" stroke-width="9"/><path d="M64 17V26M64 102V111M17 64H26M102 64H111" stroke="#3a4c59" stroke-width="5"/><path d="M64 64L38 42M64 64L86 38" fill="none" stroke="#29465b" stroke-width="7" stroke-linecap="round"/><circle cx="64" cy="64" r="6" fill="#ba8839"/></svg>');
  const roofColor = stockbroker ? "#28644f" : "#49677e";
  const columns = stockbroker ? [-1, -0.6, -0.2, 0.2, 0.6, 1] : [-0.99, -0.54, 0.54, 0.99];
  return <group position={[0, TILE_TOP, -0.52]} scale={0.9}>
    {[{ y: 0.06, width: 2.95, depth: 2.32 }, { y: 0.18, width: 2.73, depth: 2.1 }].map(({ y, width, depth }) =>
      <mesh key={y} position={[0, y, 0.03]} receiveShadow><boxGeometry args={[width, 0.12, depth]} /><meshStandardMaterial color="#ecdfc3" roughness={0.9} /></mesh>)}
    <mesh position={[0, 0.3, -0.1]} receiveShadow><boxGeometry args={[2.52, 0.12, 1.73]} /><meshStandardMaterial color={color} roughness={0.7} /></mesh>
    <mesh position={[0, 0.96, -0.31]} castShadow receiveShadow><boxGeometry args={[2.24, 1.28, 1.08]} /><meshStandardMaterial color="#ecdfc3" roughness={0.86} /></mesh>
    {[-0.99, 0.99].flatMap((x) => [-0.8, 0.19].map((z) => <mesh key={`${x}:${z}`} position={[x, 0.99, z]} castShadow>
      <boxGeometry args={[0.16, 1.22, 0.12]} /><meshStandardMaterial color="#f9edcf" />
    </mesh>))}
    <mesh geometry={door} position={[0, 0.34, 0.245]}><meshStandardMaterial color="#31566d" roughness={0.42} /></mesh>
    <mesh position={[0, 0.75, 0.345]}><boxGeometry args={[0.035, 0.82, 0.035]} /><meshStandardMaterial color={color} /></mesh>
    {[-0.07, 0.07].map((x) => <mesh key={x} position={[x, 0.72, 0.37]}><sphereGeometry args={[0.025, 8, 6]} /><meshStandardMaterial color="#edcf77" metalness={0.45} roughness={0.35} /></mesh>)}
    <CivicWindow position={[-1.14, 0.95, -0.31]} rotation={-Math.PI / 2} trim={color} />
    <CivicWindow position={[1.14, 0.95, -0.31]} rotation={Math.PI / 2} trim={color} />
    <CivicWindow position={[-0.56, 0.95, -0.865]} rotation={Math.PI} trim={color} />
    <CivicWindow position={[0.56, 0.95, -0.865]} rotation={Math.PI} trim={color} />
    {columns.map((x) => <group key={x} position={[x, 1, 0.59]}>
      <mesh castShadow><cylinderGeometry args={[0.105, 0.14, 1.19, 16]} /><meshStandardMaterial color="#fff1ce" roughness={0.63} /></mesh>
      {[-0.59, 0.59].map((y) => <group key={y} position={[0, y, 0]}>
        <mesh castShadow><boxGeometry args={[0.32, 0.1, 0.32]} /><meshStandardMaterial color={color} roughness={0.5} /></mesh>
        <mesh position={[0, -Math.sign(y) * 0.085, 0]}><cylinderGeometry args={[0.17, 0.17, 0.07, 16]} /><meshStandardMaterial color="#fff0c9" /></mesh>
      </group>)}
    </group>)}
    <mesh position={[0, 1.69, 0]} castShadow><boxGeometry args={[2.78, 0.18, 1.9]} /><meshStandardMaterial color={color} roughness={0.55} /></mesh>
    <mesh position={[0, 1.81, 0]} castShadow><boxGeometry args={[2.93, 0.07, 2.03]} /><meshStandardMaterial color="#fff0cb" /></mesh>
    <mesh position={[0, 1.86, -0.97]} geometry={roof} castShadow>
      <meshStandardMaterial attach="material-0" color={stockbroker ? color : "#e7d7ad"} roughness={0.75} />
      <meshStandardMaterial attach="material-1" color={roofColor} map={shingles} roughness={0.75} />
    </mesh>
    <mesh position={[0, 2.57, 0]} castShadow><boxGeometry args={[0.12, 0.09, 2.06]} /><meshStandardMaterial color={color} /></mesh>
    <mesh position={[0, 2.095, 1.005]}>
      <planeGeometry args={[0.39, 0.39]} /><meshStandardMaterial key={emblem?.uuid ?? "loading"} map={emblem} transparent roughness={0.7} />
    </mesh>
  </group>;
}
