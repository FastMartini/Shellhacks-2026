import { Environment, Lightformer, Sparkles } from "@react-three/drei";
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { type ReactNode, useEffect, useMemo, useRef, useState } from "react";
import * as THREE from "three";

import { CoinField } from "./MomentumCoins";
import { MomentumArrow } from "./MomentumArrow";

const FOG_COLOR = "#050807";

function useReducedMotion() {
  const [reduced, setReduced] = useState(false);

  useEffect(() => {
    const media = window.matchMedia("(prefers-reduced-motion: reduce)");
    const update = () => setReduced(media.matches);
    update();
    media.addEventListener("change", update);
    return () => media.removeEventListener("change", update);
  }, []);

  return reduced;
}

function hasWebGL() {
  try {
    const canvas = document.createElement("canvas");
    return Boolean(canvas.getContext("webgl2") || canvas.getContext("webgl"));
  } catch {
    return false;
  }
}

type Streak = { x: number; y: number; z: number; speed: number; length: number };

function AirflowParticles({ reducedMotion }: { reducedMotion: boolean }) {
  const mesh = useRef<THREE.InstancedMesh>(null);
  const dummy = useMemo(() => new THREE.Object3D(), []);
  const streaks = useMemo<Streak[]>(() => Array.from({ length: 40 }, (_, index) => ({
    x: (Math.random() - 0.5) * 10.5,
    y: (Math.random() - 0.5) * 13,
    z: (Math.random() - 0.5) * 3 - 0.8,
    speed: 0.9 + Math.random() * 2,
    length: 0.45 + Math.random() * 1.4 + (index % 5) * 0.08,
  })), []);

  useFrame(({ clock }, delta) => {
    if (!mesh.current) return;
    const movement = reducedMotion ? 0.08 : 1;
    streaks.forEach((streak, index) => {
      streak.y -= delta * streak.speed * movement;
      if (streak.y < -6.6) streak.y = 6.6;
      dummy.position.set(streak.x + Math.sin(clock.elapsedTime * 1.2 + index) * 0.08, streak.y, streak.z);
      dummy.scale.set(1, streak.length, 1);
      dummy.updateMatrix();
      mesh.current?.setMatrixAt(index, dummy.matrix);
    });
    mesh.current.instanceMatrix.needsUpdate = true;
  });

  return (
    <instancedMesh ref={mesh} args={[undefined, undefined, streaks.length]} frustumCulled={false}>
      <boxGeometry args={[0.008, 0.32, 0.008]} />
      <meshBasicMaterial color="#8fffc4" transparent opacity={0.16} depthWrite={false} />
    </instancedMesh>
  );
}

function SceneCamera({ reducedMotion }: { reducedMotion: boolean }) {
  const { camera, pointer } = useThree();

  useFrame(() => {
    const strength = reducedMotion ? 0 : 0.22;
    camera.position.x = THREE.MathUtils.lerp(camera.position.x, pointer.x * strength, 0.03);
    camera.position.y = THREE.MathUtils.lerp(camera.position.y, pointer.y * strength, 0.03);
    camera.lookAt(0, 0, 0);
  });

  return null;
}

// Center and size of the arrow head plus the four coins, in world units.
const COMPOSITION = { x: 3.05, y: -0.05, width: 3.6, height: 5.3 };
// Phones get the minimum; portrait tablets have room to grow toward the maximum.
const COMPACT_SCALE = { min: 0.34, max: 0.55, perUnitWidth: 1 / 8.5 };
const COMPACT_EDGE = 0.2;

// On narrow screens the copy stacks on top, so the arrow and coins shrink as
// one group into the bottom-right corner, keeping the head between the coins.
function Composition({ children }: { children: ReactNode }) {
  const group = useRef<THREE.Group>(null);

  useFrame(({ viewport }) => {
    if (!group.current) return;
    if (viewport.width >= 6) {
      group.current.scale.setScalar(1);
      group.current.position.set(0, 0, 0);
      return;
    }
    const scale = THREE.MathUtils.clamp(viewport.width * COMPACT_SCALE.perUnitWidth, COMPACT_SCALE.min, COMPACT_SCALE.max);
    const centerX = viewport.width / 2 - (COMPOSITION.width * scale) / 2 - COMPACT_EDGE;
    const centerY = -viewport.height / 2 + (COMPOSITION.height * scale) / 2 + COMPACT_EDGE;
    group.current.scale.setScalar(scale);
    group.current.position.set(centerX - COMPOSITION.x * scale, centerY - COMPOSITION.y * scale, 0);
  });

  return <group ref={group}>{children}</group>;
}

function Scene({ reducedMotion }: { reducedMotion: boolean }) {
  const stage = useRef<THREE.Group>(null);

  useFrame(({ clock }) => {
    if (!stage.current || reducedMotion) return;
    stage.current.rotation.y = Math.sin(clock.elapsedTime * 0.18) * 0.03;
  });

  return (
    <>
      <fog attach="fog" args={[FOG_COLOR, 8, 15]} />
      <ambientLight color="#eef6f2" intensity={1.1} />
      <hemisphereLight color="#ffffff" groundColor="#0f2119" intensity={1.4} />
      <spotLight position={[4, 6, 6]} color="#ffffff" intensity={16} angle={0.62} penumbra={1} />
      <spotLight position={[-5, 2, 5]} color="#d8fff0" intensity={6} angle={0.7} penumbra={1} />
      <pointLight position={[-4, -2, 4]} color="#5dffa8" intensity={2.4} distance={10} />
      <Environment resolution={128}>
        <Lightformer form="rect" color="#ffffff" intensity={7} position={[0, 5, 3]} scale={[12, 2.5, 1]} />
        <Lightformer form="rect" color="#d6fff0" intensity={5} position={[-5, 0, 4]} rotation={[0, Math.PI / 2, 0]} scale={[8, 2, 1]} />
        <Lightformer form="rect" color="#ffffff" intensity={4} position={[6, -2, 2]} rotation={[0, -Math.PI / 3, 0]} scale={[6, 1.5, 1]} />
        <Lightformer form="rect" color="#ffffff" intensity={3} position={[2, 0, 6]} scale={[0.6, 6, 1]} />
      </Environment>
      <SceneCamera reducedMotion={reducedMotion} />
      <group ref={stage}>
        <group rotation={[0, 0, -Math.PI / 4]}><AirflowParticles reducedMotion={reducedMotion} /></group>
        <Composition>
          <MomentumArrow reducedMotion={reducedMotion} />
          <CoinField reducedMotion={reducedMotion} />
        </Composition>
        <Sparkles count={40} position={[2, 0, 0]} scale={[7, 6, 3]} size={1.2} speed={reducedMotion ? 0.05 : 0.18} color="#c8ffe4" opacity={0.45} />
      </group>
    </>
  );
}

export function MomentumScene() {
  const reducedMotion = useReducedMotion();
  const [visible, setVisible] = useState(() => document.visibilityState !== "hidden");
  const [webGLAvailable] = useState(hasWebGL);

  useEffect(() => {
    const update = () => setVisible(document.visibilityState !== "hidden");
    document.addEventListener("visibilitychange", update);
    return () => document.removeEventListener("visibilitychange", update);
  }, []);

  if (!webGLAvailable) {
    return <div className="scene-fallback" role="img" aria-label="A green arrow rising between four platinum company coins"><span>↑</span></div>;
  }

  // The canvas is transparent: the page gradient behind it is the backdrop.
  return (
    <Canvas
      className="momentum-canvas"
      camera={{ position: [0, 0, 8.4], fov: 42 }}
      dpr={[1, 1.6]}
      frameloop={visible ? "always" : "demand"}
      gl={{ antialias: true, alpha: true, powerPreference: "high-performance", toneMapping: THREE.NeutralToneMapping }}
      aria-hidden="true"
    >
      <Scene reducedMotion={reducedMotion} />
    </Canvas>
  );
}
