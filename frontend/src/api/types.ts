export interface ApiError { error: string; message: string }
export interface ReplayState { mode: string; sim_time: string; speed: number; running: boolean }
export interface PriceQuote { symbol: string; price: number; prev_close: number; change_pct: number; sim_time: string }
export interface PriceBar { time: string; open: number; high: number; low: number; close: number; volume: number }
export interface ScannerRow { symbol: string; token_symbol: string; price: number; change_pct: number; rvol: number; momentum_pass: boolean; rvol_pass: boolean; signals_passed: number; as_of: string; headline: string | null; headline_url: string | null }
export interface FaucetResponse { signature: string; usd_amount: number }
export interface TradeQuote { quote_id: string; symbol: string; side: "buy" | "sell"; price: number; qty: number; usd_amount: number; sim_time: string; expires_in_s: number; tx_base64: string }
export interface TransactionRow { id: number; sim_time: string; symbol: string; side: "buy" | "sell"; qty: number; price: number; usd_amount: number; cash_before: number; cash_after: number; realized_pl: number | null; realized_pl_pct: number | null; outcome: "win" | "loss" | null; opened_at: string | null; held_min: number | null; signature: string; explorer_url: string | null }
export interface Holding { symbol: string; qty: number; avg_cost: number; price: number; market_value: number; unrealized_pl: number }
export interface Portfolio { cash: number; holdings: Holding[]; total_value: number; deposited: number; stats: { total_pl: number; total_pl_pct: number; avg_win: number | null; avg_loss: number | null; trade_count: number; win_count: number; loss_count: number }; equity_curve: Array<{ t: string; value: number }> }
