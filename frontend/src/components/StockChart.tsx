import { useMemo, useState } from "react";

import type { PriceBar } from "../api/types";

type ChartRange = "1H" | "4H" | "Session";
type ChartStyle = "line" | "candles";

const WIDTH = 800;
const HEIGHT = 300;
const LEFT = 58;
const RIGHT = 18;
const PRICE_TOP = 18;
const PRICE_BOTTOM = 222;
const VOLUME_TOP = 242;
const VOLUME_BOTTOM = 278;

function dollars(value: number) {
  return value.toLocaleString("en-US", { style: "currency", currency: "USD" });
}

function chartTime(value: string) {
  return new Intl.DateTimeFormat("en-US", {
    hour: "numeric", minute: "2-digit", timeZone: "America/New_York",
  }).format(new Date(value));
}

function rangeBars(bars: PriceBar[], range: ChartRange) {
  if (range === "Session" || bars.length === 0) return bars;
  const hours = range === "1H" ? 1 : 4;
  const cutoff = new Date(bars[bars.length - 1].time).getTime() - hours * 60 * 60 * 1_000;
  return bars.filter((bar) => new Date(bar.time).getTime() >= cutoff);
}

function sessionKind(value: string) {
  const parts = new Intl.DateTimeFormat("en-US", {
    hour: "2-digit", minute: "2-digit", hourCycle: "h23", timeZone: "America/New_York",
  }).formatToParts(new Date(value));
  const minutes = Number(parts.find((part) => part.type === "hour")?.value ?? 0) * 60
    + Number(parts.find((part) => part.type === "minute")?.value ?? 0);
  if (minutes < 9 * 60 + 30) return "premarket";
  if (minutes < 16 * 60) return "regular";
  return "postmarket";
}

export function StockChart({ symbol, bars, loading, error }: {
  symbol: string;
  bars: PriceBar[];
  loading: boolean;
  error: string | null;
}) {
  const [range, setRange] = useState<ChartRange>("Session");
  const [chartStyle, setChartStyle] = useState<ChartStyle>(() => window.localStorage.getItem("stock-chart-style") === "candles" ? "candles" : "line");
  const [hoverIndex, setHoverIndex] = useState<number | null>(null);
  const visible = useMemo(() => rangeBars(bars, range), [bars, range]);

  if (loading) return <div className="stock-chart-state">Loading Alpaca price history…</div>;
  if (error) return <div className="stock-chart-state error"><b>Chart unavailable</b><span>{error}</span></div>;
  if (visible.length === 0) return <div className="stock-chart-state"><b>No bars reached yet</b><span>The chart will fill as the replay advances.</span></div>;

  const lows = visible.map((bar) => bar.low);
  const highs = visible.map((bar) => bar.high);
  const min = Math.min(...lows);
  const max = Math.max(...highs);
  const pricePadding = Math.max((max - min) * 0.08, max * 0.001);
  const low = min - pricePadding;
  const high = max + pricePadding;
  const spread = high - low || 1;
  const volumeMax = Math.max(...visible.map((bar) => bar.volume), 1);
  const plotWidth = WIDTH - LEFT - RIGHT;
  const x = (index: number) => LEFT + (visible.length === 1 ? plotWidth / 2 : index / (visible.length - 1) * plotWidth);
  const y = (price: number) => PRICE_BOTTOM - (price - low) / spread * (PRICE_BOTTOM - PRICE_TOP);
  const coordinates = visible.map((bar, index) => `${x(index)},${y(bar.close)}`).join(" ");
  const selectedIndex = Math.min(hoverIndex ?? visible.length - 1, visible.length - 1);
  const selected = visible[selectedIndex];
  const first = visible[0];
  const change = first.close ? (selected.close / first.close - 1) * 100 : 0;
  const gridPrices = [high, (high + low) / 2, low];
  const sessionSegments = visible.reduce<Array<{ kind: string; start: number; end: number }>>((segments, bar, index) => {
    const kind = sessionKind(bar.time);
    const last = segments[segments.length - 1];
    if (last?.kind === kind) last.end = index;
    else segments.push({ kind, start: index, end: index });
    return segments;
  }, []);

  function selectNearest(clientX: number, bounds: DOMRect) {
    const svgX = (clientX - bounds.left) / bounds.width * WIDTH;
    const ratio = Math.max(0, Math.min(1, (svgX - LEFT) / plotWidth));
    setHoverIndex(Math.round(ratio * (visible.length - 1)));
  }

  function chooseChartStyle(nextStyle: ChartStyle) {
    setChartStyle(nextStyle);
    window.localStorage.setItem("stock-chart-style", nextStyle);
  }

  return <div className="stock-chart">
    <div className="stock-chart-toolbar">
      <div className="stock-chart-quote">
        <strong>{dollars(selected.close)}</strong>
        <span className={change >= 0 ? "positive" : "negative"}>{change >= 0 ? "+" : ""}{change.toFixed(2)}%</span>
        <small>{chartTime(selected.time)} ET · O {dollars(selected.open)} · H {dollars(selected.high)} · L {dollars(selected.low)}</small>
      </div>
      <div className="chart-controls">
        <div className="chart-ranges" aria-label="Chart display">
          {(["line", "candles"] as ChartStyle[]).map((option) => <button type="button" key={option} className={chartStyle === option ? "active" : ""} aria-pressed={chartStyle === option} onClick={() => chooseChartStyle(option)}>{option === "line" ? "Line" : "Candles"}</button>)}
        </div>
        <div className="chart-ranges" aria-label="Chart range">
          {(["1H", "4H", "Session"] as ChartRange[]).map((option) => <button type="button" key={option} className={range === option ? "active" : ""} onClick={() => { setRange(option); setHoverIndex(null); }}>{option}</button>)}
        </div>
      </div>
    </div>
    <svg
      viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
      role="img"
      aria-label={`${symbol} Alpaca ${chartStyle === "candles" ? "candlestick" : "line"} price and volume chart`}
      onPointerMove={(event) => selectNearest(event.clientX, event.currentTarget.getBoundingClientRect())}
      onPointerLeave={() => setHoverIndex(null)}
    >
      <defs>
        <linearGradient id={`stock-fill-${symbol}`} x1="0" x2="0" y1="0" y2="1">
          <stop offset="0" stopColor="#6cf2a6" stopOpacity=".24" />
          <stop offset="1" stopColor="#6cf2a6" stopOpacity="0" />
        </linearGradient>
      </defs>
      {sessionSegments.map((segment) => {
        const halfStep = visible.length > 1 ? plotWidth / (visible.length - 1) / 2 : plotWidth / 2;
        const startX = Math.max(LEFT, x(segment.start) - halfStep);
        const endX = Math.min(WIDTH - RIGHT, x(segment.end) + halfStep);
        return <rect key={`${segment.kind}-${segment.start}`} className={`session-shade ${segment.kind}`} x={startX} y={PRICE_TOP} width={endX - startX} height={VOLUME_BOTTOM - PRICE_TOP} />;
      })}
      {gridPrices.map((price) => <g key={price}>
        <line className="stock-chart-grid" x1={LEFT} x2={WIDTH - RIGHT} y1={y(price)} y2={y(price)} />
        <text className="stock-chart-axis" x={LEFT - 8} y={y(price) + 4} textAnchor="end">{dollars(price)}</text>
      </g>)}
      {visible.map((bar, index) => {
        const barWidth = Math.max(1, Math.min(5, plotWidth / visible.length * .72));
        const barHeight = bar.volume / volumeMax * (VOLUME_BOTTOM - VOLUME_TOP);
        return <rect key={bar.time} className="stock-chart-volume" x={x(index) - barWidth / 2} y={VOLUME_BOTTOM - barHeight} width={barWidth} height={barHeight} />;
      })}
      {chartStyle === "line" ? <>
        <polygon points={`${LEFT},${PRICE_BOTTOM} ${coordinates} ${WIDTH - RIGHT},${PRICE_BOTTOM}`} fill={`url(#stock-fill-${symbol})`} />
        <polyline points={coordinates} fill="none" stroke="#6cf2a6" strokeWidth="2" vectorEffect="non-scaling-stroke" />
      </> : visible.map((bar, index) => {
        const candleWidth = Math.max(1.2, Math.min(7, plotWidth / visible.length * .72));
        const bodyTop = Math.min(y(bar.open), y(bar.close));
        const bodyHeight = Math.max(1, Math.abs(y(bar.open) - y(bar.close)));
        const direction = bar.close >= bar.open ? "up" : "down";
        return <g className={`stock-candle ${direction}`} key={`candle-${bar.time}`}>
          <line x1={x(index)} x2={x(index)} y1={y(bar.high)} y2={y(bar.low)} />
          <rect x={x(index) - candleWidth / 2} y={bodyTop} width={candleWidth} height={bodyHeight} />
        </g>;
      })}
      <line className="stock-chart-crosshair" x1={x(selectedIndex)} x2={x(selectedIndex)} y1={PRICE_TOP} y2={VOLUME_BOTTOM} />
      <circle cx={x(selectedIndex)} cy={y(selected.close)} r="4" fill="#07100d" stroke="#6cf2a6" strokeWidth="2" vectorEffect="non-scaling-stroke" />
      <text className="stock-chart-time" x={x(selectedIndex)} y={HEIGHT - 4} textAnchor={selectedIndex < visible.length / 2 ? "start" : "end"}>{chartTime(selected.time)} ET</text>
    </svg>
    <div className="stock-chart-legend"><span><i className="premarket-key" />Pre-market</span><span><i className="regular-key" />Regular market</span><span><i className="postmarket-key" />Post-market to 4:15 PM</span><span>Alpaca SIP · 1-minute bars</span></div>
  </div>;
}
