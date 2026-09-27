import { useFrame } from "@react-three/fiber";
import { useEffect, useMemo, useRef } from "react";
import * as THREE from "three";

// Round 4 of the landing hero design offered two weights: "bold" (4a) ships,
// "heavy" (4b) is the alternative. Swap ARROW to compare.
const ARROW_PRESETS = {
  bold: { width: 0.34, headWidth: 1.02, headLength: 1.08, amp: 0.3, x: 0.4, y: -0.45, reach: 0.3 },
  heavy: { width: 0.5, headWidth: 1.36, headLength: 1.36, amp: 0.4, x: 0.3, y: -0.6, reach: 0.22 },
};
const ARROW = ARROW_PRESETS.bold;

const TREND_ANGLE = 0.34;
const TREND_X = Math.cos(TREND_ANGLE);
const TREND_Y = Math.sin(TREND_ANGLE);
const PERIOD = 3.3;
const RISE = 0.6;
const CORNERS = 12;
const LEG_STEPS = 4;
const SHAFT_POINTS = CORNERS * LEG_STEPS + 1;
const LAST_LEG = 1 + (CORNERS - 2) * LEG_STEPS;
const HEAD_ANCHOR_X = 2.6;
const HEAD_ANCHOR_Y = 0.05;
const HEAD_OVERLAP = 0.3;
const HEAD_CYCLE = 6.4;
const SCALE = 0.88;
const TAIL_COLOR = "#1a7a4d";
const HEAD_COLOR = "#a4ffd0";
const LIGHT_COLOR = "#56ff9a";
// The shaft shades from TAIL_COLOR to HEAD_COLOR over this stretch of the
// trend axis (0 is the head, negative runs back toward the tail).
const COLOR_START = -16;
const COLOR_END = 0.2;

// The last rising leg: a long climb of RISE × PERIOD that gains 2 × amp.
const LEG_ANGLE = TREND_ANGLE + Math.atan2(2 * ARROW.amp, RISE * PERIOD);
const LEG_DIRECTION = new THREE.Vector3(Math.cos(LEG_ANGLE), Math.sin(LEG_ANGLE), 0);

// u runs along the trend axis, offset perpendicular to it.
function trendPoint(u: number, offset: number, target: THREE.Vector3) {
  return target.set(HEAD_ANCHOR_X + TREND_X * u - TREND_Y * offset, HEAD_ANCHOR_Y + TREND_Y * u + TREND_X * offset, 0);
}

// A fixed zigzag of straight legs: crests on the trend line, troughs 2 × amp
// below it, a long climb then a short pullback every PERIOD. Corners are listed
// from the far tail (well off-screen) up to the head's resting base at u = 0.
function buildShaft() {
  const corners = Array.from({ length: CORNERS }, (_, index) => {
    const back = CORNERS - 1 - index;
    return back % 2 === 0
      ? { u: -(back / 2) * PERIOD, offset: 0 }
      : { u: -((back - 1) / 2 + RISE) * PERIOD, offset: -2 * ARROW.amp };
  });
  const samples = Array.from({ length: SHAFT_POINTS }, () => new THREE.Vector3());
  const sampleU = new Float64Array(SHAFT_POINTS);
  const from = new THREE.Vector3();
  const to = new THREE.Vector3();
  trendPoint(corners[0].u, corners[0].offset, samples[0]);
  sampleU[0] = corners[0].u;
  let index = 1;
  for (let corner = 1; corner < CORNERS; corner += 1) {
    trendPoint(corners[corner - 1].u, corners[corner - 1].offset, from);
    trendPoint(corners[corner].u, corners[corner].offset, to);
    for (let step = 1; step <= LEG_STEPS; step += 1) {
      samples[index].lerpVectors(from, to, step / LEG_STEPS);
      sampleU[index] = corners[corner - 1].u + ((corners[corner].u - corners[corner - 1].u) * step) / LEG_STEPS;
      index += 1;
    }
  }
  // A short run past the tip, hidden under the head, so the two always meet.
  for (let step = 1; step <= LEG_STEPS; step += 1) {
    sampleU[index] = 0.05 * step;
    index += 1;
  }
  const legStart = trendPoint(corners[CORNERS - 2].u, corners[CORNERS - 2].offset, new THREE.Vector3());
  const tipBase = trendPoint(0, 0, new THREE.Vector3());
  return { samples, sampleU, legStart, tipBase };
}

export function MomentumArrow({ reducedMotion }: { reducedMotion: boolean }) {
  const head = useRef<THREE.Mesh>(null);
  const headLight = useRef<THREE.PointLight>(null);

  const shaft = useMemo(buildShaft, []);

  // Sample u never changes, so the color ramp is baked in once.
  const shaftGeometry = useMemo(() => {
    const geometry = new THREE.BufferGeometry();
    const colors = new Float32Array(SHAFT_POINTS * 2 * 3);
    const tail = new THREE.Color(TAIL_COLOR);
    const tip = new THREE.Color(HEAD_COLOR);
    const mix = new THREE.Color();
    const indices: number[] = [];
    for (let index = 0; index < SHAFT_POINTS; index += 1) {
      mix.copy(tail).lerp(tip, THREE.MathUtils.smoothstep(shaft.sampleU[index], COLOR_START, COLOR_END));
      mix.toArray(colors, index * 6);
      mix.toArray(colors, index * 6 + 3);
      if (index < SHAFT_POINTS - 1) {
        const left = index * 2;
        indices.push(left, left + 1, left + 2, left + 1, left + 3, left + 2);
      }
    }
    geometry.setAttribute("position", new THREE.BufferAttribute(new Float32Array(SHAFT_POINTS * 2 * 3), 3));
    geometry.setAttribute("color", new THREE.BufferAttribute(colors, 3));
    geometry.setIndex(indices);
    return geometry;
  }, [shaft]);

  const headGeometry = useMemo(() => {
    const shape = new THREE.Shape();
    shape.moveTo(0, ARROW.headWidth / 2);
    shape.lineTo(ARROW.headLength, 0);
    shape.lineTo(0, -ARROW.headWidth / 2);
    shape.closePath();
    return new THREE.ShapeGeometry(shape);
  }, []);

  const scratch = useMemo(() => ({
    tip: new THREE.Vector3(),
    incoming: new THREE.Vector3(),
    outgoing: new THREE.Vector3(),
    normalIn: new THREE.Vector3(),
    normalOut: new THREE.Vector3(),
    miter: new THREE.Vector3(),
  }), []);

  useEffect(() => () => {
    shaftGeometry.dispose();
    headGeometry.dispose();
  }, [shaftGeometry, headGeometry]);

  useFrame(({ clock }) => {
    if (!head.current) return;
    // Only the last rising leg moves: it pushes out and eases back along its
    // own direction, so the climb reads as ongoing while the tail stays put.
    const angle = (clock.elapsedTime / HEAD_CYCLE) * Math.PI * 2;
    const reach = reducedMotion ? 0 : -0.05 - Math.cos(angle) * ARROW.reach;
    const { samples, legStart, tipBase } = shaft;
    const tip = scratch.tip.copy(tipBase).addScaledVector(LEG_DIRECTION, reach);
    for (let step = 1; step <= LEG_STEPS; step += 1) {
      samples[LAST_LEG + step - 1].lerpVectors(legStart, tip, step / LEG_STEPS);
      samples[LAST_LEG + LEG_STEPS - 1 + step].copy(tip).addScaledVector(LEG_DIRECTION, (HEAD_OVERLAP * step) / LEG_STEPS);
    }

    // Offset each sample along the miter of its two legs so corners stay sharp
    // and the ribbon keeps a constant width.
    const position = shaftGeometry.attributes.position as THREE.BufferAttribute;
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
      const half = ARROW.width / 2 / Math.max(0.5, scratch.miter.dot(scratch.normalOut));
      const left = index * 2;
      position.setXYZ(left, current.x + scratch.miter.x * half, current.y + scratch.miter.y * half, 0);
      position.setXYZ(left + 1, current.x - scratch.miter.x * half, current.y - scratch.miter.y * half, 0);
    }
    position.needsUpdate = true;

    head.current.position.set(tip.x, tip.y, 0.26);
    if (headLight.current) {
      headLight.current.position.copy(head.current.position);
      headLight.current.intensity = reducedMotion ? 0.8 : 1.6 + Math.sin(angle) * 0.8;
    }
  });

  return (
    <group position={[ARROW.x, ARROW.y, 0]} scale={[SCALE, SCALE, 1]}>
      <pointLight ref={headLight} color={LIGHT_COLOR} intensity={1.6} distance={4} decay={2} />
      <mesh geometry={shaftGeometry} position={[0, 0, 0.2]} frustumCulled={false}>
        <meshBasicMaterial vertexColors toneMapped={false} fog={false} side={THREE.DoubleSide} />
      </mesh>
      <mesh ref={head} geometry={headGeometry} rotation={[0, 0, LEG_ANGLE]}>
        <meshBasicMaterial color={HEAD_COLOR} toneMapped={false} fog={false} side={THREE.DoubleSide} />
      </mesh>
    </group>
  );
}
