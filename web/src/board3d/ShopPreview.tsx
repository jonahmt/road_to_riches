import { Component, type ReactNode } from "react";
import { Canvas } from "@react-three/fiber";
import { NeutralToneMapping } from "three";
import { PLAYER_COLORS } from "../boardColors";
import { ShopModel } from "./ShopModels";

class PreviewBoundary extends Component<{ children: ReactNode }, { failed: boolean }> {
  state = { failed: false };
  static getDerivedStateFromError() { return { failed: true }; }
  render() { return this.state.failed ? null : this.props.children; }
}

export default function ShopPreview({ owner, closed }: { owner: number | null; closed: boolean }) {
  return <PreviewBoundary><Canvas frameloop="demand" dpr={[1, 1.5]} camera={{ position: [3.4, 2.7, 5.4], fov: 32 }}
    gl={{ alpha: true, antialias: true, toneMapping: NeutralToneMapping }}>
    <ambientLight intensity={1.4} /><directionalLight position={[2, 5, 4]} intensity={2.5} />
    <group position={[0, -1.3, 0.3]}><ShopModel color={owner == null ? "#afb9bd" : PLAYER_COLORS[owner % PLAYER_COLORS.length]}
      closed={closed} activeOccupant={false} reduced /></group>
  </Canvas></PreviewBoundary>;
}
