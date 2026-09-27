import { useEffect, useMemo, useRef, useState } from "react";

import type { PriceBar } from "../api/types";

type ChartRange = "1H" | "4H" | "Session";
type ChartStyle = "line" | "candles";
type ChartWindow = { size: number; end: number | null };

const DEFAULT_WINDOW = 120;
const MIN_WINDOW = 10;

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

function chartPointerRatio(clientX: number, bounds: DOMRect) {
  const svgX = (clientX - bounds.left) / bounds.width * WIDTH;
  return Math.max(0, Math.min(1, (svgX - LEFT) / (WIDTH - LEFT - RIGHT)));
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

export function StockChart({ symbol, bars, loading, error, analysisMode = false, displayStyle, onDisplayStyleChange, onWheelZoom, onPanBars }: {
  symbol: string;
  bars: PriceBar[];
  loading: boolean;
  error: string | null;
  analysisMode?: boolean;
  displayStyle?: ChartStyle;
  onDisplayStyleChange?: (style: ChartStyle) => void;
  onWheelZoom?: (delta: number, anchor: number) => void;
  onPanBars?: (bars: number) => void;
}) {
  const [range, setRange] = useState<ChartRange>("Session");
  const [savedChartStyle, setSavedChartStyle] = useState<ChartStyle>(() => window.localStorage.getItem("stock-chart-style") === "candles" ? "candles" : "line");
  const chartStyle = displayStyle ?? savedChartStyle;
  const [hoverIndex, setHoverIndex] = useState<number | null>(null);
  const [pinnedTime, setPinnedTime] = useState<string | null>(null);
  const [dragging, setDragging] = useState(false);
  const dragRef = useRef<{ pointerId: number; lastX: number; moved: boolean } | null>(null);
  const suppressClickRef = useRef(false);
  const wheelPanRef = useRef(0);
  const [expanded, setExpanded] = useState(false);
  const [chartWindow, setChartWindow] = useState<ChartWindow>({ size: DEFAULT_WINDOW, end: null });
  const dialogRef = useRef<HTMLDialogElement>(null);
  const chartSvgRef = useRef<SVGSVGElement>(null);
  const visible = useMemo(() => analysisMode ? bars : rangeBars(bars, range), [analysisMode, bars, range]);
  const end = Math.min(chartWindow.end ?? visible.length, visible.length);
  const count = Math.min(Math.max(1, Math.round(chartWindow.size)), visible.length);
  const analysisBars = visible.slice(Math.max(0, end - count), end);

  useEffect(() => {
    if (analysisMode) return;
    const dialog = dialogRef.current;
    if (!dialog) return;
    if (expanded && !dialog.open) dialog.showModal();
    if (!expanded && dialog.open) dialog.close();
  }, [analysisMode, expanded, loading, error, visible.length]);

  useEffect(() => {
    setChartWindow({ size: DEFAULT_WINDOW, end: null });
  }, [symbol]);

  useEffect(() => {
    if (!analysisMode) return;
    const svg = chartSvgRef.current;
    if (!svg) return;
    const handleWheel = (event: WheelEvent) => {
      event.preventDefault();
      if (Math.abs(event.deltaX) > Math.abs(event.deltaY)) {
        wheelPanRef.current += event.deltaX;
        const barsMoved = Math.trunc(wheelPanRef.current / 12);
        if (barsMoved !== 0) {
          onPanBars?.(barsMoved);
          wheelPanRef.current -= barsMoved * 12;
        }
        return;
      }
      const unit = event.deltaMode === 1 ? 30 : event.deltaMode === 2 ? 100 : 1;
      onWheelZoom?.(event.deltaY * unit, chartPointerRatio(event.clientX, svg.getBoundingClientRect()));
    };
    svg.addEventListener("wheel", handleWheel, { passive: false });
    return () => svg.removeEventListener("wheel", handleWheel);
  }, [analysisMode, onPanBars, onWheelZoom, visible.length]);

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
  const pinnedIndex = visible.findIndex((bar) => bar.time === pinnedTime);
  const selectedIndex = Math.min(hoverIndex ?? (pinnedIndex >= 0 ? pinnedIndex : visible.length - 1), visible.length - 1);
  const selected = visible[selectedIndex];
  const first = visible[0];
  const change = first.close ? (selected.close / first.close - 1) * 100 : 0;
  const candleChange = selected.open ? (selected.close / selected.open - 1) * 100 : 0;
  const gridPrices = [high, (high + low) / 2, low];
  const sessionSegments = visible.reduce<Array<{ kind: string; start: number; end: number }>>((segments, bar, index) => {
    const kind = sessionKind(bar.time);
    const last = segments[segments.length - 1];
    if (last?.kind === kind) last.end = index;
    else segments.push({ kind, start: index, end: index });
    return segments;
  }, []);

  function nearestIndex(clientX: number, bounds: DOMRect) {
    return Math.round(chartPointerRatio(clientX, bounds) * (visible.length - 1));
  }

  function handlePointerMove(event: React.PointerEvent<SVGSVGElement>) {
    const drag = dragRef.current;
    if (analysisMode && drag?.pointerId === event.pointerId) {
      const bounds = event.currentTarget.getBoundingClientRect();
      const pixelsPerBar = bounds.width * plotWidth / WIDTH / Math.max(1, visible.length - 1);
      const barsMoved = Math.trunc((event.clientX - drag.lastX) / pixelsPerBar);
      if (barsMoved !== 0) {
        onPanBars?.(-barsMoved);
        drag.lastX += barsMoved * pixelsPerBar;
        drag.moved = true;
      }
      setHoverIndex(null);
      return;
    }
    setHoverIndex(nearestIndex(event.clientX, event.currentTarget.getBoundingClientRect()));
  }

  function finishDrag(event: React.PointerEvent<SVGSVGElement>) {
    const drag = dragRef.current;
    if (!drag || drag.pointerId !== event.pointerId) return;
    if (event.currentTarget.hasPointerCapture(event.pointerId)) event.currentTarget.releasePointerCapture(event.pointerId);
    suppressClickRef.current = drag.moved;
    if (drag.moved) window.setTimeout(() => { suppressClickRef.current = false; }, 0);
    dragRef.current = null;
    setDragging(false);
  }

  function chooseChartStyle(nextStyle: ChartStyle) {
    setSavedChartStyle(nextStyle);
    window.localStorage.setItem("stock-chart-style", nextStyle);
    onDisplayStyleChange?.(nextStyle);
  }

  function openExpanded() {
    chooseChartStyle("candles");
    setChartWindow({ size: DEFAULT_WINDOW, end: null });
    setExpanded(true);
  }

  function panBy(bars: number) {
    setChartWindow((current) => {
      const currentCount = Math.min(Math.max(1, Math.round(current.size)), visible.length);
      const currentEnd = Math.min(current.end ?? visible.length, visible.length);
      const next = Math.max(currentCount, Math.min(visible.length, currentEnd + bars));
      return { ...current, end: next === visible.length ? null : next };
    });
  }

  function zoomAt(delta: number, anchor: number) {
    setChartWindow((current) => {
      const total = visible.length;
      if (total === 0) return current;
      const currentSize = Math.min(current.size, total);
      const currentCount = Math.min(Math.max(1, Math.round(currentSize)), total);
      const nextSize = Math.max(Math.min(MIN_WINDOW, total), Math.min(total, currentSize * Math.exp(Math.max(-300, Math.min(300, delta)) * .003)));
      const nextCount = Math.min(Math.max(1, Math.round(nextSize)), total);
      if (nextCount === currentCount) return { ...current, size: nextSize };
      const currentEnd = Math.min(current.end ?? total, total);
      const anchorIndex = currentEnd - currentCount + anchor * (currentCount - 1);
      const nextStart = Math.round(anchorIndex - anchor * (nextCount - 1));
      const nextEnd = Math.max(nextCount, Math.min(total, nextStart + nextCount));
      return { size: nextSize, end: nextEnd === total ? null : nextEnd };
    });
  }

  return <>
  <div className={`stock-chart ${analysisMode ? "analysis-chart" : ""}`}>
    <div className="stock-chart-toolbar">
      <div className="stock-chart-quote">
        <strong>{dollars(selected.close)}</strong>
        <span className={change >= 0 ? "positive" : "negative"}>{change >= 0 ? "+" : ""}{change.toFixed(2)}%</span>
        <small>{chartTime(selected.time)} ET · O {dollars(selected.open)} · H {dollars(selected.high)} · L {dollars(selected.low)} · C {dollars(selected.close)} · Vol {selected.volume.toLocaleString("en-US")}</small>
      </div>
      <div className="chart-controls">
        <div className="chart-ranges" aria-label="Chart display">
          {(["line", "candles"] as ChartStyle[]).map((option) => <button type="button" key={option} className={chartStyle === option ? "active" : ""} aria-pressed={chartStyle === option} onClick={() => chooseChartStyle(option)}>{option === "line" ? "Line" : "Candles"}</button>)}
        </div>
        {!analysisMode && <div className="chart-ranges" aria-label="Chart range">
          {(["1H", "4H", "Session"] as ChartRange[]).map((option) => <button type="button" key={option} className={range === option ? "active" : ""} onClick={() => { setRange(option); setHoverIndex(null); setChartWindow((current) => ({ ...current, end: null })); }}>{option}</button>)}
        </div>}
        {!analysisMode && <button type="button" className="chart-expand-button" onClick={openExpanded}>↗ Expand</button>}
      </div>
    </div>
    <div className={analysisMode ? "chart-inspect-scroll" : undefined}>
    <svg
      ref={chartSvgRef}
      viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
      role="img"
      aria-label={`${symbol} Alpaca ${chartStyle === "candles" ? "candlestick" : "line"} price and volume chart`}
      className={analysisMode ? `chart-inspect-canvas ${dragging ? "dragging" : ""}` : "chart-expand-canvas"}
      tabIndex={analysisMode ? 0 : undefined}
      onPointerDown={analysisMode ? (event) => {
        if (event.pointerType !== "mouse" || event.button !== 0) return;
        dragRef.current = { pointerId: event.pointerId, lastX: event.clientX, moved: false };
        event.currentTarget.setPointerCapture(event.pointerId);
        setDragging(true);
      } : undefined}
      onPointerMove={handlePointerMove}
      onPointerUp={analysisMode ? finishDrag : undefined}
      onPointerCancel={analysisMode ? finishDrag : undefined}
      onPointerLeave={() => setHoverIndex(null)}
      onClick={analysisMode ? (event) => {
        if (suppressClickRef.current) return;
        setPinnedTime(visible[nearestIndex(event.clientX, event.currentTarget.getBoundingClientRect())].time);
      } : openExpanded}
      onKeyDown={analysisMode ? (event) => {
        if (event.key !== "ArrowLeft" && event.key !== "ArrowRight") return;
        event.preventDefault();
        setPinnedTime(visible[Math.max(0, Math.min(visible.length - 1, selectedIndex + (event.key === "ArrowRight" ? 1 : -1)))].time);
        setHoverIndex(null);
      } : undefined}
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
    </div>
    {!analysisMode && <p className="chart-expand-hint">Click the chart to inspect individual candles ↗</p>}
    {analysisMode && <div className="chart-candle-details">
      <div><small>Selected candle</small><strong>{chartTime(selected.time)} ET</strong></div>
      <div><small>Open</small><strong>{dollars(selected.open)}</strong></div>
      <div><small>High</small><strong>{dollars(selected.high)}</strong></div>
      <div><small>Low</small><strong>{dollars(selected.low)}</strong></div>
      <div><small>Close</small><strong>{dollars(selected.close)}</strong></div>
      <div><small>Volume</small><strong>{selected.volume.toLocaleString("en-US")}</strong></div>
      <div><small>Candle move</small><strong className={candleChange >= 0 ? "positive" : "negative"}>{candleChange >= 0 ? "+" : ""}{candleChange.toFixed(2)}%</strong></div>
    </div>}
    <div className="stock-chart-legend"><span><i className="premarket-key" />Pre-market</span><span><i className="regular-key" />Regular market</span><span><i className="postmarket-key" />Post-market to 4:15 PM</span><span>Alpaca SIP · 1-minute bars</span></div>
  </div>
  {!analysisMode && <dialog ref={dialogRef} className="chart-dialog" aria-label={`${symbol} expanded market chart`} onClose={() => setExpanded(false)} onClick={(event) => { if (event.target === event.currentTarget) event.currentTarget.close(); }}>
    {expanded && <div className="chart-dialog-content">
      <header className="chart-dialog-header">
        <div><p className="eyebrow">Market chart · detailed view</p><h2>{symbol} <span>→ {symbol}x-demo</span></h2><p>Scroll to zoom, drag to move through candles, or click one to pin its values. Swipe sideways on touch screens.</p></div>
        <button type="button" className="chart-close-button" onClick={() => dialogRef.current?.close()} aria-label="Close expanded chart">×</button>
      </header>
      <div className="chart-window-controls" aria-label="Chart zoom and navigation">
        <div className="chart-ranges" aria-label="Expanded chart range">
          {(["1H", "4H", "Session"] as ChartRange[]).map((option) => <button type="button" key={option} className={range === option ? "active" : ""} aria-pressed={range === option} onClick={() => { setRange(option); setChartWindow((current) => ({ ...current, end: null })); }}>{option}</button>)}
        </div>
        <span className="chart-window-label">{analysisBars.length > 0 ? `${chartTime(analysisBars[0].time)}–${chartTime(analysisBars[analysisBars.length - 1].time)} ET · ${analysisBars.length} candles` : "Waiting for bars"}</span>
        <div className="chart-window-buttons">
          <button type="button" onClick={() => panBy(-Math.max(1, Math.round(count / 2)))} disabled={end <= count} aria-label="Show earlier candles">← Earlier</button>
          <button type="button" onClick={() => panBy(Math.max(1, Math.round(count / 2)))} disabled={end >= visible.length} aria-label="Show later candles">Later →</button>
          <button type="button" onClick={() => zoomAt(-240, .5)} disabled={count <= Math.min(MIN_WINDOW, visible.length)} aria-label="Zoom in on candles">+ Zoom in</button>
          <button type="button" onClick={() => zoomAt(240, .5)} disabled={count >= visible.length} aria-label="Zoom out to more candles">− Zoom out</button>
          <button type="button" onClick={() => setChartWindow({ size: DEFAULT_WINDOW, end: null })}>Latest</button>
        </div>
      </div>
      <StockChart key={`${symbol}-${range}`} symbol={symbol} bars={analysisBars} loading={loading} error={error} analysisMode displayStyle={chartStyle} onDisplayStyleChange={chooseChartStyle} onWheelZoom={zoomAt} onPanBars={panBy} />
    </div>}
  </dialog>}
  </>;
}
