import { Environment, Float, Lightformer, Sparkles } from "@react-three/drei";
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { useEffect, useMemo, useRef, useState } from "react";
import * as THREE from "three";

type Brand = "apple" | "microsoft" | "nvidia" | "blackstone";

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

function drawApple(context: CanvasRenderingContext2D) {
  context.fillStyle = "#101412";
  context.beginPath();
  context.ellipse(105, 111, 38, 48, -0.18, 0, Math.PI * 2);
  context.ellipse(151, 111, 38, 48, 0.18, 0, Math.PI * 2);
  context.fill();
  context.beginPath();
  context.ellipse(141, 51, 13, 25, 0.75, 0, Math.PI * 2);
  context.fill();
  context.fillStyle = "#d8dce0";
  context.beginPath();
  context.arc(174, 94, 15, 0, Math.PI * 2);
  context.fill();
}

function drawMicrosoft(context: CanvasRenderingContext2D) {
  const size = 43;
  const gap = 6;
  const start = 82;
  context.fillStyle = "#f25022";
  context.fillRect(start, start, size, size);
  context.fillStyle = "#7fba00";
  context.fillRect(start + size + gap, start, size, size);
  context.fillStyle = "#00a4ef";
  context.fillRect(start, start + size + gap, size, size);
  context.fillStyle = "#ffb900";
  context.fillRect(start + size + gap, start + size + gap, size, size);
}

function drawNvidia(context: CanvasRenderingContext2D) {
  context.strokeStyle = "#76b900";
  context.lineWidth = 12;
  context.lineCap = "round";
  context.beginPath();
  context.moveTo(62, 116);
  context.bezierCurveTo(92, 76, 156, 72, 194, 110);
  context.bezierCurveTo(164, 148, 102, 151, 76, 117);
  context.bezierCurveTo(100, 94, 146, 93, 166, 115);
  context.bezierCurveTo(147, 133, 116, 132, 104, 115);
  context.stroke();
  context.fillStyle = "#76b900";
  context.beginPath();
  context.arc(135, 114, 12, 0, Math.PI * 2);
  context.fill();
  context.font = "700 24px Arial";
  context.textAlign = "center";
  context.fillText("NVIDIA", 128, 190);
}

function drawBlackstone(context: CanvasRenderingContext2D) {
  context.fillStyle = "#111514";
  context.fillRect(39, 76, 178, 104);
  context.strokeStyle = "#f2f3f3";
  context.lineWidth = 3;
  context.strokeRect(48, 85, 160, 86);
  context.fillStyle = "#f2f3f3";
  context.font = "700 20px Arial";
  context.textAlign = "center";
  context.fillText("BLACKSTONE", 128, 137);
}

function createBrandTexture(brand: Brand) {
  const canvas = document.createElement("canvas");
  canvas.width = 256;
  canvas.height = 256;
  const context = canvas.getContext("2d");
  if (!context) return new THREE.CanvasTexture(canvas);

  context.clearRect(0, 0, 256, 256);
  const silver = context.createRadialGradient(92, 72, 12, 128, 128, 124);
  silver.addColorStop(0, "#ffffff");
  silver.addColorStop(0.42, "#edf0f2");
  silver.addColorStop(0.78, "#c8cdd2");
  silver.addColorStop(1, "#f7f8f9");
  context.fillStyle = silver;
  context.beginPath();
  context.arc(128, 128, 124, 0, Math.PI * 2);
  context.fill();
  context.strokeStyle = "#ffffff";
  context.lineWidth = 5;
  context.stroke();
  if (brand === "apple") drawApple(context);
  if (brand === "microsoft") drawMicrosoft(context);
  if (brand === "nvidia") drawNvidia(context);
  if (brand === "blackstone") drawBlackstone(context);

  const texture = new THREE.CanvasTexture(canvas);
  texture.colorSpace = THREE.SRGBColorSpace;
  texture.anisotropy = 8;
  return texture;
}

function SpinningCoin({ brand, position, scale, speed, phase, rotation, reducedMotion }: CoinConfig & { reducedMotion: boolean }) {
  const group = useRef<THREE.Group>(null);
  const texture = useMemo(() => createBrandTexture(brand), [brand]);

  useEffect(() => () => texture.dispose(), [texture]);

  useFrame(({ clock }, delta) => {
    if (!group.current) return;
    const motionScale = reducedMotion ? 0.12 : 1;
    group.current.rotation.z += delta * speed * motionScale;
    group.current.rotation.y = rotation[1] + Math.sin(clock.elapsedTime * speed + phase) * 0.16 * motionScale;
    group.current.rotation.x = rotation[0] + Math.cos(clock.elapsedTime * speed * 0.7 + phase) * 0.08 * motionScale;
    group.current.position.y = position[1] + Math.sin(clock.elapsedTime * 0.8 * motionScale + phase) * (reducedMotion ? 0.035 : 0.14);
  });

  return (
    <group ref={group} position={position} rotation={rotation} scale={scale}>
      <mesh rotation={[Math.PI / 2, 0, 0]} castShadow>
        <latheGeometry args={[COIN_PROFILE, 64]} />
        <meshPhysicalMaterial color="#ffffff" metalness={0.94} roughness={0.08} clearcoat={1} clearcoatRoughness={0.04} envMapIntensity={2.4} />
      </mesh>
      <mesh position={[0, 0, 0.106]}>
        <circleGeometry args={[0.61, 64]} />
        <meshBasicMaterial map={texture} toneMapped={false} />
      </mesh>
      <mesh position={[0, 0, 0.111]}>
        <circleGeometry args={[0.61, 64]} />
        <meshPhysicalMaterial color="#ffffff" metalness={0.9} roughness={0.06} clearcoat={1} clearcoatRoughness={0.03} envMapIntensity={2.8} transparent opacity={0.12} depthWrite={false} />
      </mesh>
      <mesh position={[0, 0, -0.106]} rotation={[0, Math.PI, 0]}>
        <circleGeometry args={[0.61, 64]} />
        <meshBasicMaterial map={texture} toneMapped={false} />
      </mesh>
    </group>
  );
}

const TREND_ANGLE = 0.34;
const TREND_X = Math.cos(TREND_ANGLE);
const TREND_Y = Math.sin(TREND_ANGLE);
const PERIOD = 3.3;
const RISE = 0.6;
const AMP = 0.48;
const CORNERS = 12;
const LEG_STEPS = 4;
const SHAFT_POINTS = CORNERS * LEG_STEPS + 1;
const SHAFT_WIDTH = 0.46;
const SHAFT_OVERLAP = 0.22;
const HEAD_ANCHOR_X = 2.6;
const HEAD_ANCHOR_Y = 0.05;
const HEAD_WIDTH = 1.34;
const HEAD_LENGTH = 1.12;
const HEAD_TRAVEL = 0.62;
const HEAD_CYCLE = 6.4;
const SCROLL_CYCLE = 9;
const TAPER = PERIOD;
const FADE_START = -12.4;
const FADE_END = -9;
const GLOW_SPAN = PERIOD * 4;

function wrap(value: number, span: number) {
  const remainder = value % span;
  return remainder < 0 ? remainder + span : remainder;
}

// Triangle wave riding the trend line: a long climb, a short pullback, repeated
// every PERIOD. Because every period is identical, sliding the whole shaft
// forward by exactly PERIOD lands on the same shape, which is what lets the
// scroll loop without a seam.
function zigzagOffset(u: number, phase: number) {
  const cycle = wrap((u - phase) / PERIOD, 1);
  const wave = cycle < RISE ? cycle / RISE : (1 - cycle) / (1 - RISE);
  return AMP * (wave * 2 - 1);
}

// Corner positions along the trend axis: even indices are troughs, odd indices
// are crests. Building the shaft from these exact corners (rather than a
// uniform sample grid) keeps every leg dead straight and every miter clean.
function cornerU(index: number, phase: number) {
  const step = Math.floor(index / 2);
  return phase + (index % 2 === 0 ? step : step + RISE) * PERIOD;
}

// u runs along the trend axis with 0 at the head's resting base, negative back
// toward the tail. The zigzag flattens onto the trend line over the last TAPER
// units so the moving shaft always meets the head straight on.
function shaftPoint(u: number, phase: number, headBase: number, target: THREE.Vector3) {
  const offset = zigzagOffset(u, phase) * THREE.MathUtils.smoothstep(headBase - u, 0, TAPER);
  return target.set(
    HEAD_ANCHOR_X + TREND_X * u - TREND_Y * offset,
    HEAD_ANCHOR_Y + TREND_Y * u + TREND_X * offset,
    0,
  );
}

function InfiniteArrow({ reducedMotion }: { reducedMotion: boolean }) {
  const arrowGroup = useRef<THREE.Group>(null);
  const head = useRef<THREE.Mesh>(null);
  const headLight = useRef<THREE.PointLight>(null);
  const flowLight = useRef<THREE.PointLight>(null);
  const { viewport } = useThree();

  const shaftGeometry = useMemo(() => {
    const geometry = new THREE.BufferGeometry();
    const positions = new Float32Array(SHAFT_POINTS * 2 * 3);
    const colors = new Float32Array(SHAFT_POINTS * 2 * 4).fill(1);
    const indices: number[] = [];
    for (let index = 0; index < SHAFT_POINTS - 1; index += 1) {
      const left = index * 2;
      indices.push(left, left + 1, left + 2, left + 1, left + 3, left + 2);
    }
    geometry.setAttribute("position", new THREE.BufferAttribute(positions, 3));
    geometry.setAttribute("color", new THREE.BufferAttribute(colors, 4));
    geometry.setIndex(indices);
    return geometry;
  }, []);

  const headGeometry = useMemo(() => {
    const shape = new THREE.Shape();
    shape.moveTo(0, HEAD_WIDTH / 2);
    shape.lineTo(HEAD_LENGTH, 0);
    shape.lineTo(0, -HEAD_WIDTH / 2);
    shape.closePath();
    return new THREE.ShapeGeometry(shape);
  }, []);

  const samples = useMemo(() => Array.from({ length: SHAFT_POINTS }, () => new THREE.Vector3()), []);
  const sampleU = useMemo(() => new Float64Array(SHAFT_POINTS), []);
  const scratch = useMemo(() => ({
    incoming: new THREE.Vector3(),
    outgoing: new THREE.Vector3(),
    normalIn: new THREE.Vector3(),
    normalOut: new THREE.Vector3(),
    miter: new THREE.Vector3(),
    glow: new THREE.Vector3(),
  }), []);

  useEffect(() => () => {
    shaftGeometry.dispose();
    headGeometry.dispose();
  }, [shaftGeometry, headGeometry]);

  useFrame(({ clock }) => {
    if (!arrowGroup.current || !head.current) return;
    const compact = viewport.width < 6;
    const scale = Math.min(0.88, viewport.width / 8.2);
    arrowGroup.current.scale.set(scale, scale, 1);
    arrowGroup.current.position.set(compact ? -1.2 : 0, compact ? -1.7 : 0, 0);

    const time = clock.elapsedTime;
    // The shaft advances one PERIOD every SCROLL_CYCLE seconds and wraps there.
    const phase = reducedMotion ? PERIOD * 0.35 : (time / SCROLL_CYCLE) * PERIOD;
    // The head never leaves the pocket between the coins; it pushes back and
    // forth along the trend axis so the climb reads as ongoing, not parked.
    const headBase = reducedMotion ? 0 : Math.sin((time / HEAD_CYCLE) * Math.PI * 2) * (HEAD_TRAVEL / 2);
    const headEnd = headBase + SHAFT_OVERLAP;

    // Walk back CORNERS zigzag corners from the last one behind the head, then
    // run straight into the head. Legs are subdivided only so the tail fade has
    // something to gradate across.
    const relative = (headBase - phase) / PERIOD;
    const topCorner = Math.max(Math.floor(relative) * 2, Math.floor(relative - RISE) * 2 + 1);
    let previousU = cornerU(topCorner - CORNERS + 1, phase);
    let pointIndex = 0;
    sampleU[pointIndex] = previousU;
    shaftPoint(previousU, phase, headBase, samples[pointIndex]);
    pointIndex += 1;
    for (let corner = topCorner - CORNERS + 2; corner <= topCorner; corner += 1) {
      const nextU = cornerU(corner, phase);
      for (let step = 1; step <= LEG_STEPS; step += 1) {
        const u = previousU + ((nextU - previousU) * step) / LEG_STEPS;
        sampleU[pointIndex] = u;
        shaftPoint(u, phase, headBase, samples[pointIndex]);
        pointIndex += 1;
      }
      previousU = nextU;
    }
    for (let step = 1; step <= LEG_STEPS; step += 1) {
      const u = previousU + ((headEnd - previousU) * step) / LEG_STEPS;
      sampleU[pointIndex] = u;
      shaftPoint(u, phase, headBase, samples[pointIndex]);
      pointIndex += 1;
    }

    const position = shaftGeometry.attributes.position as THREE.BufferAttribute;
    const color = shaftGeometry.attributes.color as THREE.BufferAttribute;
    for (let index = 0; index < SHAFT_POINTS; index += 1) {
      const current = samples[index];
      const previous = samples[Math.max(0, index - 1)];
      const next = samples[Math.min(SHAFT_POINTS - 1, index + 1)];
      scratch.incoming.subVectors(current, previous);
      if (scratch.incoming.lengthSq() < 1e-8) scratch.incoming.subVectors(next, current);
      scratch.outgoing.subVectors(next, current);
      if (scratch.outgoing.lengthSq() < 1e-8) scratch.outgoing.copy(scratch.incoming);
      scratch.incoming.normalize();
      scratch.outgoing.normalize();
      scratch.normalIn.set(-scratch.incoming.y, scratch.incoming.x, 0);
      scratch.normalOut.set(-scratch.outgoing.y, scratch.outgoing.x, 0);
      scratch.miter.addVectors(scratch.normalIn, scratch.normalOut).normalize();
      const half = SHAFT_WIDTH / 2 / Math.max(0.5, scratch.miter.dot(scratch.normalOut));
      const alpha = THREE.MathUtils.smoothstep(sampleU[index], FADE_START, FADE_END);
      const left = index * 2;
      position.setXYZ(left, current.x + scratch.miter.x * half, current.y + scratch.miter.y * half, 0);
      position.setXYZ(left + 1, current.x - scratch.miter.x * half, current.y - scratch.miter.y * half, 0);
      color.setW(left, alpha);
      color.setW(left + 1, alpha);
    }
    position.needsUpdate = true;
    color.needsUpdate = true;

    head.current.position.set(HEAD_ANCHOR_X + TREND_X * headBase, HEAD_ANCHOR_Y + TREND_Y * headBase, 0.26);

    if (headLight.current) {
      headLight.current.position.copy(head.current.position);
      headLight.current.intensity = reducedMotion ? 0.8 : 3.4 + Math.sin((time / HEAD_CYCLE) * Math.PI * 2) * 1.4;
    }
    if (flowLight.current) {
      const travel = wrap(-phase, GLOW_SPAN);
      shaftPoint(headBase + 0.4 - travel, phase, headBase, scratch.glow);
      flowLight.current.position.set(scratch.glow.x, scratch.glow.y, 0.4);
      flowLight.current.intensity = reducedMotion ? 0 : 4.2 * Math.sin((1 - travel / GLOW_SPAN) * Math.PI);
    }
  });

  return (
    <group ref={arrowGroup}>
      <pointLight ref={flowLight} color="#8affbc" intensity={0} distance={3.2} decay={2} />
      <pointLight ref={headLight} color="#56ff9a" intensity={3.4} distance={4} decay={2} />
      <mesh geometry={shaftGeometry} position={[0, 0, 0.2]} frustumCulled={false}>
        <meshBasicMaterial color="#39ed82" toneMapped={false} side={THREE.DoubleSide} vertexColors transparent depthWrite={false} />
      </mesh>
      <mesh ref={head} geometry={headGeometry} position={[HEAD_ANCHOR_X, HEAD_ANCHOR_Y, 0.26]} rotation={[0, 0, TREND_ANGLE]}>
        <meshBasicMaterial color="#39ed82" toneMapped={false} side={THREE.DoubleSide} />
      </mesh>
    </group>
  );
}

type Streak = { x: number; y: number; z: number; speed: number; length: number };

function AirflowParticles({ reducedMotion }: { reducedMotion: boolean }) {
  const mesh = useRef<THREE.InstancedMesh>(null);
  const dummy = useMemo(() => new THREE.Object3D(), []);
  const streaks = useMemo<Streak[]>(() => Array.from({ length: 82 }, (_, index) => ({
    x: (Math.random() - 0.5) * 10.5,
    y: (Math.random() - 0.5) * 13,
    z: (Math.random() - 0.5) * 3 - 0.8,
    speed: 1.4 + Math.random() * 3.2,
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
      <boxGeometry args={[0.018, 0.32, 0.018]} />
      <meshBasicMaterial color="#75f7aa" transparent opacity={0.24} depthWrite={false} />
    </instancedMesh>
  );
}

function SceneCamera({ reducedMotion }: { reducedMotion: boolean }) {
  const { camera, pointer } = useThree();

  useFrame(() => {
    const strength = reducedMotion ? 0 : 0.18;
    camera.position.x = THREE.MathUtils.lerp(camera.position.x, pointer.x * strength, 0.035);
    camera.position.y = THREE.MathUtils.lerp(camera.position.y, pointer.y * strength, 0.035);
    camera.lookAt(0, 0, 0);
  });

  return null;
}

function CoinField({ reducedMotion }: { reducedMotion: boolean }) {
  const { viewport } = useThree();
  const compact = viewport.width < 6;

  return (
    <group scale={compact ? 0.4 : 1} position={compact ? [0.12, -1.55, 0.35] : [0, 0, 0]}>
      {COINS.map((coin) => <SpinningCoin key={coin.brand} {...coin} reducedMotion={reducedMotion} />)}
    </group>
  );
}

function Scene({ reducedMotion }: { reducedMotion: boolean }) {
  const stage = useRef<THREE.Group>(null);

  useFrame(({ clock }) => {
    if (!stage.current || reducedMotion) return;
    stage.current.rotation.y = Math.sin(clock.elapsedTime * 0.22) * 0.035;
  });

  return (
    <>
      <color attach="background" args={["#08120e"]} />
      <fog attach="fog" args={["#08120e", 8, 15]} />
      <ambientLight intensity={2.2} />
      <hemisphereLight color="#ffffff" groundColor="#2a4237" intensity={2.4} />
      <spotLight position={[4, 6, 6]} color="#ffffff" intensity={12} angle={0.62} penumbra={1} castShadow />
      <spotLight position={[-5, 2, 5]} color="#d8fff0" intensity={7} angle={0.7} penumbra={1} />
      <pointLight position={[-4, -2, 4]} color="#3bff8b" intensity={5} distance={10} />
      <Environment resolution={128}>
        <Lightformer form="rect" color="#ffffff" intensity={7} position={[0, 5, 3]} scale={[12, 2.5, 1]} />
        <Lightformer form="rect" color="#bfffe0" intensity={5} position={[-5, 0, 4]} rotation={[0, Math.PI / 2, 0]} scale={[8, 2, 1]} />
        <Lightformer form="rect" color="#ffffff" intensity={4} position={[6, -2, 2]} rotation={[0, -Math.PI / 3, 0]} scale={[6, 1.5, 1]} />
      </Environment>
      <SceneCamera reducedMotion={reducedMotion} />
      <group ref={stage}>
        <group rotation={[0, 0, -Math.PI / 4]}><AirflowParticles reducedMotion={reducedMotion} /></group>
        <InfiniteArrow reducedMotion={reducedMotion} />
        <CoinField reducedMotion={reducedMotion} />
        <Float speed={reducedMotion ? 0.08 : 0.45} rotationIntensity={0.06} floatIntensity={0.12}>
          <Sparkles count={34} scale={[6, 6, 3]} size={1.5} speed={reducedMotion ? 0.05 : 0.22} color="#a9ffd0" opacity={0.32} />
        </Float>
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
    return <div className="scene-fallback" role="img" aria-label="A green arrow rising between four silver company coins"><span>↑</span></div>;
  }

  return (
    <Canvas
      className="momentum-canvas"
      camera={{ position: [0, 0, 8.4], fov: 42 }}
      dpr={[1, 1.6]}
      frameloop={visible ? "always" : "demand"}
      gl={{ antialias: true, alpha: false, powerPreference: "high-performance" }}
      shadows
      aria-hidden="true"
    >
      <Scene reducedMotion={reducedMotion} />
    </Canvas>
  );
}
