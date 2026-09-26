"""6 PM checkpoint test run, Phantom half: does Phantom sign a vault-fee-payer buy without a red warning?

Serves one page at http://localhost:8001 that connects Phantom, gets demo dollars, and buys 1 AKAM through
quote → Phantom signs first → vault co-signs and sends. Standalone on purpose: the real /faucet and /trade/*
routes are Matthew's (routers/vault.py), and the real ticket is Diego's.

Run from backend/ after setup_devnet:  ./venv/bin/python -m scripts.phantom_check
Phantom: Settings → Developer Settings → Testnet Mode on (devnet).
"""

import base64
import time
import uuid

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from solders.pubkey import Pubkey

from app import chain, config

PRICE = 116.00  # hard-coded like vault_test_run; /trade/quote will use price_at
QUOTE_TTL_S = 30

app = FastAPI()
quotes: dict[str, tuple[float, object]] = {}  # quote_id → (expires_at, Message)


class WalletBody(BaseModel):
    wallet: str


class SubmitBody(BaseModel):
    quote_id: str
    signed_tx_base64: str


def explorer(sig) -> str:
    return f"https://explorer.solana.com/tx/{sig}?cluster=devnet"


@app.post("/faucet")
async def faucet(body: WalletBody):
    async with chain.client() as rpc:
        sig = await chain.faucet(rpc, chain.vault(), chain.mints()["dUSD"], Pubkey.from_string(body.wallet),
                                 1000 * config.UNITS)
    return {"explorer_url": explorer(sig)}


@app.post("/quote")
async def quote(body: WalletBody):
    vault, mints = chain.vault(), chain.mints()
    async with chain.client() as rpc:
        blockhash = (await rpc.get_latest_blockhash()).value.blockhash
    message = chain.swap_message(vault.pubkey(), Pubkey.from_string(body.wallet), mints["dUSD"],
                                 round(PRICE * config.UNITS), mints["AKAM"], 1 * config.UNITS, blockhash)
    quote_id = uuid.uuid4().hex
    quotes[quote_id] = (time.monotonic() + QUOTE_TTL_S, message)
    return {"quote_id": quote_id, "tx_base64": base64.b64encode(chain.unsigned_tx(message)).decode()}


@app.post("/submit")
async def submit(body: SubmitBody):
    expires_at, message = quotes.pop(body.quote_id, (0, None))
    if time.monotonic() > expires_at:
        raise HTTPException(409, "quote expired, buy again")
    async with chain.client() as rpc:
        sig = await chain.cosign_and_send(rpc, chain.vault(), base64.b64decode(body.signed_tx_base64), message)
    return {"explorer_url": explorer(sig)}


@app.get("/", response_class=HTMLResponse)
def page():
    return PAGE


PAGE = """<!doctype html>
<meta charset="utf-8">
<title>Phantom check</title>
<style>body{font:16px system-ui;max-width:640px;margin:40px auto;padding:0 16px}button{font:inherit;margin:4px 8px 4px 0}
pre{white-space:pre-wrap;background:#f4f4f4;padding:12px}</style>
<h1>Vault test run: Phantom signs first</h1>
<p>Phantom in Testnet Mode (devnet). Watch for a red warning on the buy.</p>
<button id="connect">1. Connect Phantom</button>
<button id="faucet" disabled>2. Get 1,000 dUSD</button>
<button id="buy" disabled>3. Buy 1 AKAM ($116)</button>
<pre id="log"></pre>
<script src="https://cdn.jsdelivr.net/npm/@solana/web3.js@1.98.4/lib/index.iife.min.js"></script>
<script>
const $ = (id) => document.getElementById(id);
const log = (msg) => { $("log").textContent += msg + "\\n"; };
let wallet;

async function post(path, body) {
  const res = await fetch(path, {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(body)});
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || res.statusText);
  return data;
}

async function step(button, fn) {
  button.disabled = true;
  try { await fn(); } catch (e) { log("ERROR: " + e.message); }
  button.disabled = false;
}

$("connect").onclick = () => step($("connect"), async () => {
  const phantom = window.phantom?.solana;
  if (!phantom?.isPhantom) throw new Error("Phantom not found; install it and reload");
  wallet = (await phantom.connect()).publicKey.toString();
  log("connected " + wallet);
  $("faucet").disabled = $("buy").disabled = false;
});

$("faucet").onclick = () => step($("faucet"), async () => {
  log("faucet… " + (await post("/faucet", {wallet})).explorer_url);
});

$("buy").onclick = () => step($("buy"), async () => {
  const {quote_id, tx_base64} = await post("/quote", {wallet});
  const bytes = Uint8Array.from(atob(tx_base64), (c) => c.charCodeAt(0));
  const tx = solanaWeb3.Transaction.from(bytes);
  const signed = await window.phantom.solana.signTransaction(tx);  // Phantom signs first
  const raw = signed.serialize({requireAllSignatures: false});
  const signed_tx_base64 = btoa(String.fromCharCode(...raw));
  log("buy… " + (await post("/submit", {quote_id, signed_tx_base64})).explorer_url);
});
</script>
"""


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8001)
