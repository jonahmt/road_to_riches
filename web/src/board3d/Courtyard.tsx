import { useEffect, useLayoutEffect, useMemo, useRef } from "react";
import { CanvasTexture, InstancedMesh, Object3D, Shape, SRGBColorSpace } from "three";
import type { SquareInfo } from "../protocol";
import { boardExtent, type Point3 } from "./geometry";

type Block = { position: Point3; scale: Point3 };

// Decorative objects have no pointer handlers or gameplay state. Repeated masonry
// and foliage share geometry/materials in two instanced draw calls.
function Blocks({ blocks, color, rounded = false }: { blocks: Block[]; color: string; rounded?: boolean }) {
  const mesh = useRef<InstancedMesh>(null);
  useLayoutEffect(() => {
    const transform = new Object3D();
    blocks.forEach((block, index) => {
      transform.position.set(...block.position); transform.scale.set(...block.scale); transform.updateMatrix();
      mesh.current?.setMatrixAt(index, transform.matrix);
    });
    if (mesh.current) { mesh.current.instanceMatrix.needsUpdate = true; mesh.current.computeBoundingSphere(); }
  }, [blocks]);
  return <instancedMesh ref={mesh} args={[undefined, undefined, blocks.length]} receiveShadow>
    {rounded ? <icosahedronGeometry args={[0.5, 1]} /> : <boxGeometry args={[1, 1, 1]} />}
    <meshStandardMaterial color={color} roughness={0.95} />
  </instancedMesh>;
}

export function Courtyard({ squares: boardSquares }: { squares: SquareInfo[] }) {
  // Cash, ownership and presentation snapshots must not repaint the 2048px ground.
  const layoutKey = JSON.stringify(boardSquares.map(({ id, position, waypoints }) => [id, position, waypoints]));
  const squares = useMemo(() => boardSquares, [layoutKey]);
  const extent = useMemo(() => boardExtent(squares), [squares]);
  const width = extent.width + 44, depth = extent.depth + 44;
  const [cx, , cz] = extent.center;
  const left = cx - extent.width / 2 - 10, right = cx + extent.width / 2 + 10;
  const back = cz - extent.depth / 2 - 12, front = cz + extent.depth / 2 + 12;
  const texture = useMemo(() => {
    const canvas = document.createElement("canvas"); canvas.width = canvas.height = 2048;
    const ctx = canvas.getContext("2d")!;
    const sx = 2048 / width, sz = 2048 / depth;
    const px = (x: number) => (x - cx + width / 2) * sx;
    const pz = (z: number) => (z - cz + depth / 2) * sz;
    let seed = 917;
    const random = () => { seed = (seed * 1664525 + 1013904223) >>> 0; return seed / 4294967296; };
    ctx.fillStyle = "#70834c"; ctx.fillRect(0, 0, 2048, 2048);
    // Low-contrast grain gives broad lawns texture without geometry or animation.
    for (let i = 0; i < 42000; i++) {
      ctx.fillStyle = random() > 0.5 ? "#d3d7a313" : "#324b2813";
      ctx.fillRect(random() * 2048, random() * 2048, 2 + random() * 7, 2 + random() * 5);
    }
    const paving = new Path2D();
    for (const square of squares) {
      paving.roundRect(px(square.position[0] - 3.5), pz(square.position[1] - 3.5), 7 * sx, 7 * sz, 0.65 * Math.min(sx, sz));
      // Only join real board neighbors, never imply a new route across the lawn.
      const ids = new Set(square.waypoints.flatMap((waypoint) => waypoint.to_ids));
      for (const id of ids) {
        const next = squares.find((item) => item.id === id);
        if (!next || Math.hypot(next.position[0] - square.position[0], next.position[1] - square.position[1]) > 7) continue;
        const dx = next.position[0] - square.position[0], dz = next.position[1] - square.position[1];
        const length = Math.hypot(dx, dz); if (!length) continue;
        const nx = dz / length * 3.2, nz = -dx / length * 3.2;
        paving.moveTo(px(square.position[0] + nx), pz(square.position[1] + nz));
        paving.lineTo(px(next.position[0] + nx), pz(next.position[1] + nz));
        paving.lineTo(px(next.position[0] - nx), pz(next.position[1] - nz));
        paving.lineTo(px(square.position[0] - nx), pz(square.position[1] - nz)); paving.closePath();
      }
    }
    ctx.strokeStyle = "#53613d"; ctx.lineWidth = 0.22 * sx; ctx.stroke(paving);
    ctx.save(); ctx.clip(paving); ctx.fillStyle = "#b4ab8d"; ctx.fillRect(0, 0, 2048, 2048);
    for (let row = 0; row < depth / 1.6; row++) {
      for (let col = -1; col < width / 2.5; col++) {
        const x = (col * 2.5 + (row % 2) * 1.25) * sx, y = row * 1.6 * sz;
        const tone = Math.floor(random() * 12);
        ctx.fillStyle = `rgb(${184 + tone},${176 + tone},${150 + tone})`;
        ctx.fillRect(x + 0.6, y + 0.6, 2.5 * sx - 1.2, 1.6 * sz - 1.2);
        ctx.fillStyle = "#fff7d51a"; ctx.fillRect(x + 1, y + 1, 2.5 * sx - 2, 1);
      }
    }
    ctx.restore();
    const result = new CanvasTexture(canvas); result.colorSpace = SRGBColorSpace; result.anisotropy = 8;
    return result;
  }, [squares, width, depth, cx, cz]);
  useEffect(() => () => texture.dispose(), [texture]);
  const masonry = useMemo(() => {
    const blocks: Block[] = [];
    const box = (position: Point3, scale: Point3) => blocks.push({ position, scale });
    box([cx, 0.55, back], [right - left, 1.4, 1]);
    for (const x of [left, right]) {
      box([x, 0.55, (back + front) / 2], [1, 1.4, front - back]);
      for (let z = back; z <= front; z += 6) box([x, 0.9, z], [1.6, 2.1, 1.6]);
    }
    // A distant gatehouse stays outside the playable footprint at every board size.
    box([cx, 3.5, back - 5], [13, 7, 3]);
    box([cx, 7.2, back - 5], [14, 0.6, 3.6]);
    for (const x of [cx - 8.5, cx + 8.5, left, right]) {
      const z = x === left || x === right ? back : back - 5;
      box([x, 4.5, z], [4.2, 9, 4.2]);
      box([x, 8.9, z], [4.7, 0.6, 4.7]);
      for (const dx of [-1.65, 0, 1.65]) for (const dz of [-1.65, 1.65]) box([x + dx, 9.6, z + dz], [0.9, 1, 1]);
    }
    return blocks;
  }, [left, right, back, front, cx]);
  const shrubs = useMemo(() => {
    const blocks: Block[] = [];
    for (const x of [left + 3, right - 3]) for (let z = back + 6; z < front - 3; z += 7) {
      blocks.push({ position: [x, 0.65, z], scale: [2.8, 1.8, 3.8] });
    }
    return blocks;
  }, [left, right, back, front]);
  const gate = useMemo(() => {
    const shape = new Shape(); shape.moveTo(-1.8, 0); shape.lineTo(-1.8, 3.4);
    shape.quadraticCurveTo(-1.8, 5.2, 0, 5.6); shape.quadraticCurveTo(1.8, 5.2, 1.8, 3.4);
    shape.lineTo(1.8, 0); shape.closePath(); return shape;
  }, []);
  const windows = useMemo(() => [cx - 8.5, cx + 8.5].flatMap((x) => [3, 6.4].map((y) =>
    ({ position: [x, y, back - 2.88] as Point3, scale: [0.55, 1.5, 0.06] as Point3 }))), [cx, back]);
  return <group name="courtyard-scenery">
    <mesh rotation={[-Math.PI / 2, 0, 0]} position={[cx, -0.17, cz]} receiveShadow>
      <planeGeometry args={[600 + width, 600 + depth]} /><meshStandardMaterial color="#70834c" roughness={1} />
    </mesh>
    <mesh rotation={[-Math.PI / 2, 0, 0]} position={[cx, -0.14, cz]} receiveShadow>
      <planeGeometry args={[width, depth]} /><meshStandardMaterial map={texture} roughness={1} />
    </mesh>
    <Blocks blocks={masonry} color="#b8b8a5" />
    <Blocks blocks={shrubs} color="#496a39" rounded />
    <Blocks blocks={windows} color="#475657" />
    <mesh position={[cx, -0.12, back - 3.46]}>
      <shapeGeometry args={[gate]} /><meshStandardMaterial color="#57605b" roughness={1} />
    </mesh>
    {[cx - 8.5, cx + 8.5].map((x) => <mesh key={x} position={[x, 11.3, back - 5]} rotation={[0, Math.PI / 4, 0]}>
      <coneGeometry args={[3.05, 4.2, 4]} /><meshStandardMaterial color="#526c7a" roughness={0.95} />
    </mesh>)}
  </group>;
}
