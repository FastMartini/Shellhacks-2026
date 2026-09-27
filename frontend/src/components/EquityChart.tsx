interface EquityPoint { t: string; value: number }

export function EquityChart({ points }: { points: EquityPoint[] }) {
  if (points.length < 2) return <div className="chart-empty"><b>Your account history will appear here</b><span>Get demo dollars and complete a trade to begin the chart.</span></div>;
  const values = points.map((point) => point.value);
  const min = Math.min(...values); const max = Math.max(...values); const spread = max - min || 1;
  const coordinates = points.map((point, index) => `${(index / (points.length - 1)) * 100},${92 - ((point.value - min) / spread) * 76}`).join(" ");
  const money = (value: number) => value.toLocaleString("en-US", { style: "currency", currency: "USD" });
  return <div className="equity-chart"><div className="chart-scale"><span>{money(max)}</span><span>{money(min)}</span></div><svg viewBox="0 0 100 100" preserveAspectRatio="none" role="img" aria-label="Account value over replay time"><defs><linearGradient id="equity-fill" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stopColor="#6cf2a6" stopOpacity=".28"/><stop offset="1" stopColor="#6cf2a6" stopOpacity="0"/></linearGradient></defs><polygon points={`0,100 ${coordinates} 100,100`} fill="url(#equity-fill)"/><polyline points={coordinates} fill="none" stroke="#6cf2a6" strokeWidth="1.5" vectorEffect="non-scaling-stroke"/></svg></div>;
}
