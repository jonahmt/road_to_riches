import { playbackNow, playbackSpeed } from "../playback";
import { Component, type ErrorInfo, type ReactNode, useContext, useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { Canvas, type ThreeEvent, useFrame, useThree } from "@react-three/fiber";
import {
  type Camera, Group, MeshStandardMaterial, NeutralToneMapping, Object3D, Plane, Raycaster, Vector2, Vector3,
} from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { RoundedBoxGeometry } from "three/addons/geometries/RoundedBoxGeometry.js";
import { PLAYER_COLORS } from "../boardColors";
import { adjacentStepAnimationDuration } from "../cameraTiming";
import { PresentationMotionContext } from "../usePresentationDirector";
import type { GameState, InputRequest, SquareInfo } from "../protocol";
import { boardExtent, boardPoint, canPickSquare, focusPoint, piecePositions, pieceStepPosition, TILE_SIZE, TILE_SURFACE_SIZE, TILE_TOP, type Point3, type BoardProjector } from "./geometry";
import { ShopModel, ShopRentPlaque, ShopSign } from "./ShopModels";
import { TextureReadinessContext, useTileTexture } from "./textures";
import { makeTileRim } from "./tileGeometry";
import { PlayerFigure } from "./PlayerFigure";
import { SkyBackdrop } from "./SkyBackdrop";
import { Courtyard } from "./Courtyard";
import { CivicBuilding } from "./CivicBuilding";
import { MovementGuideButtons, MovementGuideMeshes, type MovementButtons } from "./MovementGuides";
import { movementGuides } from "./movementPresentation";
import { MechanicalObject, type MechanicalObjectKind } from "./MechanicalObject";
import { SvgReliefParts } from "./SvgReliefParts";
import { nearbySquare, type BoardSquareSelection, type SquareCursorControl } from "../squarePickerNavigation";
import "./board3d.css";

const FOLLOW_CAMERA_OFFSET: Point3 = [0, 24, 24];

export interface TileArtwork {
  object: MechanicalObjectKind | null;
  uprightSuit: string | null;
  surface: string;
  symbol: string | null;
  sign: string | null;
  rentPlaque: string | null;
  border: string;
  description: string;
}

export type BoardSelection = BoardSquareSelection;

interface SceneProps {
  stockOpen: boolean;
  onReady: () => void;
  squareCursor: SquareCursorControl;
  onCursorSquareChange: (id: number | null) => void;
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
  const pendingTextures = useRef(new Set<object>());
  const [free, setFree] = useState(false);
  const [command, setCommand] = useState({ id: 0, action: "reset" });
  const [contextLost, setContextLost] = useState(false);
  const reduced = useReducedMotion();
  const root = useRef<HTMLDivElement>(null);
  const anchors = useRef(new Map<string, HTMLSpanElement>());
  const movementButtons = useRef<MovementButtons>(new Map());
  const selectionCursor = useRef<HTMLDivElement>(null);
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
    if (props.selection) {
      const square = props.state.board.squares.find((square) => square.id === id);
      if (square) { props.squareCursor.jumpTo = square.position; props.squareCursor.reframe = true; }
    }
    props.onSelectSquare(id);
    if (confirm && canPickSquare(id, props.selection?.eligibleSquareIds ?? null)) props.selection?.onConfirmSquare(id);
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
  return <div className="board3d-root" ref={root} data-camera-mode={props.selection ? "selection" : isFree ? "free" : "follow"}>
    <RendererBoundary onFallback={props.onFallback}>
      <Canvas shadows="percentage" dpr={[1, 1.75]} camera={{ fov: 38, near: 0.1, far: 1500, position: FOLLOW_CAMERA_OFFSET }}
        gl={{ antialias: true, powerPreference: "high-performance", toneMapping: NeutralToneMapping, toneMappingExposure: 1.08 }}
        fallback={<div className="board3d-error" aria-hidden="true">Your browser could not start WebGL.
          <button onClick={props.onFallback}>Use 2D view</button></div>}>
        <TextureReadinessContext.Provider value={pendingTextures.current}>
        <SceneReady pending={pendingTextures.current} onReady={props.onReady} />
        <SkyBackdrop />
        <hemisphereLight args={["#fff9ed", "#87a9b7", 1.6]} />
        <primitive object={lightTarget} />
        <directionalLight position={[extent.center[0] - 20, 45, extent.center[2] + 20]} intensity={1.8}
          target={lightTarget}
          castShadow shadow-mapSize={[2048, 2048]} shadow-bias={-0.00015} shadow-normalBias={0.015}
          shadow-camera-left={-shadowRadius} shadow-camera-right={shadowRadius}
          shadow-camera-top={shadowRadius} shadow-camera-bottom={-shadowRadius}
          shadow-camera-far={180} />
        <Courtyard squares={props.state.board.squares} />
        <CameraRig stockOpen={props.stockOpen} state={props.state} free={isFree} focusDistrictId={props.focusDistrictId}
          command={command} controlsRef={controls} reduced={reduced} projectorRef={props.projectorRef}
          selection={props.selection} cursor={props.squareCursor} />
        {props.state.board.squares.map((square) => <BoardTile key={square.id} square={square}
          artwork={props.artwork.get(square.id)!} selected={!props.selection && props.selectedSquareId === square.id}
          chosen={props.selection?.chosenSquareIds?.has(square.id) ?? false}
          eligible={true}
          focused={props.focusDistrictId !== null && square.property_district === props.focusDistrictId}
          activeOccupant={pieces.some((piece) => piece.active && piece.player.position === square.id)
            && pieces.filter((piece) => piece.player.position === square.id).length <= 4}
          reduced={reduced} anchors={anchors.current} onSelect={select} />)}
        {pieces.map((piece) => <PlayerPiece key={piece.player.player_id} {...piece}
          assignedPlayerId={props.assignedPlayerId} reduced={reduced} anchors={anchors.current} />)}
        <SquareAnchors squares={props.state.board.squares} artwork={props.artwork} anchors={anchors.current} />
        {props.selection && <SelectionCursor squares={props.state.board.squares} selection={props.selection}
          cursor={props.squareCursor} onSnap={props.onCursorSquareChange} reduced={reduced} element={selectionCursor} controlsRef={controls} />}
        {props.movementRequest && guides.length > 0 && <MovementGuideMeshes request={props.movementRequest}
          guides={guides} buttons={movementButtons.current} projectorRef={props.projectorRef} reduced={reduced} />}
        </TextureReadinessContext.Provider>
      </Canvas>
      <MovementGuideButtons guides={contextLost ? [] : guides} buttons={movementButtons.current} onChoose={props.onMovementChoice} />
    </RendererBoundary>
    {props.selection && <div ref={selectionCursor} className={`square-picker-cursor ${props.selectedSquareId === null ? "is-free" : props.selection.eligibleSquareIds.has(props.selectedSquareId) ? "" : "is-unavailable"}`}
      style={{ color: PLAYER_COLORS[(props.assignedPlayerId ?? 0) % PLAYER_COLORS.length] }} aria-hidden="true">
      <svg><path /></svg><span>{props.selection.eligibleSquareIds.has(props.selectedSquareId ?? -1) ? "▼" : "×"}</span>
    </div>}
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

function SceneReady({ pending, onReady }: { pending: Set<object>; onReady: () => void }) {
  const frames = useRef(0);
  const done = useRef(false);
  useFrame(() => {
    if (done.current) return;
    frames.current = pending.size ? 0 : frames.current + 1;
    // Allow React material updates and GPU uploads to reach two rendered frames.
    if (frames.current >= 3) { done.current = true; onReady(); }
  });
  return null;
}

function CameraRig({ stockOpen, state, free, focusDistrictId, command, controlsRef, reduced, projectorRef, selection, cursor }: {
  stockOpen: boolean; state: GameState; free: boolean; focusDistrictId: number | null;
  command: { id: number; action: string }; controlsRef: { current: OrbitControls | null }; reduced: boolean;
  projectorRef: { current: BoardProjector | null };
  selection: BoardSelection | null;
  cursor: SquareCursorControl;
}) {
  const presentation = useContext(PresentationMotionContext);
  const { camera, gl, size } = useThree();
  const picking = selection !== null;
  const savedView = useRef<{ position: Vector3; target: Vector3 } | null>(null);
  const pickerMotion = useRef<{ from: Vector3; fromTarget: Vector3; to: Vector3; toTarget: Vector3; start: number; duration: number } | null>(null);
  const intro = presentation.beat?.type === "turn_started";
  const shiftingLayout = presentation.beat?.type === "board_layout_changed";
  const layoutExtent = boardExtent(state.board.squares);
  const pitch = (stockOpen ? 72 : intro ? 32 : 52) * Math.PI / 180;
  const distance = (shiftingLayout || stockOpen) ? Math.max(35, layoutExtent.depth * 1.4, layoutExtent.width * size.height / size.width * 1.6) : intro ? 25 : 28;
  const followZoom = useRef(1);
  const offset = new Vector3(0, Math.sin(pitch) * distance, Math.cos(pitch) * distance);
  const profile = useRef({ from: offset.clone(), to: offset.clone(), start: 0 });
  const target = (shiftingLayout || stockOpen) ? layoutExtent.center : focusPoint(state, focusDistrictId);
  target[1] += intro ? 2.5 : 0.6;
  useLayoutEffect(() => {
    const orbit = controlsRef.current;
    profile.current = { from: orbit ? camera.position.clone().sub(orbit.target) : offset.clone(),
      to: offset.clone().multiplyScalar(followZoom.current), start: playbackNow() };
  }, [intro, shiftingLayout, stockOpen]);
  const targetRef = useRef(new Vector3(...target));
  const stepCamera = useRef({ from: new Vector3(...target), start: 0, duration: 0 });
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
    camera.position.copy(targetRef.current).add(offset);
    orbit.update();
    controlsRef.current = orbit;
    projectorRef.current = (point) => {
      const projected = new Vector3(...boardPoint(point)).project(camera);
      return [projected.x * gl.domElement.clientWidth, -projected.y * gl.domElement.clientHeight];
    };
    initialized.current = true;
    return () => { orbit.dispose(); controlsRef.current = null; projectorRef.current = null; };
  }, [camera, gl, reduced]);
  useLayoutEffect(() => {
    stepCamera.current = { from: controlsRef.current?.target.clone() ?? targetRef.current.clone(),
      start: playbackNow(), duration: reduced ? 0 : adjacentStepAnimationDuration(-1, null) };
    targetRef.current.set(...target);
  }, [target[0], target[1], target[2]]);
  useLayoutEffect(() => {
    const orbit = controlsRef.current;
    if (!orbit) return;
    let to: Vector3, toTarget: Vector3;
    if (picking) {
      if (!savedView.current) savedView.current = { position: camera.position.clone(), target: orbit.target.clone() };
      const square = state.board.squares.find((square) => square.id === selection.selectedSquareId);
      const focus = square ? boardPoint(square.position) : target;
      const distance = Math.max(30, Math.min(38, Math.max(extent.width, extent.depth) * 0.85));
      toTarget = new Vector3(...focus);
      to = toTarget.clone().add(new Vector3(...FOLLOW_CAMERA_OFFSET).normalize().multiplyScalar(distance));
    } else {
      if (!savedView.current) return;
      to = savedView.current.position; toTarget = savedView.current.target; savedView.current = null;
    }
    pickerMotion.current = { from: camera.position.clone(), fromTarget: orbit.target.clone(), to, toTarget,
      start: playbackNow(), duration: reduced ? 0 : 400 };
  }, [picking, reduced, size.width, size.height]);
  useEffect(() => {
    const orbit = controlsRef.current;
    if (!orbit) return;
    orbit.enableRotate = free && !picking;
    orbit.maxPolarAngle = free && !picking ? Math.PI / 2 - 0.09 : Math.PI / 2.8;
    orbit.enablePan = free && !picking;
    orbit.enableZoom = !picking;
    if (free && !previousFree.current) savedDistance.current = orbit.getDistance();
    if (!free && previousFree.current) {
      // Return to the board's original orientation so WASD remains intuitive.
      camera.position.copy(orbit.target).add(offset.clone().normalize().multiplyScalar(savedDistance.current));
      orbit.update();
    }
    previousFree.current = free;
  }, [free, picking, camera, controlsRef, reduced]);
  useEffect(() => {
    const orbit = controlsRef.current;
    if (!orbit) return;
    const rememberZoom = () => {
      if (free || picking) return;
      followZoom.current = orbit.getDistance() / distance;
      const current = camera.position.clone().sub(orbit.target);
      profile.current = { from: current, to: current.clone(), start: playbackNow() };
    };
    orbit.addEventListener("end", rememberZoom);
    return () => orbit.removeEventListener("end", rememberZoom);
  }, [free, picking, intro, camera]);
  useEffect(() => {
    const orbit = controlsRef.current;
    if (!orbit || command.id === 0) return;
    if (!free) {
      followZoom.current = command.action === "reset" ? 1
        : Math.max(0.65, Math.min(2.5, followZoom.current * (command.action === "in" ? 0.8 : 1.25)));
      profile.current = { from: camera.position.clone().sub(orbit.target),
        to: offset.clone().multiplyScalar(followZoom.current), start: playbackNow() };
      return;
    }
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
    if (picking && !savedView.current) {
      savedView.current = { position: camera.position.clone(), target: orbit.target.clone() };
    }
    if (picking && cursor.reframe && (cursor.jumpTo || cursor.position)) {
      const focus = (cursor.jumpTo ?? cursor.position)!;
      const distance = Math.max(30, Math.min(38, Math.max(extent.width, extent.depth) * 0.85));
      const toTarget = new Vector3(focus[0], TILE_TOP, focus[1]);
      pickerMotion.current = { from: camera.position.clone(), fromTarget: orbit.target.clone(), toTarget,
        to: toTarget.clone().add(new Vector3(...FOLLOW_CAMERA_OFFSET).normalize().multiplyScalar(distance)),
        start: playbackNow(), duration: reduced ? 0 : 400 };
      cursor.reframe = false;
    }
    const picker = pickerMotion.current;
    if (picker) {
      const progress = picker.duration ? Math.min(1, (playbackNow() - picker.start) / picker.duration) : 1;
      const blend = progress * progress * (3 - 2 * progress);
      camera.position.lerpVectors(picker.from, picker.to, blend);
      orbit.target.lerpVectors(picker.fromTarget, picker.toTarget, blend);
      if (progress >= 1) pickerMotion.current = null;
    } else if (!free && !picking) {
      const step = stepCamera.current;
      const next = presentation.beat?.type === "piece_moved"
        ? step.from.clone().lerp(targetRef.current, step.duration ? Math.min(1, (playbackNow() - step.start) / step.duration) : 1)
        : orbit.target.clone().lerp(targetRef.current, reduced ? 1 : 1 - Math.exp(-delta * playbackSpeed() * 14));
      camera.position.add(next.clone().sub(orbit.target));
      orbit.target.copy(next);
      const p = profile.current;
      const elapsed = reduced ? 1 : Math.min(1, (playbackNow() - p.start) / 450);
      const blend = elapsed * elapsed * (3 - 2 * elapsed);
      camera.position.copy(next).add(p.from.clone().lerp(p.to, blend));
    }
    orbit.update(delta);
    if (free || (orbit.target.distanceTo(targetRef.current) < 0.025 &&
      camera.position.clone().sub(orbit.target).distanceTo(profile.current.to) < 0.025)) {
      presentation.complete("camera", presentation.beat?.requestId);
    }
  });
  return null;
}

function SelectionCursor({ squares, selection, cursor, onSnap, reduced, element, controlsRef }: {
  controlsRef: { current: OrbitControls | null };
  squares: SquareInfo[]; selection: BoardSelection; cursor: SquareCursorControl;
  onSnap: (id: number | null) => void; reduced: boolean; element: { current: HTMLDivElement | null };
}) {
  const { camera, size, gl } = useThree();
  const pointer = useRef<[number, number] | null>(null);
  const lastSnap = useRef<number | null | undefined>(undefined);
  const ray = useMemo(() => new Raycaster(), []);
  const plane = useMemo(() => new Plane(new Vector3(0, 1, 0), -TILE_TOP), []);
  const extent = useMemo(() => boardExtent(squares), [squares]);
  useEffect(() => {
    cursor.attached = true;
    const move = (event: PointerEvent) => {
      if (!cursor.enabled || event.buttons) return;
      const rect = gl.domElement.getBoundingClientRect();
      const prior = pointer.current ?? [0, 0];
      pointer.current = [prior[0] + event.movementX / rect.width * 2, prior[1] - event.movementY / rect.height * 2];
    };
    gl.domElement.addEventListener("pointermove", move);
    return () => { cursor.attached = false; cursor.keys.clear(); gl.domElement.removeEventListener("pointermove", move); };
  }, [gl]);
  useFrame((_, delta) => {
    if (!element.current) return;
    if (cursor.jumpTo) { cursor.position = [...cursor.jumpTo]; cursor.jumpTo = null; pointer.current = null; }
    if (!cursor.position) { element.current.style.visibility = "hidden"; return; }
    const keys = cursor.keys;
    const x = Number(keys.has("d") || keys.has("arrowright")) - Number(keys.has("a") || keys.has("arrowleft"));
    const z = Number(keys.has("s") || keys.has("arrowdown")) - Number(keys.has("w") || keys.has("arrowup"));
    if (cursor.enabled && (x || z)) {
      const step = Math.min(delta, 0.05) * 12 / Math.hypot(x, z);
      cursor.position = [cursor.position[0] + x * step, cursor.position[1] + z * step];
      pointer.current = null;
    } else if (cursor.enabled && pointer.current) {
      ray.setFromCamera(new Vector2(...pointer.current), camera);
      const hit = ray.ray.intersectPlane(plane, new Vector3());
      ray.setFromCamera(new Vector2(0, 0), camera);
      const center = ray.ray.intersectPlane(plane, new Vector3());
      if (hit && center) cursor.position = [cursor.position[0] + hit.x - center.x, cursor.position[1] + hit.z - center.z];
      pointer.current = null;
    }
    cursor.position = [
      Math.max(extent.center[0] - extent.width / 2, Math.min(extent.center[0] + extent.width / 2, cursor.position[0])),
      Math.max(extent.center[2] - extent.depth / 2, Math.min(extent.center[2] + extent.depth / 2, cursor.position[1])),
    ];
    const candidates = squares.filter((square) => cursor.snapAll || square.type === "SHOP" || selection.eligibleSquareIds.has(square.id));
    const snapped = nearbySquare(cursor.position, candidates);
    const target = snapped?.position ?? cursor.position;
    const blend = reduced || !cursor.display ? 1 : 1 - Math.exp(-delta * 28);
    const from = cursor.display ?? target;
    cursor.display = [from[0] + (target[0] - from[0]) * blend, from[1] + (target[1] - from[1]) * blend];
    const orbit = controlsRef.current;
    if (orbit) {
      const center = new Vector3(cursor.display[0], TILE_TOP + 0.05, cursor.display[1]);
      camera.position.add(center.clone().sub(orbit.target));
      orbit.target.copy(center);
      orbit.update();
      camera.updateMatrixWorld();
    }
    const id = snapped?.id ?? null;
    if (id !== lastSnap.current) { lastSnap.current = id; onSnap(id); }
    // Project each bracket leg from one horizontal plane, rather than enclosing
    // the building in an axis-aligned screen rectangle. Keep the SVG overlay crisp.
    const half = TILE_SIZE / 2 + 0.08;
    const leg = 0.65;
    const corners = [-1, 1].flatMap((sx) => [-1, 1].map((sz) =>
      [[sx * (half - leg), sz * half], [sx * half, sz * half], [sx * half, sz * (half - leg)]].map(([dx, dz]) => {
        const point = new Vector3(cursor.display![0] + dx, TILE_TOP + 0.05, cursor.display![1] + dz).project(camera);
        return [(point.x + 1) * size.width / 2, (1 - point.y) * size.height / 2];
      })));
    const points = corners.flat();
    const left = Math.min(...points.map((p) => p[0]));
    const right = Math.max(...points.map((p) => p[0]));
    const top = Math.min(...points.map((p) => p[1]));
    const bottom = Math.max(...points.map((p) => p[1]));
    element.current.querySelector("path")?.setAttribute("d", corners.map((corner) =>
      corner.map(([x, y], index) => `${index ? "L" : "M"}${x - left},${y - top}`).join(" ")).join(" "));
    Object.assign(element.current.style, { visibility: "visible", transform: `translate(${left}px,${top}px)`,
      width: `${right - left}px`, height: `${bottom - top}px` });
    element.current.dataset.cursorX = String(cursor.position[0]);
    element.current.dataset.cursorZ = String(cursor.position[1]);
    element.current.dataset.snappedSquare = id === null ? "" : String(id);
  });
  return null;
}

function BoardTile({ square, artwork, selected, chosen, eligible, focused, activeOccupant, reduced, anchors, onSelect }: {
  square: SquareInfo; artwork: TileArtwork; selected: boolean; chosen: boolean;
  eligible: boolean; focused: boolean; activeOccupant: boolean; reduced: boolean; onSelect: (id: number, confirm: boolean) => void;
  anchors: Map<string, HTMLSpanElement>;
}) {
  const tile = useRef<Group>(null);
  const initial = useRef(boardPoint(square.position, 0));
  const destination = boardPoint(square.position, 0);
  const motion = useRef({ from: initial.current, start: 0 });
  useLayoutEffect(() => {
    motion.current = { from: tile.current?.position.toArray() as Point3 ?? destination, start: playbackNow() };
  }, [square.position[0], square.position[1]]);
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
    const progress = reduced ? 1 : Math.min(1, (playbackNow() - motion.current.start) / 1200);
    const eased = progress * progress * (3 - 2 * progress);
    tile.current?.position.set(...destination.map((value, i) => motion.current.from[i] + (value - motion.current.from[i]) * eased) as Point3);
    if (glow.current) glow.current.emissiveIntensity = focused
      ? (reduced ? 0.35 : 0.3 + Math.sin(clock.elapsedTime * 5) * 0.2) : 0;
  });
  const shop = square.type === "SHOP";
  const bank = ["BANK", "STOCKBROKER"].includes(square.type);
  return <group ref={tile} position={initial.current}
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
      <meshStandardMaterial key={texture?.uuid ?? "loading"} map={texture} color={eligible ? (hovered ? "#ffffff" : "#fafafa") : "#49515a"}
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
    {shop && artwork.rentPlaque && <ShopRentPlaque markup={artwork.rentPlaque} dimmed={!eligible} activeOccupant={activeOccupant} />}
    {shop && square.property_owner !== null && <ShopModel color={eligible
      ? PLAYER_COLORS[square.property_owner % PLAYER_COLORS.length] : "#46505a"}
      activeOccupant={activeOccupant} reduced={reduced}
      closed={square.statuses.some((status) => status.type === "closed")} />}
    {bank && <group position={activeOccupant ? [-0.85, TILE_TOP / 2, -1.25] : [0, 0, 0]} scale={activeOccupant ? 0.5 : 1}>
      <CivicBuilding color={eligible ? (square.type === "BANK" ? "#d2a543" : "#359e78") : "#46505a"}
        stockbroker={square.type === "STOCKBROKER"} />
    </group>}
    {artwork.object && <group position={activeOccupant ? [-0.85, TILE_TOP / 2, -1.1] : [0, 0, 0]} scale={activeOccupant ? 0.5 : 1}>
      <MechanicalObject kind={artwork.object} dimmed={!eligible} />
    </group>}
    {artwork.uprightSuit && <SuitToken markup={artwork.uprightSuit} dimmed={!eligible} reduced={reduced}
      squareId={square.id} anchors={anchors} activeOccupant={activeOccupant} />}
    {!shop && !bank && !artwork.object && artwork.symbol && <SymbolRelief markup={artwork.symbol} dimmed={!eligible} />}
  </group>;
}

function SymbolRelief({ markup, dimmed }: { markup: string; dimmed: boolean }) {
  const scale = TILE_SURFACE_SIZE / TILE_SIZE;
  return <group position={[0, TILE_TOP + 0.015, 0]} rotation={[-Math.PI / 2, 0, 0]} scale={[scale, -scale, 1]}>
    <SvgReliefParts markup={markup} dimmed={dimmed} />
  </group>;
}

function SuitToken({ markup, dimmed, reduced, squareId, anchors, activeOccupant }: {
  activeOccupant: boolean;
  markup: string; dimmed: boolean; reduced: boolean; squareId: number; anchors: Map<string, HTMLSpanElement>;
}) {
  const group = useRef<Group>(null);
  const point = useMemo(() => new Vector3(), []);
  const { camera, size } = useThree();
  useFrame(({ clock }) => {
    if (!group.current) return;
    group.current.position.y = (activeOccupant ? TILE_TOP + 1.15 : TILE_TOP + 1.6) + (reduced ? 0 : Math.sin(clock.elapsedTime * 1.8 + squareId) * 0.06);
    group.current.rotation.y = reduced ? 0.18 : clock.elapsedTime * 0.45 + squareId * 0.7;
    projectAnchor(anchors.get(`square:${squareId}`), group.current.getWorldPosition(point), camera, size);
  });
  return <group ref={group} position={activeOccupant ? [-0.95, TILE_TOP + 1.15, -1] : [0, TILE_TOP + 1.6, 0]} scale={activeOccupant ? 0.65 : 1}>
    <group position={[0, 0, -0.14]} scale={[0.95, -0.95, 1]}>
      <SvgReliefParts markup={markup} dimmed={dimmed} depth={0.28} bevel={0.045} roughness={0.32} metalness={0.16} />
    </group>
  </group>;
}

function PlayerPiece({ player, active, position, scale, baseRadius, assignedPlayerId, reduced, anchors }: ReturnType<typeof piecePositions>[number] & {
  assignedPlayerId: number | null; reduced: boolean; anchors: Map<string, HTMLSpanElement>;
}) {
  const presentation = useContext(PresentationMotionContext);
  const group = useRef<Group>(null);
  const figure = useRef<Group>(null);
  const heading = useRef(0);
  const stride = useRef(-1);
  const initialPosition = useRef(position);
  const initialScale = useRef(scale);
  const { camera, size } = useThree();
  const destination = useRef(position);
  const transition = useRef({ from: position, start: 0, duration: 0, layout: false });
  const color = PLAYER_COLORS[player.player_id % PLAYER_COLORS.length];
  useLayoutEffect(() => {
    if (group.current) transition.current = { from: group.current.position.toArray() as Point3, start: playbackNow(),
      duration: reduced ? 0 : presentation.beat?.type === "board_layout_changed" ? 1200 : adjacentStepAnimationDuration(player.player_id, assignedPlayerId),
      layout: presentation.beat?.type === "board_layout_changed" };
    const from = transition.current.from;
    if (Math.hypot(position[0] - from[0], position[2] - from[2]) > 0.1) {
      heading.current = Math.atan2(position[0] - from[0], position[2] - from[2]);
    }
    destination.current = position;
  }, [position[0], position[1], position[2], reduced, assignedPlayerId, player.player_id, player.position, baseRadius]);
  useFrame((_, delta) => {
    if (!group.current) return;
    const motion = transition.current;
    const progress = motion.duration ? Math.min(1, (playbackNow() - motion.start) / motion.duration) : 1;
    group.current.position.set(...(motion.layout
      ? destination.current.map((value, i) => motion.from[i] + (value - motion.from[i]) * progress * progress * (3 - 2 * progress)) as Point3
      : pieceStepPosition(motion.from, destination.current, progress)));
    group.current.scale.setScalar(reduced ? scale : group.current.scale.x +
      (scale - group.current.scale.x) * (1 - Math.exp(-20 * delta * playbackSpeed())));
    const traveling = !motion.layout && Math.hypot(motion.from[0] - destination.current[0], motion.from[2] - destination.current[2]) > 0.1;
    stride.current = !reduced && traveling && progress < 1 ? progress : -1;
    if (figure.current) {
      if (presentation.beat?.type === "turn_started") heading.current = 0;
      const turn = Math.atan2(Math.sin(heading.current - figure.current.rotation.y), Math.cos(heading.current - figure.current.rotation.y));
      figure.current.rotation.y += reduced ? turn : turn * (1 - Math.exp(-delta * playbackSpeed() * 24));
      const arc = !reduced && traveling ? Math.sin(progress * Math.PI) : 0;
      figure.current.position.y = arc * 0.7;
      const landing = !reduced && traveling && progress >= 1
        ? Math.max(0, 1 - (playbackNow() - motion.start - motion.duration) / 150) : 0;
      figure.current.scale.set(1 + landing * 0.1, 1 - landing * 0.12 + arc * 0.035, 1 + landing * 0.1);
    }
    if (progress >= 1 && presentation.beat?.playerId === player.player_id) {
      presentation.complete("piece", presentation.beat.requestId);
    }
    projectAnchor(anchors.get(`player:${player.player_id}`), group.current.position.clone().add(
      new Vector3(0, (1.2 + (figure.current?.position.y ?? 0)) * group.current.scale.y, 0)), camera, size);
  });
  return <group ref={group} position={initialPosition.current} scale={initialScale.current}>
    <mesh position={[0, 0.12, 0]} castShadow receiveShadow>
      <cylinderGeometry args={[baseRadius * 0.9, baseRadius, 0.22, 24]} /><meshStandardMaterial color={active ? "#fff4ce" : color} metalness={0.25} roughness={0.4} />
    </mesh>
    <group ref={figure}><PlayerFigure playerId={player.player_id} color={color} reduced={reduced} stride={stride} /></group>
  </group>;
}

function projectAnchor(element: HTMLSpanElement | undefined, position: Vector3, camera: Camera, size: { width: number; height: number }) {
  if (!element) return;
  position.project(camera);
  element.style.transform = `translate(${(position.x + 1) * size.width / 2 - 1}px,${(1 - position.y) * size.height / 2 - 1}px)`;
}

function SquareAnchors({ squares, artwork, anchors }: {
  squares: SquareInfo[]; artwork: Map<number, TileArtwork>; anchors: Map<string, HTMLSpanElement>;
}) {
  const { camera, size } = useThree();
  useFrame(() => {
    for (const square of squares) {
      if (artwork.get(square.id)?.uprightSuit) continue;
      projectAnchor(anchors.get(`square:${square.id}`), new Vector3(...boardPoint(square.position)), camera, size);
    }
  });
  return null;
}
