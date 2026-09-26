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
from pathlib import Path

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from solders.compute_budget import set_compute_unit_limit, set_compute_unit_price
from solders.message import Message
from solders.pubkey import Pubkey
from solders.transaction import Transaction

from spl.token.constants import TOKEN_PROGRAM_ID
from spl.token.instructions import burn, get_associated_token_address
from spl.token.models import BurnParams

from app import chain, config

PRICE = 116.00  # hard-coded like vault_test_run; /trade/quote will use price_at
QUOTE_TTL_S = 60  # longer than /trade/quote's 30 s so there is time to read Phantom's screen

app = FastAPI()
quotes: dict[str, tuple[float, object]] = {}  # quote_id → (expires_at, Message)


class WalletBody(BaseModel):
    wallet: str


class QuoteBody(WalletBody):
    # Which transaction layout to try in Phantom:
    #   vault_pays: the spec's design (vault is fee payer, both sign)
    #   she_pays:   the spec's first fallback (she is fee payer, vault still signs as mint authority)
    #   burn_only:  the 8 PM fallback's first half (she signs alone; the vault would mint in a second tx)
    mode: str = "vault_pays"


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
async def quote(body: QuoteBody):
    vault, mints, owner = chain.vault(), chain.mints(), Pubkey.from_string(body.wallet)
    usd_units = round(PRICE * config.UNITS)
    async with chain.client() as rpc:
        blockhash = (await rpc.get_latest_blockhash()).value.blockhash
    if body.mode == "burn_only":
        message = Message.new_with_blockhash([
            set_compute_unit_limit(chain.COMPUTE_UNITS), set_compute_unit_price(chain.MICROLAMPORTS_PER_CU),
            burn(BurnParams(program_id=TOKEN_PROGRAM_ID, account=get_associated_token_address(owner, mints["dUSD"]),
                            mint=mints["dUSD"], owner=owner, amount=usd_units)),
        ], owner, blockhash)
    else:
        message = chain.swap_message(vault.pubkey(), owner, mints["dUSD"], usd_units, mints["AKAM"], 1 * config.UNITS,
                                     blockhash, fee_payer=owner if body.mode == "she_pays" else None)
    quote_id = uuid.uuid4().hex
    quotes[quote_id] = (time.monotonic() + QUOTE_TTL_S, message)
    return {"quote_id": quote_id, "tx_base64": base64.b64encode(chain.unsigned_tx(message)).decode()}


@app.post("/submit")
async def submit(body: SubmitBody):
    expires_at, message = quotes.pop(body.quote_id, (0, None))
    if time.monotonic() > expires_at:
        raise HTTPException(409, "quote expired, buy again")
    raw = base64.b64decode(body.signed_tx_base64)
    try:
        async with chain.client() as rpc:
            if message.header.num_required_signatures == 1:  # burn_only: she is the only signer
                if bytes(Transaction.from_bytes(raw).message) != bytes(message):
                    raise ValueError("signed transaction does not match the quote")
                sig = (await rpc.send_raw_transaction(raw)).value
                await rpc.confirm_transaction(sig, sleep_seconds=chain.POLL_S)
            else:
                sig = await chain.cosign_and_send(rpc, chain.vault(), raw, message)
    except ValueError as e:
        Path("phantom_signed.b64").write_text(body.signed_tx_base64)  # for comparing with the quote offline
        raise HTTPException(409, f"{e}. quoted: {describe(message)} | signed: {describe(Transaction.from_bytes(raw).message)}")
    return {"explorer_url": explorer(sig)}


def describe(message) -> str:
    """Fee payer and the program of each instruction, to see what Phantom changed."""
    keys = message.account_keys
    programs = [str(keys[ix.program_id_index])[:8] for ix in message.instructions]
    return f"payer {str(keys[0])[:8]}, signers {message.header.num_required_signatures}, programs {programs}"


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
<p>Fallbacks to compare in Phantom (she needs a little SOL for these):</p>
<button id="she_pays" disabled>3b. Buy, she pays the fee</button>
<button id="burn_only" disabled>3c. Burn $116 dUSD, she signs alone</button>
<pre id="log"></pre>
<script src="https://cdn.jsdelivr.net/npm/@solana/web3.js@1.98.4/lib/index.iife.min.js"></script>
<script>
const $ = (id) => document.getElementById(id);
const log = (msg) => { $("log").textContent += msg + "\\n"; };
let wallet, provider;  // not "phantom": the extension owns window.phantom and a global let would clash

async function post(path, body) {
  const res = await fetch(path, {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(body)});
  const text = await res.text();
  let data; try { data = JSON.parse(text); } catch { data = {detail: text}; }
  if (!res.ok) throw new Error(data.detail || res.statusText);
  return data;
}

async function step(button, fn) {
  button.disabled = true;
  try { await fn(); } catch (e) { log("ERROR: " + e.message); }
  button.disabled = false;
}

$("connect").onclick = () => step($("connect"), async () => {
  provider = [window.phantom?.solana, window.solana].find((p) => p?.isPhantom);  // older Phantom only sets window.solana
  if (!provider) throw new Error("Phantom not found in this browser; install it (or allow it on this site) and reload");
  log("waiting for you to approve in Phantom (click its toolbar icon if no popup)…");
  wallet = (await provider.connect()).publicKey.toString();
  log("connected " + wallet);
  for (const id of ["faucet", "buy", "she_pays", "burn_only"]) $(id).disabled = false;
});

$("faucet").onclick = () => step($("faucet"), async () => {
  log("faucet… " + (await post("/faucet", {wallet})).explorer_url);
});

const buy = (mode) => () => step($(mode), async () => {
  const {quote_id, tx_base64} = await post("/quote", {wallet, mode});
  const bytes = Uint8Array.from(atob(tx_base64), (c) => c.charCodeAt(0));
  const tx = solanaWeb3.Transaction.from(bytes);
  log("waiting for you to approve the buy in Phantom…");
  const signed = await provider.signTransaction(tx);  // Phantom signs first
  const raw = signed.serialize({requireAllSignatures: false});
  const signed_tx_base64 = btoa(String.fromCharCode(...raw));
  log(mode + "… " + (await post("/submit", {quote_id, signed_tx_base64})).explorer_url);
});
$("buy").onclick = buy("buy");
$("she_pays").onclick = buy("she_pays");
$("burn_only").onclick = buy("burn_only");
</script>
"""


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8001)
