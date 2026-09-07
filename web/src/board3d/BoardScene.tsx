import { Component, type ErrorInfo, type ReactNode, useEffect, useMemo, useRef, useState } from "react";
import { Canvas, type ThreeEvent, useFrame, useThree } from "@react-three/fiber";
import {
  type BufferGeometry, type Camera, Color, Curve, ExtrudeGeometry, Group, MeshStandardMaterial, NeutralToneMapping, Object3D,
  TubeGeometry, Vector3,
} from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { SVGLoader } from "three/addons/loaders/SVGLoader.js";
import { RoundedBoxGeometry } from "three/addons/geometries/RoundedBoxGeometry.js";
import { PLAYER_COLORS } from "../boardColors";
import { adjacentStepAnimationDuration } from "../cameraTiming";
import type { GameState, InputRequest, SquareInfo } from "../protocol";
import { boardExtent, boardPoint, canPickSquare, focusPoint, piecePositions, TILE_SIZE, TILE_SURFACE_SIZE, TILE_TOP, type Point3, type BoardProjector } from "./geometry";
import { ShopModel, ShopSign } from "./ShopModels";
import { useTileTexture } from "./textures";
import { makeTileRim } from "./tileGeometry";
import { PlayerFigure } from "./PlayerFigure";
import { CivicBuilding } from "./CivicBuilding";
import { MovementGuideButtons, MovementGuideMeshes, type MovementButtons } from "./MovementGuides";
import { movementGuides } from "./movementPresentation";
import "./board3d.css";

const FOLLOW_CAMERA_OFFSET: Point3 = [0, 24, 24];

export interface TileArtwork {
  surface: string;
  symbol: string | null;
  sign: string | null;
  border: string;
  description: string;
}

export interface BoardSelection {
  eligibleSquareIds: ReadonlySet<number>;
  selectedSquareId: number | null;
  chosenSquareIds?: ReadonlySet<number>;
  onConfirmSquare: (squareId: number) => void;
}

interface SceneProps {
  state: GameState;
  artwork: Map<number, TileArtwork>;
  selectedSquareId: number | null;
  assignedPlayerId: number | null;
  focusDistrictId: number | null;
  temporaryFreeCamera: boolean;
  selection: BoardSelection | null;
  onSelectSquare: (id: number) => void;
  onFallback: () => void;
  projectorRef: { current: BoardProjector | null };
  movementRequest: InputRequest | null;
  onMovementChoice: (value: number | "undo") => void;
}

class RendererBoundary extends Component<{ children: ReactNode; onFallback: () => void }, { failed: boolean }> {
  state = { failed: false };
  static getDerivedStateFromError() { return { failed: true }; }
  componentDidCatch(error: Error, info: ErrorInfo) { console.error("3D board renderer", error, info); }
  render() {
    return this.state.failed
      ? <div className="board3d-error" role="alert">The 3D view could not start.
          <button onClick={this.props.onFallback}>Use 2D view</button></div>
      : this.props.children;
  }
}

function useReducedMotion() {
  const [reduced, setReduced] = useState(() => window.matchMedia("(prefers-reduced-motion: reduce)").matches);
  useEffect(() => {
    const query = window.matchMedia("(prefers-reduced-motion: reduce)");
    const update = () => setReduced(query.matches);
    query.addEventListener("change", update);
    return () => query.removeEventListener("change", update);
  }, []);
  return reduced;
}

export default function BoardScene(props: SceneProps) {
  const [free, setFree] = useState(false);
  const [command, setCommand] = useState({ id: 0, action: "reset" });
  const [contextLost, setContextLost] = useState(false);
  const reduced = useReducedMotion();
  const root = useRef<HTMLDivElement>(null);
  const anchors = useRef(new Map<string, HTMLSpanElement>());
  const movementButtons = useRef<MovementButtons>(new Map());
  const guides = useMemo(() => movementGuides(props.movementRequest, props.assignedPlayerId),
    [props.movementRequest, props.assignedPlayerId]);
  const controls = useRef<OrbitControls | null>(null);
  const pieces = useMemo(() => piecePositions(props.state), [props.state]);
  const extent = useMemo(() => boardExtent(props.state.board.squares), [props.state.board.squares]);
  const lightTarget = useMemo(() => {
    const target = new Object3D();
    target.position.set(...extent.center);
    return target;
  }, [extent.center[0], extent.center[2]]);
  const isFree = free || props.temporaryFreeCamera;
  const shadowRadius = Math.hypot(extent.width, extent.depth) / 2 + 3;
  const select = (id: number, confirm = false) => {
    if (!canPickSquare(id, props.selection?.eligibleSquareIds ?? null)) return;
    props.onSelectSquare(id);
    if (confirm) props.selection?.onConfirmSquare(id);
  };
  const sendCommand = (action: string) => setCommand((previous) => ({ id: previous.id + 1, action }));
  useEffect(() => {
    const canvas = root.current?.querySelector("canvas");
    if (!canvas) return;
    const lost = (event: Event) => {
      event.preventDefault();
      requestAnimationFrame(() => {
        if (canvas.isConnected && canvas === root.current?.querySelector("canvas")) setContextLost(true);
      });
    };
    const restored = () => setContextLost(false);
    canvas.addEventListener("webglcontextlost", lost);
    canvas.addEventListener("webglcontextrestored", restored);
    return () => { canvas.removeEventListener("webglcontextlost", lost); canvas.removeEventListener("webglcontextrestored", restored); };
  }, []);
  return <div className="board3d-root" ref={root} data-camera-mode={isFree ? "free" : "follow"}>
    <RendererBoundary onFallback={props.onFallback}>
      <Canvas shadows="percentage" dpr={[1, 1.75]} camera={{ fov: 38, near: 0.1, far: 1500, position: FOLLOW_CAMERA_OFFSET }}
        gl={{ antialias: true, powerPreference: "high-performance", toneMapping: NeutralToneMapping, toneMappingExposure: 0.92 }}
        fallback={<div className="board3d-error" aria-hidden="true">Your browser could not start WebGL.
          <button onClick={props.onFallback}>Use 2D view</button></div>}>
        <color attach="background" args={["#315768"]} />
        <hemisphereLight args={["#fff9e5", "#536d81", 1.1]} />
        <primitive object={lightTarget} />
        <directionalLight position={[extent.center[0] - 20, 45, extent.center[2] + 20]} intensity={1.8}
          target={lightTarget}
          castShadow shadow-mapSize={[2048, 2048]} shadow-bias={-0.00015} shadow-normalBias={0.015}
          shadow-camera-left={-shadowRadius} shadow-camera-right={shadowRadius}
          shadow-camera-top={shadowRadius} shadow-camera-bottom={-shadowRadius}
          shadow-camera-far={180} />
        <mesh position={[extent.center[0], -0.14, extent.center[2]]} rotation={[-Math.PI / 2, 0, 0]} receiveShadow>
          <planeGeometry args={[2000 + extent.width, 2000 + extent.depth]} />
          <meshStandardMaterial color="#315768" roughness={0.96} />
        </mesh>
        <CameraRig state={props.state} free={isFree} focusDistrictId={props.focusDistrictId}
          command={command} controlsRef={controls} reduced={reduced} projectorRef={props.projectorRef} />
        {props.state.board.squares.map((square) => <BoardTile key={square.id} square={square}
          artwork={props.artwork.get(square.id)!} selected={props.selectedSquareId === square.id}
          chosen={props.selection?.chosenSquareIds?.has(square.id) ?? false}
          eligible={canPickSquare(square.id, props.selection?.eligibleSquareIds ?? null)}
          focused={props.focusDistrictId !== null && square.property_district === props.focusDistrictId}
          reduced={reduced} onSelect={select} />)}
        {pieces.map((piece) => <PlayerPiece key={piece.player.player_id} {...piece}
          assignedPlayerId={props.assignedPlayerId} reduced={reduced} anchors={anchors.current} />)}
        <SquareAnchors squares={props.state.board.squares} anchors={anchors.current} />
        {props.movementRequest && guides.length > 0 && <MovementGuideMeshes request={props.movementRequest}
          guides={guides} buttons={movementButtons.current} projectorRef={props.projectorRef} reduced={reduced} />}
      </Canvas>
      <MovementGuideButtons guides={contextLost ? [] : guides} buttons={movementButtons.current} onChoose={props.onMovementChoice} />
    </RendererBoundary>
    <div className="board3d-anchors" aria-hidden="true">
      {props.state.board.squares.map((square) => <span key={square.id} className="board-square-tile"
        data-square-id={square.id} ref={(node) => {
          if (node) anchors.current.set(`square:${square.id}`, node);
          else anchors.current.delete(`square:${square.id}`);
        }} />)}
      {pieces.map(({ player }) => <span key={player.player_id} className="player-token-svg"
        data-player-id={player.player_id} ref={(node) => {
          if (node) anchors.current.set(`player:${player.player_id}`, node);
          else anchors.current.delete(`player:${player.player_id}`);
        }} />)}
    </div>
    {contextLost && <div className="board3d-error" role="alert">The browser lost its 3D graphics context.
      <button onClick={props.onFallback}>Use 2D view</button></div>}
    <div className="board3d-controls" aria-label="3D board camera">
      <div className="board3d-camera-row">
        <button aria-label="Zoom out" onClick={() => sendCommand("out")}>−</button>
        <button onClick={() => sendCommand("reset")}>Reset</button>
        <button aria-label="Zoom in" onClick={() => sendCommand("in")}>+</button>
        <button disabled={props.temporaryFreeCamera} onClick={() => setFree(!free)}>
          {props.temporaryFreeCamera ? "Choosing" : free ? "Follow" : "Free Cam"}
        </button>
      </div>
      {isFree && <p>Drag to orbit · Right-drag to pan · Scroll to zoom</p>}
      <details><summary>Choose a square</summary>
        <label>Board square
          <select aria-label="Inspect board square" value={props.selectedSquareId ?? ""}
            onChange={(event) => select(Number(event.target.value))}>
            <option value="" disabled>Select a square</option>
            {props.state.board.squares.map((square) => <option key={square.id} value={square.id}
              disabled={!canPickSquare(square.id, props.selection?.eligibleSquareIds ?? null)}>
              {props.artwork.get(square.id)?.description}
            </option>)}
          </select>
        </label>
        {props.selection && <button disabled={props.selectedSquareId === null ||
          !props.selection.eligibleSquareIds.has(props.selectedSquareId)}
          onClick={() => props.selectedSquareId !== null && select(props.selectedSquareId, true)}>Confirm square</button>}
      </details>
    </div>
  </div>;
}

function CameraRig({ state, free, focusDistrictId, command, controlsRef, reduced, projectorRef }: {
  state: GameState; free: boolean; focusDistrictId: number | null;
  command: { id: number; action: string }; controlsRef: { current: OrbitControls | null }; reduced: boolean;
  projectorRef: { current: BoardProjector | null };
}) {
  const { camera, gl } = useThree();
  const target = focusPoint(state, focusDistrictId);
  const targetRef = useRef(new Vector3(...target));
  const previousFree = useRef(free);
  const savedDistance = useRef(34);
  const initialized = useRef(false);
  const extent = boardExtent(state.board.squares);
  useEffect(() => {
    const orbit = new OrbitControls(camera, gl.domElement);
    orbit.enableDamping = !reduced;
    orbit.dampingFactor = 0.14;
    orbit.minDistance = 10;
    orbit.maxDistance = Math.max(100, extent.width * 2, extent.depth * 2);
    orbit.minPolarAngle = 0.12;
    orbit.maxPolarAngle = Math.PI / 2.8;
    orbit.screenSpacePanning = false;
    orbit.target.copy(targetRef.current);
    camera.position.copy(targetRef.current).add(new Vector3(...FOLLOW_CAMERA_OFFSET));
    orbit.update();
    controlsRef.current = orbit;
    projectorRef.current = (point) => {
      const projected = new Vector3(...boardPoint(point)).project(camera);
      return [projected.x * gl.domElement.clientWidth, -projected.y * gl.domElement.clientHeight];
    };
    initialized.current = true;
    return () => { orbit.dispose(); controlsRef.current = null; projectorRef.current = null; };
  }, [camera, gl, reduced]);
  useEffect(() => {
    targetRef.current.set(...target);
  }, [target[0], target[1], target[2]]);
  useEffect(() => {
    const orbit = controlsRef.current;
    if (!orbit) return;
    orbit.enableRotate = free;
    orbit.enablePan = free;
    if (free && !previousFree.current) savedDistance.current = orbit.getDistance();
    if (!free && previousFree.current) {
      // Return to the board's original orientation so WASD remains intuitive.
      camera.position.copy(orbit.target).add(new Vector3(...FOLLOW_CAMERA_OFFSET).normalize().multiplyScalar(savedDistance.current));
      orbit.update();
    }
    previousFree.current = free;
  }, [free, camera, controlsRef, reduced]);
  useEffect(() => {
    const orbit = controlsRef.current;
    if (!orbit || command.id === 0) return;
    if (command.action === "reset") {
      const center = free ? new Vector3(...extent.center) : targetRef.current;
      orbit.target.copy(center);
      const distance = free ? Math.max(extent.width, extent.depth) * 1.65 : 34;
      camera.position.copy(center).add(new Vector3(...FOLLOW_CAMERA_OFFSET).normalize().multiplyScalar(distance));
    } else {
      const distance = camera.position.clone().sub(orbit.target);
      distance.multiplyScalar(command.action === "in" ? 0.8 : 1.25);
      distance.clampLength(orbit.minDistance, orbit.maxDistance);
      camera.position.copy(orbit.target).add(distance);
    }
    orbit.update();
  }, [command]);
  useFrame((_, delta) => {
    const orbit = controlsRef.current;
    if (!orbit || !initialized.current) return;
    if (!free) {
      const next = orbit.target.clone().lerp(targetRef.current, reduced ? 1 : 1 - Math.exp(-delta * 14));
      camera.position.add(next.clone().sub(orbit.target));
      orbit.target.copy(next);
    }
    orbit.update(delta);
  });
  return null;
}

function BoardTile({ square, artwork, selected, chosen, eligible, focused, reduced, onSelect }: {
  square: SquareInfo; artwork: TileArtwork; selected: boolean; chosen: boolean;
  eligible: boolean; focused: boolean; reduced: boolean; onSelect: (id: number, confirm: boolean) => void;
}) {
  const texture = useTileTexture(artwork.surface);
  const base = useMemo(() => new RoundedBoxGeometry(4, 0.42, 4, 2, 0.1), []);
  const rim = useMemo(makeTileRim, []);
  useEffect(() => () => { base.dispose(); rim.dispose(); }, [base, rim]);
  const [hovered, setHovered] = useState(false);
  const glow = useRef<MeshStandardMaterial>(null);
  const down = useRef<{ x: number; y: number } | null>(null);
  const click = (event: ThreeEvent<MouseEvent>, confirm: boolean) => {
    event.stopPropagation();
    if (!eligible || event.delta > 4 || !down.current ||
      Math.hypot(event.clientX - down.current.x, event.clientY - down.current.y) > 4) return;
    onSelect(square.id, confirm);
  };
  useFrame(({ clock }) => {
    if (glow.current) glow.current.emissiveIntensity = focused
      ? (reduced ? 0.35 : 0.3 + Math.sin(clock.elapsedTime * 5) * 0.2) : 0;
  });
  const shop = square.type === "SHOP";
  const bank = ["BANK", "STOCKBROKER"].includes(square.type);
  return <group position={boardPoint(square.position, 0)}
    onPointerDown={(event) => { event.stopPropagation(); down.current = { x: event.clientX, y: event.clientY }; }}
    onClick={(event) => click(event, false)} onDoubleClick={(event) => click(event, true)}
    onPointerOver={(event) => { event.stopPropagation(); setHovered(true); }} onPointerOut={() => setHovered(false)}>
    <mesh position={[0, 0.17, 0]} geometry={base} castShadow receiveShadow>
      <meshStandardMaterial color={eligible ? artwork.border : "#28303a"} roughness={0.42} />
    </mesh>
    <mesh position={[0, 0.37, 0]} rotation={[-Math.PI / 2, 0, 0]} geometry={rim} castShadow receiveShadow>
      <meshStandardMaterial ref={glow} color={eligible ? artwork.border : "#28303a"}
        emissive={artwork.border} roughness={0.32} metalness={0.12} />
    </mesh>
    <mesh position={[0, TILE_TOP, 0]} rotation={[-Math.PI / 2, 0, 0]} receiveShadow>
      <planeGeometry args={[TILE_SURFACE_SIZE, TILE_SURFACE_SIZE]} />
      <meshStandardMaterial key={texture?.uuid ?? "loading"} map={texture} color={eligible ? (hovered ? "#ffffff" : "#eeeeee") : "#49515a"}
        roughness={0.85} />
    </mesh>
    {eligible && (selected || chosen) && <group position={[0, 0.46, 0]}>
      {[[-1.84, 0, 0], [1.84, 0, 0], [0, 0, -1.84], [0, 0, 1.84]].map((position, index) =>
        <mesh key={index} position={position as Point3}>
          <boxGeometry args={index < 2 ? [0.09, 0.08, 3.7] : [3.7, 0.08, 0.09]} />
          <meshBasicMaterial color={chosen ? "#ffd166" : "#ffffff"} />
        </mesh>)}
    </group>}
    {shop && artwork.sign && <ShopSign markup={artwork.sign} dimmed={!eligible} />}
    {shop && square.property_owner !== null && <ShopModel color={eligible
      ? PLAYER_COLORS[square.property_owner % PLAYER_COLORS.length] : "#46505a"}
      closed={square.statuses.some((status) => status.type === "closed")} />}
    {bank && <CivicBuilding color={eligible ? (square.type === "BANK" ? "#d2a543" : "#359e78") : "#46505a"}
      stockbroker={square.type === "STOCKBROKER"} />}
    {!shop && !bank && artwork.symbol && <SymbolRelief markup={artwork.symbol} dimmed={!eligible} />}
  </group>;
}

function SymbolRelief({ markup, dimmed }: { markup: string; dimmed: boolean }) {
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
        geometry: new ExtrudeGeometry(shape, { depth: 0.16, bevelEnabled: true,
          bevelSegments: 1, steps: 1, bevelSize: 0.018, bevelThickness: 0.018, curveSegments: 10 }),
        color: path.color.clone(),
      }));
    });
  }, [markup]);
  useEffect(() => () => parts.forEach((part) => part.geometry.dispose()), [parts]);
  const scale = TILE_SURFACE_SIZE / TILE_SIZE;
  return <group position={[0, TILE_TOP + 0.015, 0]} rotation={[-Math.PI / 2, 0, 0]} scale={[scale, -scale, 1]}>
    {parts.map((part, index) => <mesh key={index} geometry={part.geometry} position={[0, 0, index * 0.003]} castShadow receiveShadow>
      <meshStandardMaterial color={dimmed ? "#43505b" : part.color} roughness={0.46} metalness={0.08} />
    </mesh>)}
  </group>;
}

function PlayerPiece({ player, active, position, scale, assignedPlayerId, reduced, anchors }: ReturnType<typeof piecePositions>[number] & {
  assignedPlayerId: number | null; reduced: boolean; anchors: Map<string, HTMLSpanElement>;
}) {
  const group = useRef<Group>(null);
  const figure = useRef<Group>(null);
  const initialPosition = useRef(position);
  const initialScale = useRef(scale);
  const { camera, size } = useThree();
  const destination = useRef(new Vector3(...position));
  const transition = useRef({ from: new Vector3(...position), start: 0, duration: 0 });
  const color = PLAYER_COLORS[player.player_id % PLAYER_COLORS.length];
  useEffect(() => {
    if (group.current) transition.current = { from: group.current.position.clone(), start: performance.now(),
      duration: reduced ? 0 : adjacentStepAnimationDuration(player.player_id, assignedPlayerId) };
    destination.current.set(...position);
  }, [position[0], position[1], position[2], reduced, assignedPlayerId, player.player_id]);
  useFrame((_, delta) => {
    if (!group.current) return;
    const motion = transition.current;
    const progress = motion.duration ? Math.min(1, (performance.now() - motion.start) / motion.duration) : 1;
    group.current.position.lerpVectors(motion.from, destination.current, progress);
    group.current.scale.setScalar(reduced ? scale : group.current.scale.x +
      (scale - group.current.scale.x) * (1 - Math.exp(-20 * delta)));
    if (figure.current) figure.current.position.y = reduced ? 0 : Math.sin(progress * Math.PI) * 0.18;
    projectAnchor(anchors.get(`player:${player.player_id}`), group.current.position.clone().add(
      new Vector3(0, (1.2 + (figure.current?.position.y ?? 0)) * group.current.scale.y, 0)), camera, size);
  });
  return <group ref={group} position={initialPosition.current} scale={initialScale.current}>
    <mesh position={[0, 0.12, 0]} castShadow receiveShadow>
      <cylinderGeometry args={[0.72, 0.8, 0.22, 24]} /><meshStandardMaterial color={active ? "#fff4ce" : color} metalness={0.25} roughness={0.4} />
    </mesh>
    <group ref={figure}><PlayerFigure playerId={player.player_id} color={color} reduced={reduced} /></group>
  </group>;
}

function projectAnchor(element: HTMLSpanElement | undefined, position: Vector3, camera: Camera, size: { width: number; height: number }) {
  if (!element) return;
  position.project(camera);
  element.style.transform = `translate(${(position.x + 1) * size.width / 2 - 1}px,${(1 - position.y) * size.height / 2 - 1}px)`;
}

function SquareAnchors({ squares, anchors }: { squares: SquareInfo[]; anchors: Map<string, HTMLSpanElement> }) {
  const { camera, size } = useThree();
  useFrame(() => {
    for (const square of squares) projectAnchor(anchors.get(`square:${square.id}`), new Vector3(...boardPoint(square.position)), camera, size);
  });
  return null;
}
