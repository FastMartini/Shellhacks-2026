import { useWallet } from "@solana/wallet-adapter-react";
import { WalletMultiButton } from "@solana/wallet-adapter-react-ui";
import { useCallback, useEffect, useMemo, useState } from "react";

import { apiRequest } from "./api/client";
import type { Alert, Portfolio, PriceQuote, ReplayState, TransactionRow } from "./api/types";
import { EquityChart } from "./components/EquityChart";
import { StatCard } from "./components/StatCard";
import { TransactionTable } from "./components/TransactionTable";

const EMPTY_PORTFOLIO: Portfolio = {
  cash: 0, holdings: [], total_value: 0, deposited: 0,
  stats: { total_pl: 0, total_pl_pct: 0, avg_win: null, avg_loss: null, trade_count: 0, win_count: 0, loss_count: 0 },
  equity_curve: [],
};

const REPLAY_START_MS = new Date("2026-09-25T09:25:00-04:00").getTime();

function money(value: number) {
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(value);
}

function signed(value: number, suffix = "") {
  return `${value >= 0 ? "+" : ""}${value.toFixed(2)}${suffix}`;
}

function marketTime(value?: string) {
  if (!value) return "—";
  return new Intl.DateTimeFormat("en-US", { hour: "numeric", minute: "2-digit", timeZone: "America/New_York" }).format(new Date(value));
}

export default function App() {
  const { publicKey, connected } = useWallet();
  const wallet = publicKey?.toBase58();
  const [view, setView] = useState<"dashboard" | "scanner">(() => window.location.hash === "#scanner" ? "scanner" : "dashboard");
  const [replay, setReplay] = useState<ReplayState | null>(null);
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [prices, setPrices] = useState<PriceQuote[]>([]);
  const [portfolio, setPortfolio] = useState<Portfolio>(EMPTY_PORTFOLIO);
  const [transactions, setTransactions] = useState<TransactionRow[]>([]);
  const [selectedSymbol, setSelectedSymbol] = useState("AKAM");
  const [amount, setAmount] = useState("");
  const [side, setSide] = useState<"buy" | "sell">("buy");
  const [loading, setLoading] = useState(true);
  const [working, setWorking] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const loadMarket = useCallback(async (quiet = false) => {
    if (!quiet) setLoading(true);
    try {
      const [nextReplay, nextAlerts, nextPrices] = await Promise.all([
        apiRequest<ReplayState>("/replay/state"),
        apiRequest<Alert[]>("/alerts"),
        apiRequest<PriceQuote[]>("/prices"),
      ]);
      setReplay(nextReplay); setAlerts(nextAlerts); setPrices(nextPrices); setError(null);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "The API is unavailable.");
    } finally {
      if (!quiet) setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadMarket();
    const timer = window.setInterval(() => void loadMarket(true), 2_000);
    return () => window.clearInterval(timer);
  }, [loadMarket]);

  useEffect(() => {
    if (!wallet) { setPortfolio(EMPTY_PORTFOLIO); setTransactions([]); return; }
    const loadPortfolio = () => Promise.all([
      apiRequest<Portfolio>(`/portfolio?wallet=${encodeURIComponent(wallet)}`),
      apiRequest<TransactionRow[]>(`/transactions?wallet=${encodeURIComponent(wallet)}`),
    ]).then(([nextPortfolio, nextTransactions]) => { setPortfolio(nextPortfolio); setTransactions(nextTransactions); })
      .catch((requestError: unknown) => setError(requestError instanceof Error ? requestError.message : "Could not load the portfolio."));
    void loadPortfolio();
    const timer = window.setInterval(loadPortfolio, 2_000);
    return () => window.clearInterval(timer);
  }, [wallet]);

  const selectedAlert = alerts.find((alert) => alert.symbol === selectedSymbol);
  const selectedPrice = prices.find((price) => price.symbol === selectedSymbol);
  const parsedAmount = Number(amount);
  const estimatedShares = selectedPrice && parsedAmount > 0 ? parsedAmount / selectedPrice.price : null;
  const visibleAlerts = useMemo(() => [...alerts].sort((a, b) => b.time.localeCompare(a.time)), [alerts]);

  function navigate(nextView: "dashboard" | "scanner") {
    setView(nextView);
    window.history.replaceState(null, "", nextView === "scanner" ? "#scanner" : "#dashboard");
  }

  async function controlReplay(action: "start" | "pause", speed?: number) {
    setWorking(true); setNotice(null);
    try {
      setReplay(await apiRequest<ReplayState>("/replay/control", { method: "POST", body: JSON.stringify({ action, speed }) }));
      await loadMarket(true);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Could not control the replay.");
    } finally { setWorking(false); }
  }

  async function jumpToNextAlert() {
    setWorking(true); setNotice(null);
    try {
      setReplay(await apiRequest<ReplayState>("/replay/next-alert", { method: "POST" }));
      await loadMarket(true);
    } catch (requestError) {
      setNotice(requestError instanceof Error ? requestError.message : "No later alert is available.");
    } finally { setWorking(false); }
  }

  async function resetReplayTimer() {
    setWorking(true); setNotice(null);
    try {
      setReplay(await apiRequest<ReplayState>("/replay/control", {
        method: "POST",
        body: JSON.stringify({ action: "seek", to: new Date(REPLAY_START_MS).toISOString() }),
      }));
      await loadMarket(true);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Could not reset the replay timer.");
    } finally { setWorking(false); }
  }

  const canResetTimer = replay != null && portfolio.deposited === 0 && new Date(replay.sim_time).getTime() > REPLAY_START_MS;

  return (
    <main>
      <header className="topbar">
        <a className="brand" href="#dashboard" onClick={(event) => { event.preventDefault(); navigate("dashboard"); }}><span className="brand-mark">M</span><span>Momentum</span></a>
        <nav className="main-nav" aria-label="Primary navigation">
          <button className={view === "dashboard" ? "active" : ""} onClick={() => navigate("dashboard")}>Dashboard</button>
          <button className={view === "scanner" ? "active" : ""} onClick={() => navigate("scanner")}>Scanner</button>
        </nav>
        <div className="network-pill"><i /> Solana Devnet</div>
        <WalletMultiButton />
      </header>

      {error && <div className="error-banner" role="alert"><span><b>Backend unavailable.</b> {error}</span><button onClick={() => void loadMarket()}>Retry</button></div>}

      {view === "scanner" ? <>
        <section className="hero">
          <div><p className="eyebrow">Alpaca SIP market replay</p><h1>Trade the signal.<br />Understand the move.</h1><p className="lede">Large-cap momentum alerts backed by real Friday prices, relative volume, and company news.</p><div className="rule-pills"><span>≥ 3% move</span><span>≥ 2× RVOL</span><span>News ≤ 24h</span></div></div>
          <div className="replay-card">
            <div><span className={replay?.running ? "live-dot running" : "live-dot"} /> {replay?.running ? "Replay running" : "Replay paused"}</div>
            <strong>{marketTime(replay?.sim_time)} ET</strong>
            <div className="replay-meta"><span>Friday, Sep 25</span><span>{replay?.speed ?? 30}× speed</span></div>
            <label className="speed-control">Replay speed<select value={replay?.speed ?? 30} disabled={working} onChange={(event) => void controlReplay(replay?.running ? "start" : "pause", Number(event.target.value))}><option value="1">1×</option><option value="10">10×</option><option value="30">30×</option><option value="60">60×</option></select></label>
            <div className="replay-actions"><button className="reset-button" title={portfolio.deposited > 0 ? "Reset is unavailable after demo dollars are deposited" : "Return the replay clock to 9:25 AM"} disabled={working || loading || !canResetTimer} onClick={() => void resetReplayTimer()}>↺ Reset timer</button><button className="play-button" disabled={working || loading} onClick={() => void controlReplay(replay?.running ? "pause" : "start")}>{working ? "Updating…" : replay?.running ? "Pause replay" : "Start replay"}</button></div>
          </div>
        </section>

        <section className="workspace">
          <div className="panel alerts-panel">
            <div className="panel-heading"><div><p className="eyebrow">Scanner</p><h2>Momentum alerts</h2></div><button className="text-button" disabled={working} onClick={() => void jumpToNextAlert()}>Jump to next →</button></div>
            {notice && <p className="notice">{notice}</p>}
            <div className="alert-list">
              {loading ? <div className="empty-state">Loading scanner…</div> : visibleAlerts.length === 0 ? <div className="empty-state"><b>No alerts revealed yet</b><span>Start the replay or jump directly to the first signal.</span></div> : visibleAlerts.map((alert) => (
                <button className={`alert-row ${selectedSymbol === alert.symbol ? "selected" : ""}`} key={alert.id} onClick={() => setSelectedSymbol(alert.symbol)}>
                  <span className="ticker">{alert.symbol}<small>{alert.symbol}x-demo</small></span><span><b>{signed(alert.change_pct, "%")}</b><small>Price move</small></span><span><b>{alert.rvol.toFixed(1)}×</b><small>Rel. volume</small></span><time>{marketTime(alert.time)}</time>
                </button>
              ))}
            </div>
            {selectedAlert?.headline && <a className="headline" href={selectedAlert.headline_url ?? "#"} target="_blank" rel="noreferrer"><span>Qualifying catalyst</span>{selectedAlert.headline}<b>↗</b></a>}
          </div>

          <aside className="panel trade-panel">
            <p className="eyebrow">Trade ticket preview</p>
            <div className="ticket-title"><div><h2>{selectedSymbol}</h2><small>{selectedSymbol}x-demo</small></div><span>{selectedPrice ? money(selectedPrice.price) : "—"}</span></div>
            <div className={selectedPrice && selectedPrice.change_pct < 0 ? "price-change negative" : "price-change"}>{selectedPrice ? `${signed(selectedPrice.change_pct, "%")} vs. previous close` : "Waiting for price"}</div>
            <div className="segmented"><button className={side === "buy" ? "active" : ""} onClick={() => setSide("buy")}>Buy</button><button className={side === "sell" ? "active sell" : ""} onClick={() => setSide("sell")}>Sell</button></div>
            <label>Amount in dUSD<input inputMode="decimal" min="0" value={amount} onChange={(event) => setAmount(event.target.value)} placeholder="0.00" /></label>
            <div className="quote-row"><span>Estimated shares</span><span>{estimatedShares ? estimatedShares.toFixed(6) : "—"}</span></div>
            <button className="primary" disabled>{!connected ? "Connect wallet to trade" : "Vault integration is next"}</button>
            <small className="disclaimer">Market data is real. Trades will use devnet test tokens with no monetary value.</small>
          </aside>
        </section>

        <section className="market-strip" aria-label="Replay market prices">
          <div className="market-heading"><div><p className="eyebrow">Alpaca replay prices</p><h2>Tracked market</h2></div><span>{prices.length} symbols</span></div>
          <div className="price-grid">{prices.map((price) => <button key={price.symbol} className={selectedSymbol === price.symbol ? "active" : ""} onClick={() => setSelectedSymbol(price.symbol)}><b>{price.symbol}</b><span>{money(price.price)}</span><small className={price.change_pct >= 0 ? "positive" : "negative"}>{signed(price.change_pct, "%")}</small></button>)}</div>
        </section>
      </> : <>
        <section className="portfolio-hero">
          <div><p className="eyebrow">Your account</p><h1>{connected ? "Portfolio overview" : "Your investing story starts here."}</h1><p className="lede">Track demo-dollar cash, tokenized stock positions, and account performance throughout the replay.</p></div>
          <div className="account-value"><span>Total account value</span><strong>{money(portfolio.total_value)}</strong><small className={portfolio.stats.total_pl >= 0 ? "positive" : "negative"}>{signed(portfolio.stats.total_pl, " total return")}</small></div>
        </section>
        <section className="stats-grid">
          <StatCard label="Portfolio value" value={money(portfolio.total_value)} detail={connected ? "Connected account" : "Connect Phantom to load"} />
          <StatCard label="Total return" value={`${portfolio.stats.total_pl >= 0 ? "+" : ""}${money(portfolio.stats.total_pl)}`} detail={signed(portfolio.stats.total_pl_pct, "% all time")} tone={portfolio.stats.total_pl > 0 ? "positive" : portfolio.stats.total_pl < 0 ? "negative" : undefined} />
          <StatCard label="Available cash" value={money(portfolio.cash)} detail="dUSD balance" />
          <StatCard label="Trades" value={String(portfolio.stats.trade_count)} detail={`${portfolio.stats.win_count} wins · ${portfolio.stats.loss_count} losses`} />
        </section>
        <section className="portfolio-grid">
          <article className="panel chart-panel"><div className="panel-heading"><div><p className="eyebrow">Performance</p><h2>Account value</h2></div><span className="range-pill">Replay day</span></div><EquityChart points={portfolio.equity_curve} /></article>
          <article className="panel holdings-panel"><div className="panel-heading"><div><p className="eyebrow">Assets</p><h2>Holdings</h2></div><span>{portfolio.holdings.length} positions</span></div>{portfolio.holdings.length === 0 ? <div className="empty-state"><b>No positions yet</b><span>Open the scanner to explore the first signal.</span><button className="text-button" onClick={() => navigate("scanner")}>Open scanner →</button></div> : <div className="holdings-list">{portfolio.holdings.map((holding) => <div key={holding.symbol}><span className="asset-icon">{holding.symbol[0]}</span><span><b>{holding.symbol}</b><small>{holding.qty.toFixed(6)} shares</small></span><span><b>{money(holding.market_value)}</b><small className={holding.unrealized_pl >= 0 ? "positive" : "negative"}>{signed(holding.unrealized_pl)}</small></span></div>)}</div>}</article>
        </section>
        <TransactionTable transactions={transactions} />
      </>}
    </main>
  );
}
