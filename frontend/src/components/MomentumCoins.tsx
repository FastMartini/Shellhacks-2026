import { useFrame } from "@react-three/fiber";
import { useEffect, useMemo, useRef } from "react";
import * as THREE from "three";

import { type Brand, createCoinFace, createReedTexture, TICKER_FONT, WORDMARK_FONT } from "./coinFaces";

type CoinConfig = {
  brand: Brand;
  position: [number, number, number];
  scale: number;
  speed: number;
  phase: number;
  rotation: [number, number, number];
};

const COINS: CoinConfig[] = [
  { brand: "apple", position: [2.35, 1.9, 0.5], scale: 0.9, speed: 0.55, phase: 0.2, rotation: [0.08, -0.12, -0.12] },
  { brand: "microsoft", position: [4.25, 0.65, -0.25], scale: 0.76, speed: 0.68, phase: 1.4, rotation: [-0.06, 0.12, 0.16] },
  { brand: "nvidia", position: [1.85, -1.75, -0.1], scale: 0.75, speed: 0.78, phase: 2.8, rotation: [0.06, 0.1, 0.1] },
  { brand: "blackstone", position: [4.15, -2.05, 0.4], scale: 0.84, speed: 0.48, phase: 4.1, rotation: [-0.08, -0.1, -0.14] },
];

const COIN_PROFILE = [
  new THREE.Vector2(0, -0.09),
  new THREE.Vector2(0.64, -0.09),
  new THREE.Vector2(0.71, -0.075),
  new THREE.Vector2(0.755, -0.035),
  new THREE.Vector2(0.755, 0.035),
  new THREE.Vector2(0.71, 0.075),
  new THREE.Vector2(0.64, 0.09),
  new THREE.Vector2(0, 0.09),
];

const RIM_COLOR = "#e7ebee";
// Every coin sits at least this far forward, so the arrow passes behind them.
const COIN_MIN_Z = 0.6;

function Coin({ brand, position, scale, speed, phase, rotation, reed, reducedMotion }: CoinConfig & { reed: THREE.Texture; reducedMotion: boolean }) {
  const group = useRef<THREE.Group>(null);
  const face = useMemo(() => createCoinFace(brand), [brand]);

  useEffect(() => {
    let cancelled = false;
    if (!document.fonts.check(TICKER_FONT) || !document.fonts.check(WORDMARK_FONT)) {
      Promise.all([document.fonts.load(TICKER_FONT), document.fonts.load(WORDMARK_FONT)])
        .then(() => { if (!cancelled) face.repaint(); })
        .catch(() => { /* keep the fallback-font paint */ });
    }
    return () => {
      cancelled = true;
      face.dispose();
    };
  }, [face]);

  // The coins sway rather than spin, so the ticker on each face stays readable.
  useFrame(({ clock }) => {
    if (!group.current) return;
    const time = clock.elapsedTime;
    const motionScale = reducedMotion ? 0.12 : 1;
    group.current.rotation.set(
      rotation[0] + Math.cos(time * speed * 0.6 + phase) * 0.1 * motionScale,
      rotation[1] - 0.28 + Math.sin(time * speed * 0.8 + phase) * 0.3 * motionScale,
      rotation[2] + Math.sin(time * speed * 0.5 + phase) * 0.1 * motionScale,
    );
    group.current.position.y = position[1] + Math.sin(time * 0.6 * motionScale + phase) * (reducedMotion ? 0.03 : 0.1);
  });

  return (
    <group ref={group} position={[position[0], position[1], Math.max(position[2], COIN_MIN_Z)]} scale={scale}>
      <mesh rotation={[Math.PI / 2, 0, 0]}>
        <latheGeometry args={[COIN_PROFILE, 96]} />
        <meshPhysicalMaterial color={RIM_COLOR} metalness={1} roughness={0.12} clearcoat={0.6} clearcoatRoughness={0.08} envMapIntensity={1.7} />
      </mesh>
      <mesh rotation={[Math.PI / 2, 0, 0]}>
        <cylinderGeometry args={[0.758, 0.758, 0.068, 160, 1, true]} />
        <meshPhysicalMaterial color={RIM_COLOR} metalness={1} roughness={0.26} bumpMap={reed} bumpScale={2} envMapIntensity={1.5} />
      </mesh>
      <mesh position={[0, 0, 0.092]} material={face.material}>
        <circleGeometry args={[0.61, 96]} />
      </mesh>
      <mesh position={[0, 0, -0.092]} rotation={[0, Math.PI, 0]} material={face.material}>
        <circleGeometry args={[0.61, 96]} />
      </mesh>
    </group>
  );
}

export function CoinField({ reducedMotion }: { reducedMotion: boolean }) {
  const reed = useMemo(createReedTexture, []);

  useEffect(() => () => reed.dispose(), [reed]);

  return COINS.map((coin) => <Coin key={coin.brand} {...coin} reed={reed} reducedMotion={reducedMotion} />);
}
