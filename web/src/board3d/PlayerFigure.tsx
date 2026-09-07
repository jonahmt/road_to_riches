import { useEffect, useMemo, useRef } from "react";
import { useFrame } from "@react-three/fiber";
import { Color, Group, QuadraticBezierCurve3, TubeGeometry, Vector3 } from "three";
import { useTileTexture } from "./textures";

export function PlayerFigure({ playerId, color, reduced }: { playerId: number; color: string; reduced: boolean }) {
  const eyes = useRef<Group>(null);
  const shade = useMemo(() => new Color(color).multiplyScalar(0.48), [color]);
  const highlight = useMemo(() => new Color(color).lerp(new Color("#ffffff"), 0.2), [color]);
  const smile = useMemo(() => new TubeGeometry(new QuadraticBezierCurve3(
    new Vector3(-0.14, 1.38, 0.54), new Vector3(0, 1.26, 0.62), new Vector3(0.14, 1.38, 0.54),
  ), 12, 0.024, 6, false), []);
  useEffect(() => () => smile.dispose(), [smile]);
  const badge = useTileTexture(`<svg xmlns="http://www.w3.org/2000/svg" width="128" height="128" viewBox="0 0 128 128"><circle cx="64" cy="64" r="57" fill="#fff2c4" stroke="#997142" stroke-width="7"/><text x="64" y="91" font-family="Arial,sans-serif" font-weight="900" font-size="81" text-anchor="middle" fill="#284660">${playerId}</text></svg>`);
  useFrame(({ clock }) => {
    if (!eyes.current) return;
    const cycle = (clock.elapsedTime + playerId * 0.83) % 4.7;
    eyes.current.scale.y = !reduced && cycle > 4.53 ? 0.09 : 1;
  });
  return <group>
    {[-0.24, 0.24].map((x) => <mesh key={x} position={[x, 0.28, 0.2]} scale={[0.28, 0.15, 0.39]} castShadow>
      <sphereGeometry args={[1, 16, 10]} /><meshStandardMaterial color={shade} roughness={0.55} />
    </mesh>)}
    <mesh position={[0, 0.81, 0]} scale={[0.58, 0.62, 0.45]} castShadow receiveShadow>
      <sphereGeometry args={[1, 24, 16]} /><meshStandardMaterial color={color} roughness={0.62} />
    </mesh>
    {[-1, 1].map((side) => <group key={side} position={[side * 0.52, 0.85, 0.035]} rotation={[0, 0, side * 0.22]}>
      <mesh castShadow><capsuleGeometry args={[0.13, 0.25, 4, 10]} /><meshStandardMaterial color={shade} roughness={0.6} /></mesh>
      <mesh position={[0, -0.21, 0.025]} castShadow><sphereGeometry args={[0.16, 14, 10]} /><meshStandardMaterial color="#ffedc8" roughness={0.65} /></mesh>
    </group>)}
    <mesh position={[0, 1.25, 0]} castShadow><cylinderGeometry args={[0.35, 0.43, 0.16, 24]} /><meshStandardMaterial color="#fff0c5" roughness={0.7} /></mesh>
    <mesh position={[0, 0.85, 0.45]}>
      <planeGeometry args={[0.37, 0.37]} /><meshBasicMaterial key={badge?.uuid ?? "loading"} map={badge} transparent />
    </mesh>
    <mesh position={[0, 1.64, 0]} scale={[1, 0.96, 1]} castShadow>
      <sphereGeometry args={[0.56, 28, 20]} /><meshStandardMaterial color={color} roughness={0.43} />
    </mesh>
    <group ref={eyes} position={[0, 1.7, 0]}>
      {[-0.19, 0.19].map((x) => <group key={x} position={[x, 0, 0.505]}>
        <mesh scale={[0.126, 0.171, 0.064]}><sphereGeometry args={[1, 14, 10]} /><meshStandardMaterial color="#fffdf0" roughness={0.4} /></mesh>
        <mesh position={[0, -0.006, 0.057]} scale={[0.054, 0.089, 0.027]}><sphereGeometry args={[1, 12, 8]} /><meshBasicMaterial color="#18334a" /></mesh>
        <mesh position={[-0.014, 0.025, 0.078]}><sphereGeometry args={[0.019, 8, 6]} /><meshBasicMaterial color="#ffffff" /></mesh>
      </group>)}
    </group>
    <mesh position={[0, 1.53, 0.565]} scale={[1, 0.8, 0.8]}><sphereGeometry args={[0.09, 14, 10]} /><meshStandardMaterial color={highlight} roughness={0.5} /></mesh>
    <mesh geometry={smile}><meshBasicMaterial color="#244354" /></mesh>
    <group position={[0, 2.075, -0.025]} rotation={[0.04, 0, -0.05]}>
      <mesh castShadow><cylinderGeometry args={[0.52, 0.57, 0.1, 24]} /><meshStandardMaterial color={shade} roughness={0.8} /></mesh>
      <mesh position={[0, 0.12, -0.015]} scale={[0.53, 0.23, 0.52]} castShadow>
        <sphereGeometry args={[1, 24, 12]} /><meshStandardMaterial color={shade} roughness={0.8} />
      </mesh>
      <mesh position={[0, -0.005, 0.38]} scale={[0.51, 0.055, 0.28]} castShadow>
        <sphereGeometry args={[1, 20, 10]} /><meshStandardMaterial color={shade} roughness={0.7} />
      </mesh>
      <mesh position={[0, 0.34, -0.015]}><sphereGeometry args={[0.064, 10, 8]} /><meshStandardMaterial color="#e7c16f" roughness={0.45} metalness={0.25} /></mesh>
    </group>
  </group>;
}
