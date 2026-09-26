import { useState } from "react";

import "./styles.css";

type Transaction = {
  id: number;
  time: string;
  symbol: string;
  side: "Buy" | "Sell";
  shares: string;
  amount: string;
  status: "Confirmed" | "Pending";
};

type PhantomProvider = {
  connect: () => Promise<{ publicKey: { toString: () => string } }>;
};

declare global {
  interface Window {
    phantom?: { solana?: PhantomProvider };
  }
}

const demoTransactions: Transaction[] = [
  { id: 1, time: "9:31 AM", symbol: "AKAMx", side: "Buy", shares: "2.500000", amount: "$300.00", status: "Confirmed" },
  { id: 2, time: "9:45 AM", symbol: "AKAMx", side: "Sell", shares: "2.500000", amount: "$311.25", status: "Confirmed" },
  { id: 3, time: "10:08 AM", symbol: "MSFTx", side: "Buy", shares: "0.791922", amount: "$400.00", status: "Confirmed" },
];

function shortenAddress(address: string) {
  return `${address.slice(0, 4)}…${address.slice(-4)}`;
}

function StatusPill({ children, tone = "default" }: { children: React.ReactNode; tone?: "default" | "success" }) {
  return <span className={`status-pill ${tone}`}>{children}</span>;
}

function CheckMark() {
  return <span className="check-mark" aria-hidden="true">✓</span>;
}

function VaultSetup({ isReady, onGenerate }: { isReady: boolean; onGenerate: () => void }) {
  return (
    <section className="card vault-card" aria-labelledby="vault-heading">
      <div className="card-heading">
        <div>
          <p className="eyebrow">Setup step · target 4:45 PM</p>
          <h2 id="vault-heading">Mints + Vault</h2>
        </div>
        <StatusPill tone={isReady ? "success" : "default"}>{isReady ? "Ready" : "Required"}</StatusPill>
      </div>
      <p className="card-copy">Create the devnet vault first, then use it as the mint authority for demo dollars and stock tokens.</p>
      <div className="setup-checklist">
        <div><CheckMark /><span><strong>1 dUSD</strong> demo-dollar mint</span></div>
        <div><CheckMark /><span><strong>19 stock mints</strong> with 6 decimals</span></div>
        <div><CheckMark /><span><strong>Vault keypair</strong> funded for devnet fees</span></div>
      </div>
      <button className="primary-button" onClick={onGenerate} disabled={isReady}>
        {isReady ? "Vault keypair created" : "Create vault keypair"}
        {!isReady && <span aria-hidden="true">→</span>}
      </button>
    </section>
  );
}

function WalletPanel({ wallet, isConnecting, message, onConnect }: { wallet: string | null; isConnecting: boolean; message: string | null; onConnect: () => void }) {
  return (
    <section className="card wallet-card" aria-labelledby="wallet-heading">
      <div className="card-heading">
        <div><p className="eyebrow">Demo wallet</p><h2 id="wallet-heading">Ready to trade</h2></div>
        <span className="solana-mark" aria-label="Solana devnet">≋</span>
      </div>
      <p className="card-copy">Connect Phantom to receive dUSD and sign trades the vault co-signs on devnet.</p>
      {wallet ? (
        <div className="connected-wallet"><span className="wallet-dot" />{shortenAddress(wallet)}<StatusPill tone="success">Connected</StatusPill></div>
      ) : (
        <button className="wallet-button" onClick={onConnect} disabled={isConnecting}><span className="phantom-icon" aria-hidden="true">◒</span>{isConnecting ? "Connecting…" : "Connect Phantom"}</button>
      )}
      {message && <p className="wallet-message" role="status">{message}</p>}
    </section>
  );
}

function TransactionTable({ transactions }: { transactions: Transaction[] }) {
  return (
    <section className="card transaction-card" aria-labelledby="transactions-heading">
      <div className="card-heading transaction-heading"><div><p className="eyebrow">Demo ledger</p><h2 id="transactions-heading">Transactions</h2></div><StatusPill>{transactions.length} recorded</StatusPill></div>
      <div className="table-wrap"><table><thead><tr><th>Time</th><th>Asset</th><th>Type</th><th>Shares</th><th>Value</th><th>Status</th></tr></thead><tbody>
        {transactions.map((transaction) => <tr key={transaction.id}><td>{transaction.time}</td><td className="asset-cell"><span>{transaction.symbol.slice(0, -1)}</span><small>x</small></td><td><span className={`trade-type ${transaction.side.toLowerCase()}`}>{transaction.side}</span></td><td>{transaction.shares}</td><td>{transaction.amount}</td><td><span className="confirmed"><i />{transaction.status}</span></td></tr>)}
      </tbody></table></div>
      <p className="table-note">Transactions are recorded after the vault confirms on Solana devnet.</p>
    </section>
  );
}

function App() {
  const [vaultReady, setVaultReady] = useState(false);
  const [wallet, setWallet] = useState<string | null>(null);
  const [isConnecting, setIsConnecting] = useState(false);
  const [walletMessage, setWalletMessage] = useState<string | null>(null);

  async function connectWallet() {
    const provider = window.phantom?.solana;
    if (!provider) { setWalletMessage("Install or unlock Phantom, then try again."); return; }
    setIsConnecting(true); setWalletMessage(null);
    try { const response = await provider.connect(); setWallet(response.publicKey.toString()); }
    catch { setWalletMessage("Wallet connection was cancelled. Try again when you are ready."); }
    finally { setIsConnecting(false); }
  }

  return (
    <main className="app-shell">
      <header className="topbar"><a className="brand" href="#top" aria-label="ShellHacks home"><span className="brand-mark">S</span><span>shell<span>trade</span></span></a><span className="network-badge"><i />Solana devnet</span></header>
      <div className="intro" id="top"><p className="eyebrow">Demo environment</p><h1>Set up the trading vault.</h1><p>One secure vault powers the demo dollar faucet and every tokenized stock trade.</p></div>
      <div className="flow" aria-label="Demo setup progress"><div className="flow-step active"><span>1</span><strong>Mints + Vault</strong></div><div className={vaultReady ? "flow-line active" : "flow-line"} /><div className={vaultReady ? "flow-step active" : "flow-step"}><span>2</span><strong>Connect wallet</strong></div><div className="flow-line" /><div className="flow-step"><span>3</span><strong>Trade</strong></div></div>
      <div className="content-grid"><VaultSetup isReady={vaultReady} onGenerate={() => setVaultReady(true)} />{vaultReady && <WalletPanel wallet={wallet} isConnecting={isConnecting} message={walletMessage} onConnect={connectWallet} />}</div>
      {vaultReady && <TransactionTable transactions={demoTransactions} />}
    </main>
  );
}

export default App;
