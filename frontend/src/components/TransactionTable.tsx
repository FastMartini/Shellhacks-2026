import type { TransactionRow } from "../api/types";

const dollars = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" });
const date = new Intl.DateTimeFormat("en-US", { month: "short", day: "numeric", timeZone: "America/New_York" });
const time = new Intl.DateTimeFormat("en-US", { hour: "numeric", minute: "2-digit", timeZone: "America/New_York" });

function replayTime(value: string) {
  const parsed = new Date(value);
  return `${date.format(parsed)} · ${time.format(parsed)}`;
}

function percent(value: number | null) {
  if (value == null) return "—";
  return `${value >= 0 ? "+" : ""}${value.toFixed(2)}%`;
}

export function TransactionTable({ transactions }: { transactions: TransactionRow[] }) {
  return (
    <section className="panel transaction-panel" aria-labelledby="transactions-heading">
      <div className="panel-heading">
        <div><p className="eyebrow">Demo ledger</p><h2 id="transactions-heading">Transactions</h2></div>
        <span>{transactions.length} recorded</span>
      </div>
      {transactions.length === 0 ? <div className="transaction-empty">Completed buys and sells will appear here after they confirm on Solana devnet.</div> :
        <div className="transaction-table-wrap"><table className="transaction-table">
          <thead><tr><th>Time</th><th>Side</th><th>Stock</th><th>Shares</th><th>Price</th><th>Value</th><th>Cash before</th><th>Cash after</th><th>P/L</th><th>P/L %</th><th>Outcome</th><th>Held</th><th>Proof</th></tr></thead>
          <tbody>{transactions.map((transaction) => <tr key={transaction.id}>
            <td>{replayTime(transaction.sim_time)}</td>
            <td><span className={`transaction-side ${transaction.side}`}>{transaction.side}</span></td>
            <td className="transaction-symbol">{transaction.symbol}</td>
            <td>{transaction.qty.toFixed(6)}</td>
            <td>{dollars.format(transaction.price)}</td>
            <td>{dollars.format(transaction.usd_amount)}</td>
            <td>{dollars.format(transaction.cash_before)}</td>
            <td>{dollars.format(transaction.cash_after)}</td>
            <td className={transaction.realized_pl == null ? "" : transaction.realized_pl >= 0 ? "positive" : "negative"}>{transaction.realized_pl == null ? "—" : dollars.format(transaction.realized_pl)}</td>
            <td className={transaction.realized_pl_pct == null ? "" : transaction.realized_pl_pct >= 0 ? "positive" : "negative"}>{percent(transaction.realized_pl_pct)}</td>
            <td>{transaction.outcome ?? "—"}</td>
            <td>{transaction.held_min == null ? "—" : `${transaction.held_min} min`}</td>
            <td>{transaction.explorer_url ? <a href={transaction.explorer_url} target="_blank" rel="noreferrer">Explorer ↗</a> : "—"}</td>
          </tr>)}</tbody>
        </table></div>}
      <p className="transaction-note">Only confirmed transactions are recorded. Symbols are shown exactly as returned by the API.</p>
    </section>
  );
}
