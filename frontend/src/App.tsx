import { useWallet } from "@solana/wallet-adapter-react";
import { WalletMultiButton } from "@solana/wallet-adapter-react-ui";
import { Transaction } from "@solana/web3.js";
import { useCallback, useEffect, useMemo, useState } from "react";

import { ApiRequestError, apiRequest } from "./api/client";
import { submitSignedTrade } from "./api/trade";
import type { Alert, FaucetResponse, Portfolio, PriceBar, PriceQuote, ReplayState, TradeQuote, TransactionRow } from "./api/types";
import { EquityChart } from "./components/EquityChart";
import { StatCard } from "./components/StatCard";
import { StockChart } from "./components/StockChart";
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

function marketSession(value?: string) {
  if (!value) return "Loading session";
  const parts = new Intl.DateTimeFormat("en-US", {
    hour: "2-digit", minute: "2-digit", hourCycle: "h23", timeZone: "America/New_York",
  }).formatToParts(new Date(value));
  const hour = Number(parts.find((part) => part.type === "hour")?.value ?? 0);
  const minute = Number(parts.find((part) => part.type === "minute")?.value ?? 0);
  const minutes = hour * 60 + minute;
  if (minutes < 9 * 60 + 30) return "Pre-market";
  if (minutes < 16 * 60) return "Regular market";
  if (minutes <= 16 * 60 + 15) return "Post-market";
  return "Market closed";
}

function decodeBase64(value: string) {
  return Uint8Array.from(window.atob(value), (character) => character.charCodeAt(0));
}

function encodeBase64(value: Uint8Array) {
  let binary = "";
  for (const byte of value) binary += String.fromCharCode(byte);
  return window.btoa(binary);
}

export default function App() {
  const { publicKey, connected, signTransaction } = useWallet();
  const wallet = publicKey?.toBase58();
  const [view, setView] = useState<"dashboard" | "scanner">(() => window.location.hash === "#scanner" ? "scanner" : "dashboard");
  const [replay, setReplay] = useState<ReplayState | null>(null);
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [prices, setPrices] = useState<PriceQuote[]>([]);
  const [chart, setChart] = useState<{ symbol: string; bars: PriceBar[] } | null>(null);
  const [chartError, setChartError] = useState<string | null>(null);
  const [portfolio, setPortfolio] = useState<Portfolio>(EMPTY_PORTFOLIO);
  const [portfolioWallet, setPortfolioWallet] = useState<string | null>(null);
  const [transactions, setTransactions] = useState<TransactionRow[]>([]);
  const [selectedSymbol, setSelectedSymbol] = useState("AKAM");
  const [amount, setAmount] = useState("");
  const [side, setSide] = useState<"buy" | "sell">("buy");
  const [loading, setLoading] = useState(true);
  const [working, setWorking] = useState(false);
  const [vaultAction, setVaultAction] = useState<"faucet" | "quote" | "sign" | "submit" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [vaultFeedback, setVaultFeedback] = useState<{ kind: "success" | "error"; message: string } | null>(null);

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
    if (view !== "scanner" || !replay) return;
    const controller = new AbortController();
    setChartError(null);
    void apiRequest<PriceBar[]>(`/prices/${encodeURIComponent(selectedSymbol)}/history`, { signal: controller.signal })
      .then((bars) => setChart({ symbol: selectedSymbol, bars }))
      .catch((requestError: unknown) => {
        if (requestError instanceof DOMException && requestError.name === "AbortError") return;
        setChartError(requestError instanceof Error ? requestError.message : "Could not load the price chart.");
      });
    return () => controller.abort();
  }, [replay, selectedSymbol, view]);

  const loadPortfolio = useCallback(async () => {
    if (!wallet) { setPortfolio(EMPTY_PORTFOLIO); setTransactions([]); setPortfolioWallet(null); return; }
    try {
      const [nextPortfolio, nextTransactions] = await Promise.all([
      apiRequest<Portfolio>(`/portfolio?wallet=${encodeURIComponent(wallet)}`),
      apiRequest<TransactionRow[]>(`/transactions?wallet=${encodeURIComponent(wallet)}`),
      ]);
      setPortfolio(nextPortfolio); setTransactions(nextTransactions);
      setPortfolioWallet(wallet);
      return nextPortfolio;
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Could not load the portfolio.");
    }
  }, [wallet]);

  useEffect(() => {
    setPortfolioWallet(null);
    if (!wallet) { setPortfolio(EMPTY_PORTFOLIO); setTransactions([]); return; }
    void loadPortfolio();
    const timer = window.setInterval(() => void loadPortfolio(), 2_000);
    return () => window.clearInterval(timer);
  }, [loadPortfolio, wallet]);

  const selectedAlert = alerts.find((alert) => alert.symbol === selectedSymbol);
  const selectedPrice = prices.find((price) => price.symbol === selectedSymbol);
  const selectedHolding = portfolio.holdings.find((holding) => holding.symbol === selectedSymbol);
  const parsedAmount = Number(amount);
  const estimatedShares = side === "buy" && selectedPrice && parsedAmount > 0 ? parsedAmount / selectedPrice.price : null;
  const estimatedValue = side === "sell" && selectedPrice && parsedAmount > 0 ? parsedAmount * selectedPrice.price : null;
  const visibleAlerts = useMemo(() => [...alerts].sort((a, b) => b.time.localeCompare(a.time)), [alerts]);
  const portfolioReady = wallet != null && portfolioWallet === wallet;
  const hasValidAmount = Number.isFinite(parsedAmount) && parsedAmount > 0;
  const hasTradeBalance = side === "buy" ? portfolio.cash >= parsedAmount : (selectedHolding?.qty ?? 0) >= parsedAmount;
  const canTrade = Boolean(wallet && signTransaction && selectedPrice && portfolioReady && hasValidAmount && hasTradeBalance);

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

  async function getDemoDollars() {
    if (!wallet) return;
    setVaultAction("faucet"); setVaultFeedback(null);
    try {
      const depositedBefore = portfolio.deposited;
      const result = await apiRequest<FaucetResponse>("/faucet", {
        method: "POST",
        body: JSON.stringify({ wallet }),
      });
      const refreshedPortfolio = await loadPortfolio();
      if (!refreshedPortfolio || refreshedPortfolio.deposited <= depositedBefore) {
        throw new Error("The faucet responded, but the ledger balance did not update because the vault backend is still using its stub route.");
      }
      setVaultFeedback({ kind: "success", message: `${money(result.usd_amount)} in demo dollars was added to your account.` });
    } catch (requestError) {
      setVaultFeedback({ kind: "error", message: requestError instanceof Error ? requestError.message : "Could not get demo dollars." });
    } finally { setVaultAction(null); }
  }

  async function signAndSubmitTrade(retryExpired = true): Promise<TransactionRow> {
    if (!wallet || !signTransaction) throw new Error("Connect Phantom before trading.");
    setVaultAction("quote");
    const quote = await apiRequest<TradeQuote>("/trade/quote", {
      method: "POST",
      body: JSON.stringify({
        wallet,
        symbol: selectedSymbol,
        side,
        ...(side === "buy" ? { usd_amount: parsedAmount } : { qty: parsedAmount }),
      }),
    });

    setVaultAction("sign");
    const transaction = Transaction.from(decodeBase64(quote.tx_base64));
    const signedTransaction = await signTransaction(transaction);
    const signedTxBase64 = encodeBase64(signedTransaction.serialize({ requireAllSignatures: false, verifySignatures: false }));

    setVaultAction("submit");
    try {
      return await submitSignedTrade(quote.quote_id, signedTxBase64);
    } catch (requestError) {
      // Nothing changed on-chain: re-quote and sign once more.
      if (retryExpired && requestError instanceof ApiRequestError && (requestError.code === "quote_expired" || requestError.code === "tx_failed")) {
        return signAndSubmitTrade(false);
      }
      throw requestError;
    }
  }

  async function submitTrade() {
    if (!canTrade) return;
    setVaultFeedback(null);
    try {
      const transaction = await signAndSubmitTrade();
      setAmount("");
      await loadPortfolio();
      setVaultFeedback({ kind: "success", message: `${transaction.side === "buy" ? "Bought" : "Sold"} ${transaction.qty.toFixed(6)} ${transaction.symbol} shares on Solana devnet.` });
    } catch (requestError) {
      setVaultFeedback({ kind: "error", message: requestError instanceof Error ? requestError.message : "The trade could not be completed." });
    } finally { setVaultAction(null); }
  }

  function tradeButtonLabel() {
    if (vaultAction === "quote") return "Preparing quote…";
    if (vaultAction === "sign") return "Confirm in Phantom…";
    if (vaultAction === "submit") return "Confirming on Solana…";
    if (!connected) return "Connect wallet to trade";
    if (!hasValidAmount) return side === "buy" ? "Enter a dUSD amount" : "Enter shares to sell";
    if (!hasTradeBalance) return side === "buy" ? "Get demo dollars first" : `Only ${(selectedHolding?.qty ?? 0).toFixed(6)} shares available`;
    return `${side === "buy" ? "Buy" : "Sell"} ${selectedSymbol}`;
  }

  const canResetTimer = connected && portfolioReady && replay != null && portfolio.deposited === 0 && new Date(replay.sim_time).getTime() > REPLAY_START_MS;

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
      {vaultFeedback && <div className={`vault-feedback ${vaultFeedback.kind}`} role={vaultFeedback.kind === "error" ? "alert" : "status"}><span>{vaultFeedback.message}</span><button aria-label="Dismiss message" onClick={() => setVaultFeedback(null)}>×</button></div>}

      {view === "scanner" ? <>
        <section className="hero">
          <div><p className="eyebrow">Alpaca SIP market replay</p><h1>Trade the signal.<br />Understand the move.</h1><p className="lede">Large-cap momentum alerts backed by real Friday prices from pre-market through 4:15 PM ET, relative volume, and company news.</p><div className="rule-pills"><span>4:00 AM–4:15 PM ET</span><span>≥ 3% move</span><span>≥ 2× RVOL</span><span>News ≤ 24h</span></div></div>
          <div className="replay-card">
            <div><span className={replay?.running ? "live-dot running" : "live-dot"} /> {replay?.running ? "Replay running" : "Replay paused"}<span className="session-badge">{marketSession(replay?.sim_time)}</span></div>
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
            <div className="segmented"><button className={side === "buy" ? "active" : ""} onClick={() => { setSide("buy"); setAmount(""); }}>Buy</button><button className={side === "sell" ? "active sell" : ""} onClick={() => { setSide("sell"); setAmount(""); }}>Sell</button></div>
            <label>{side === "buy" ? "Amount in dUSD" : "Shares to sell"}<input inputMode="decimal" min="0" value={amount} onChange={(event) => setAmount(event.target.value)} placeholder="0.00" /></label>
            <div className="quote-row"><span>{side === "buy" ? "Estimated shares" : "Estimated value"}</span><span>{side === "buy" ? (estimatedShares ? estimatedShares.toFixed(6) : "—") : (estimatedValue ? money(estimatedValue) : "—")}</span></div>
            <button className="primary" disabled={vaultAction != null || !canTrade} onClick={() => void submitTrade()}>{tradeButtonLabel()}</button>
            <small className="disclaimer">Market data is real. Trades will use devnet test tokens with no monetary value.</small>
          </aside>
        </section>

        <section className="panel stock-chart-panel" aria-label={`${selectedSymbol} trading chart`}>
          <div className="panel-heading stock-chart-heading">
            <div><p className="eyebrow">Underlying market chart</p><h2>{selectedSymbol} <span>→ {selectedSymbol}x-demo</span></h2></div>
            <div className="chart-current"><strong>{selectedPrice ? money(selectedPrice.price) : "—"}</strong><small className={selectedPrice && selectedPrice.change_pct < 0 ? "negative" : "positive"}>{selectedPrice ? signed(selectedPrice.change_pct, "% vs. close") : "Waiting for price"}</small></div>
          </div>
          <StockChart symbol={selectedSymbol} bars={chart?.symbol === selectedSymbol ? chart.bars : []} loading={chart?.symbol !== selectedSymbol && chartError == null} error={chartError} />
        </section>

        <section className="market-strip" aria-label="Replay market prices">
          <div className="market-heading"><div><p className="eyebrow">Alpaca replay prices</p><h2>Tracked market</h2></div><span>{prices.length} symbols</span></div>
          <div className="price-grid">{prices.map((price) => <button key={price.symbol} className={selectedSymbol === price.symbol ? "active" : ""} onClick={() => setSelectedSymbol(price.symbol)}><b>{price.symbol}</b><span>{money(price.price)}</span><small className={price.change_pct >= 0 ? "positive" : "negative"}>{signed(price.change_pct, "%")}</small></button>)}</div>
        </section>
      </> : <>
        <section className="portfolio-hero">
          <div><p className="eyebrow">Your account</p><h1>{connected ? "Portfolio overview" : "Your investing story starts here."}</h1><p className="lede">Track demo-dollar cash, tokenized stock positions, and account performance throughout the replay.</p></div>
          <div className="account-value"><span>Total account value</span><strong>{money(portfolio.total_value)}</strong><small className={portfolio.stats.total_pl >= 0 ? "positive" : "negative"}>{signed(portfolio.stats.total_pl, " total return")}</small><button className="primary faucet-button" disabled={!connected || !portfolioReady || portfolio.deposited > 0 || vaultAction != null} onClick={() => void getDemoDollars()}>{vaultAction === "faucet" ? "Adding demo dollars…" : !connected ? "Connect wallet first" : portfolio.deposited > 0 ? `${money(portfolio.deposited)} in demo dollars added` : "Get 1,000 demo dollars"}</button></div>
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
