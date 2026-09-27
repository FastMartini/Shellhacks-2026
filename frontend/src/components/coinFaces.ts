import * as THREE from "three";

export type Brand = "apple" | "microsoft" | "nvidia" | "blackstone";

export const TICKER_FONT = '500 40px "Geist Mono", monospace';
export const WORDMARK_FONT = '600 70px "Geist", sans-serif';

const TICKERS: Record<Brand, string> = { apple: "AAPL", microsoft: "MSFT", nvidia: "NVDA", blackstone: "BX" };

// Simple Icons outlines on a 24×24 grid.
const APPLE_PATH = "M12.152 6.896c-.948 0-2.415-1.078-3.96-1.04-2.04.027-3.91 1.183-4.961 3.014-2.117 3.675-.546 9.103 1.519 12.09 1.013 1.454 2.208 3.09 3.792 3.039 1.52-.065 2.09-.987 3.935-.987 1.831 0 2.35.987 3.96.948 1.637-.026 2.676-1.48 3.676-2.948 1.156-1.688 1.636-3.325 1.662-3.415-.039-.013-3.182-1.221-3.22-4.857-.026-3.04 2.48-4.494 2.597-4.559-1.429-2.09-3.623-2.324-4.39-2.376-2-.156-3.675 1.09-4.61 1.09zM15.53 3.83c.843-1.012 1.4-2.427 1.245-3.83-1.207.052-2.662.805-3.532 1.818-.78.896-1.454 2.338-1.273 3.714 1.338.104 2.715-.688 3.559-1.701";
const NVIDIA_PATH = "M8.948 8.798v-1.43a6.7 6.7 0 0 1 .424-.018c3.922-.124 6.493 3.374 6.493 3.374s-2.774 3.851-5.75 3.851c-.398 0-.787-.062-1.158-.185v-4.346c1.528.185 1.837.857 2.747 2.385l2.04-1.714s-1.492-1.952-4-1.952a6.016 6.016 0 0 0-.796.035m0-4.735v2.138l.424-.027c5.45-.185 9.01 4.47 9.01 4.47s-4.08 4.964-8.33 4.964c-.37 0-.733-.035-1.095-.097v1.325c.3.035.61.062.91.062 3.957 0 6.82-2.023 9.593-4.408.459.371 2.34 1.263 2.73 1.652-2.633 2.208-8.772 3.984-12.253 3.984-.335 0-.653-.018-.971-.053v1.864H24V4.063zm0 10.326v1.131c-3.657-.654-4.673-4.46-4.673-4.46s1.758-1.944 4.673-2.262v1.237H8.94c-1.528-.186-2.73 1.245-2.73 1.245s.68 2.412 2.739 3.11M2.456 10.9s2.164-3.197 6.5-3.533V6.201C4.153 6.59 0 10.653 0 10.653s2.35 6.802 8.948 7.42v-1.237c-4.84-.6-6.492-5.936-6.492-5.936z";

const SIZE = 1024;
const CENTER = SIZE / 2;
const METAL = ["#ffffff", "#cdd5d9", "#7f8a90"];
const ENAMEL = ["#1c2123", "#090c0d"];

// Each face is painted twice from the same drawing: once in color (platinum
// relief on dark enamel) and once as a metalness mask (white = metal), so the
// relief catches reflections and the enamel stays matte.
type Pass = "color" | "metal";

function paintFace(context: CanvasRenderingContext2D, brand: Brand, pass: Pass) {
  const isMask = pass === "metal";
  context.clearRect(0, 0, SIZE, SIZE);

  let metal: string | CanvasGradient = "#ffffff";
  if (!isMask) {
    const sheen = context.createLinearGradient(CENTER - 420, CENTER - 420, CENTER + 420, CENTER + 420);
    METAL.forEach((color, index) => sheen.addColorStop(index / (METAL.length - 1), color));
    metal = sheen;
  }
  if (isMask) {
    context.fillStyle = "#000000";
  } else {
    const enamel = context.createRadialGradient(CENTER - 140, CENTER - 170, 30, CENTER, CENTER, CENTER);
    enamel.addColorStop(0, ENAMEL[0]);
    enamel.addColorStop(1, ENAMEL[1]);
    context.fillStyle = enamel;
  }
  context.beginPath();
  context.arc(CENTER, CENTER, CENTER, 0, Math.PI * 2);
  context.fill();

  // Outer ring, tick marks, inner rule and faint guilloché rings.
  context.fillStyle = metal;
  context.beginPath();
  context.arc(CENTER, CENTER, 512, 0, Math.PI * 2);
  context.arc(CENTER, CENTER, 472, 0, Math.PI * 2, true);
  context.fill();
  context.strokeStyle = metal;
  context.globalAlpha = 0.6;
  context.lineWidth = 3;
  for (let tick = 0; tick < 160; tick += 1) {
    const angle = (tick / 160) * Math.PI * 2;
    context.beginPath();
    context.moveTo(CENTER + Math.cos(angle) * 438, CENTER + Math.sin(angle) * 438);
    context.lineTo(CENTER + Math.cos(angle) * 458, CENTER + Math.sin(angle) * 458);
    context.stroke();
  }
  context.globalAlpha = 1;
  context.lineWidth = 2;
  context.beginPath();
  context.arc(CENTER, CENTER, 422, 0, Math.PI * 2);
  context.stroke();
  context.globalAlpha = 0.07;
  context.lineWidth = 1.5;
  for (let radius = 36; radius < 410; radius += 11) {
    context.beginPath();
    context.arc(CENTER, CENTER, radius, 0, Math.PI * 2);
    context.stroke();
  }
  context.globalAlpha = 1;

  context.fillStyle = metal;
  if (brand === "apple") drawPath(context, APPLE_PATH, 15.5);
  if (brand === "nvidia") drawPath(context, NVIDIA_PATH, 15);
  if (brand === "microsoft") drawMicrosoft(context, isMask);
  if (brand === "blackstone") drawBlackstone(context);

  context.font = TICKER_FONT;
  context.textAlign = "center";
  context.textBaseline = "middle";
  context.letterSpacing = "14px";
  context.globalAlpha = 0.85;
  // Nudged right by half the letter spacing that trails the last glyph.
  context.fillText(TICKERS[brand], CENTER + 7, CENTER + 300);
  context.globalAlpha = 1;
  context.letterSpacing = "0px";
}

function drawPath(context: CanvasRenderingContext2D, path: string, scale: number) {
  context.save();
  context.translate(CENTER - 12 * scale, CENTER - 12 * scale - 44);
  context.scale(scale, scale);
  context.fill(new Path2D(path));
  context.restore();
}

function drawMicrosoft(context: CanvasRenderingContext2D, isMask: boolean) {
  const size = 148;
  const gap = 14;
  const x = CENTER - size - gap / 2;
  const y = CENTER - size - gap / 2 - 44;
  const tones = [1, 0.72, 0.72, 1];
  [[x, y], [x + size + gap, y], [x, y + size + gap], [x + size + gap, y + size + gap]].forEach(([left, top], index) => {
    context.globalAlpha = isMask ? 1 : tones[index];
    context.fillRect(left, top, size, size);
  });
  context.globalAlpha = 1;
}

function drawBlackstone(context: CanvasRenderingContext2D) {
  context.lineWidth = 6;
  context.strokeRect(CENTER - 310, CENTER - 150, 620, 200);
  context.font = WORDMARK_FONT;
  context.textAlign = "center";
  context.textBaseline = "middle";
  context.letterSpacing = "6px";
  const fit = Math.min(1, 540 / context.measureText("BLACKSTONE").width);
  context.save();
  context.translate(CENTER, CENTER - 48);
  context.scale(fit, fit);
  context.fillText("BLACKSTONE", 0, 0);
  context.restore();
  context.letterSpacing = "0px";
}

function canvasTexture(brand: Brand, pass: Pass) {
  const canvas = document.createElement("canvas");
  canvas.width = SIZE;
  canvas.height = SIZE;
  const context = canvas.getContext("2d");
  const texture = new THREE.CanvasTexture(canvas);
  texture.anisotropy = 8;
  const paint = () => {
    if (!context) return;
    paintFace(context, brand, pass);
    texture.needsUpdate = true;
  };
  paint();
  return { texture, paint };
}

export function createCoinFace(brand: Brand) {
  const color = canvasTexture(brand, "color");
  const metal = canvasTexture(brand, "metal");
  color.texture.colorSpace = THREE.SRGBColorSpace;
  const material = new THREE.MeshPhysicalMaterial({
    map: color.texture, metalnessMap: metal.texture, metalness: 1, roughness: 0.3,
    clearcoat: 0.8, clearcoatRoughness: 0.06, envMapIntensity: 1.6,
  });
  return {
    material,
    // Ticker and wordmark use web fonts; repaint once they finish loading.
    repaint() {
      color.paint();
      metal.paint();
    },
    dispose() {
      material.dispose();
      color.texture.dispose();
      metal.texture.dispose();
    },
  };
}

// Alternating light and dark bands, used as a bump map for the reeded edge.
export function createReedTexture() {
  const canvas = document.createElement("canvas");
  canvas.width = 512;
  canvas.height = 4;
  const context = canvas.getContext("2d");
  if (context) {
    for (let x = 0; x < 512; x += 4) {
      context.fillStyle = x % 8 === 0 ? "#ffffff" : "#000000";
      context.fillRect(x, 0, 4, 4);
    }
  }
  const texture = new THREE.CanvasTexture(canvas);
  texture.wrapS = THREE.RepeatWrapping;
  texture.repeat.set(4, 1);
  return texture;
}
