"""/faucet, /trade/quote and /trade/submit against a fake devnet: no RPC calls reach the network.

FakeRpc keeps token balances and applies each sent transaction's burn and mint, so a buy then a sell_all
moves real (fake) balances, and Sofía signs the quoted transaction the way Phantom would.
"""

import base64
from datetime import datetime
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from solana.exceptions import SolanaRpcException
from solana.rpc.core import RPCException, TransactionExpiredBlockheightExceededError
from solders.hash import Hash
from solders.keypair import Keypair
from solders.transaction import Transaction
from solders.transaction_status import InstructionErrorCustom, TransactionErrorInstructionError
from spl.token.constants import TOKEN_PROGRAM_ID
from spl.token.instructions import get_associated_token_address

from app import chain, config, db, ledger
from app.main import app
from app.replay import clock
from app.routers import vault

U = config.UNITS
VAULT, SOFIA = Keypair(), Keypair()
W = str(SOFIA.pubkey())
MINTS = {"dUSD": Keypair().pubkey(), **{s: Keypair().pubkey() for s in config.SYMBOLS}}
BLOCKHASH = Hash.new_unique()


def network_error():
    return SolanaRpcException(ConnectionError("connection reset"), None, None, None)


def et(hh, mm):
    return datetime(2026, 9, 25, hh, mm, tzinfo=config.ET)


class FakeRpc:
    """The AsyncClient calls chain.py makes, with SPL balances kept per (owner, mint)."""

    def __init__(self):
        self.balances: dict[tuple, int] = {}
        self.sent: list[Transaction] = []
        self.fail_send = None      # exception send_raw_transaction raises
        self.fail_confirm = None   # exception confirm_transaction raises
        self.drop_send_reply = False  # the transaction lands but the reply is lost
        self.drop_confirms = 0        # confirm calls that lose the connection first
        self.err = None            # on-chain error the confirmed status carries

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def get_latest_blockhash(self):
        return SimpleNamespace(value=SimpleNamespace(blockhash=BLOCKHASH, last_valid_block_height=500))

    async def get_account_info(self, ata):
        for (owner, mint), units in self.balances.items():
            if get_associated_token_address(owner, mint) == ata:
                data = bytes(mint) + bytes(owner) + units.to_bytes(8, "little") + bytes(93)
                return SimpleNamespace(value=SimpleNamespace(data=data))
        return SimpleNamespace(value=None)

    async def send_raw_transaction(self, raw):
        if self.fail_send:
            raise self.fail_send
        tx = Transaction.from_bytes(raw)
        tx.verify()
        self.sent.append(tx)
        if self.err is None and self.fail_confirm is None:  # a failed or expired transaction changes nothing
            self._apply(tx)
        if self.drop_send_reply:
            raise network_error()
        return SimpleNamespace(value=tx.signatures[0])

    async def confirm_transaction(self, sig, commitment=None, sleep_seconds=0.5, last_valid_block_height=None):
        if self.drop_confirms:
            self.drop_confirms -= 1
            raise network_error()
        if self.fail_confirm:
            raise self.fail_confirm
        return SimpleNamespace(value=[SimpleNamespace(err=self.err)])

    def _apply(self, tx):
        """Burn (SPL instruction 8) and MintTo (7): amount is a u64 after the 1-byte tag."""
        keys = tx.message.account_keys
        by_ata = {get_associated_token_address(o, m): (o, m) for o in (SOFIA.pubkey(),) for m in MINTS.values()}
        for ix in tx.message.instructions:
            if keys[ix.program_id_index] != TOKEN_PROGRAM_ID or ix.data[0] not in (7, 8):
                continue
            amount = int.from_bytes(bytes(ix.data)[1:9], "little")
            if ix.data[0] == 8:  # burn: accounts = [her token account, mint, owner]
                owner_mint = by_ata[keys[ix.accounts[0]]]
                self.balances[owner_mint] -= amount
            else:                # mint_to: accounts = [mint, her token account, authority]
                owner_mint = by_ata[keys[ix.accounts[1]]]
                self.balances[owner_mint] = self.balances.get(owner_mint, 0) + amount


@pytest.fixture
def rpc(monkeypatch):
    c = db.connect(":memory:")
    db.init(c)
    c.execute("INSERT INTO daily_bars VALUES ('AKAM', '2026-09-24', 110.0, 1000000)")
    c.executemany("INSERT INTO bars VALUES ('AKAM', ?, NULL, NULL, NULL, ?, 1000)",
                  [(config.iso(et(9, 31)), 120.0), (config.iso(et(9, 45)), 124.5)])
    db.use(c)
    clock.reset()
    vault.quotes.clear()
    vault.submitted.clear()
    vault.in_flight.clear()
    monkeypatch.setattr(chain, "POLL_S", 0)
    fake = FakeRpc()
    monkeypatch.setattr(chain, "client", lambda: fake)
    monkeypatch.setattr(chain, "vault", lambda: VAULT)
    monkeypatch.setattr(chain, "mints", lambda: MINTS)
    yield fake
    db.use(None)


api = TestClient(app)


def seek(hh, mm):
    api.post("/replay/control", json={"action": "seek", "to": config.iso(et(hh, mm))})


def quote(**body):
    return api.post("/trade/quote", json={"wallet": W, "symbol": "AKAM", **body})


def sign(q, signer=SOFIA):
    """What the front-end does: Phantom signs first, serialize without the vault's signature."""
    tx = Transaction.from_bytes(base64.b64decode(q["tx_base64"]))
    tx.partial_sign([signer], tx.message.recent_blockhash)
    return base64.b64encode(bytes(tx)).decode()


def submit(q, signed=None):
    return api.post("/trade/submit", json={"quote_id": q["quote_id"], "signed_tx_base64": signed or sign(q)})


def fund(rpc, usd=1000):
    rpc.balances[(SOFIA.pubkey(), MINTS["dUSD"])] = usd * U


def test_faucet_mints_and_records_a_deposit(rpc):
    r = api.post("/faucet", json={"wallet": W}).json()
    assert r == {"signature": str(rpc.sent[0].signatures[0]), "usd_amount": 1000}
    assert rpc.balances[(SOFIA.pubkey(), MINTS["dUSD"])] == 1000 * U
    assert rpc.sent[0].message.account_keys[0] == VAULT.pubkey()  # the vault pays; she needs no SOL
    assert api.get("/portfolio", params={"wallet": W}).json()["cash"] == 1000.0


def test_buy_then_sell_all_through_the_api(rpc):
    api.post("/faucet", json={"wallet": W})

    seek(9, 31)
    q = quote(side="buy", usd_amount=300).json()
    assert {k: q[k] for k in ("symbol", "side", "price", "qty", "usd_amount", "sim_time", "expires_in_s")} == {
        "symbol": "AKAM", "side": "buy", "price": 120.0, "qty": 2.5, "usd_amount": 300.0,
        "sim_time": "2026-09-25T09:31:00-04:00", "expires_in_s": 30}
    unsigned = Transaction.from_bytes(base64.b64decode(q["tx_base64"]))
    assert unsigned.message.account_keys[0] == VAULT.pubkey()  # vault is fee payer, nobody has signed yet

    buy = submit(q).json()
    assert (buy["side"], buy["qty"], buy["price"], buy["cash_before"], buy["cash_after"]) == ("buy", 2.5, 120.0, 1000.0, 700.0)
    assert buy["signature"] == str(rpc.sent[-1].signatures[0])
    rpc.sent[-1].verify()  # both signatures present and valid
    assert rpc.balances[(SOFIA.pubkey(), MINTS["AKAM"])] == 2_500_000

    seek(9, 45)
    q = quote(side="sell", sell_all=True).json()
    assert (q["qty"], q["price"], q["usd_amount"]) == (2.5, 124.5, 311.25)
    sell = submit(q).json()
    assert (sell["realized_pl"], sell["outcome"], sell["held_min"], sell["cash_after"]) == (11.25, "win", 14, 1011.25)
    assert rpc.balances[(SOFIA.pubkey(), MINTS["AKAM"])] == 0

    assert api.get("/transactions", params={"wallet": W}).json() == [sell, buy]
    assert api.get("/portfolio", params={"wallet": W}).json()["stats"]["total_pl"] == 11.25


def test_buy_burns_exact_dollars_and_rounds_qty_down(rpc):
    fund(rpc)
    seek(9, 31)
    q = quote(side="buy", usd_amount=50).json()
    assert (q["usd_amount"], q["qty"]) == (50.0, 0.416666)  # 50 / 120 = 0.4166666…, rounded down


@pytest.mark.parametrize("body, status, code", [
    ({"side": "buy", "usd_amount": 300, "qty": 1}, 400, "invalid_amount"),
    ({"side": "buy", "sell_all": True}, 400, "invalid_amount"),
    ({"side": "buy", "usd_amount": 0}, 400, "invalid_amount"),
    ({"side": "buy", "usd_amount": 0.0000001}, 400, "invalid_amount"),
    ({"side": "buy", "usd_amount": 5000}, 409, "insufficient_funds"),
    ({"side": "sell", "sell_all": True}, 409, "insufficient_shares"),
    ({"side": "sell", "qty": 1}, 409, "insufficient_shares"),
    ({"side": "buy", "usd_amount": 10, "symbol": "NOPE"}, 404, "unknown_symbol"),
    ({"side": "buy", "usd_amount": 10, "wallet": "not-a-wallet"}, 400, "invalid_wallet"),
])
def test_quote_rejects(rpc, body, status, code):
    fund(rpc)
    seek(9, 31)
    r = quote(**body)
    assert (r.status_code, r.json()["error"]) == (status, code)


def buy_quote(rpc):
    fund(rpc)
    seek(9, 31)
    return quote(side="buy", usd_amount=300).json()


def assert_no_trade(rpc):
    assert ledger.rows(W) == []
    assert rpc.balances[(SOFIA.pubkey(), MINTS["dUSD"])] == 1000 * U


def test_expired_quote(rpc):
    q = buy_quote(rpc)
    vault.quotes[q["quote_id"]].expires_at = 0
    r = submit(q)
    assert (r.status_code, r.json()["error"]) == (409, "quote_expired")
    assert rpc.sent == [] and ledger.rows(W) == []


def test_a_retried_submit_returns_the_same_trade(rpc):
    q = buy_quote(rpc)
    first = submit(q)
    again = submit(q)  # double click, or the first reply was lost
    assert first.status_code == again.status_code == 200 and first.json() == again.json()
    assert len(ledger.rows(W)) == 1 and len(rpc.sent) == 1


def test_a_submit_already_in_flight_is_refused(rpc):
    q = buy_quote(rpc)
    vault.in_flight.add(q["quote_id"])
    r = submit(q)
    assert (r.status_code, r.json()["error"]) == (409, "submit_in_progress")
    assert rpc.sent == []


def test_a_lost_send_reply_still_records_the_trade(rpc):
    # The transaction reached devnet but the reply didn't come back: checking its signature finds it confirmed.
    q = buy_quote(rpc)
    rpc.drop_send_reply = True
    r = submit(q)
    assert r.status_code == 200 and r.json()["signature"] == str(rpc.sent[0].signatures[0])
    assert len(ledger.rows(W)) == 1


def test_confirm_survives_a_dropped_connection(rpc):
    q = buy_quote(rpc)
    rpc.drop_confirms = 2
    assert submit(q).status_code == 200
    assert len(ledger.rows(W)) == 1


def test_devnet_unreachable_while_confirming_writes_no_row(rpc):
    q = buy_quote(rpc)
    rpc.drop_confirms = chain.CONFIRM_ATTEMPTS
    r = submit(q)
    assert (r.status_code, r.json()["error"]) == (502, "chain_unavailable")
    assert "check the transaction log" in r.json()["message"] and ledger.rows(W) == []


def test_rejects_a_transaction_other_than_the_quote(rpc):
    q, other = buy_quote(rpc), quote(side="buy", usd_amount=1).json()
    r = submit(q, signed=sign(other))
    assert (r.status_code, r.json()["error"]) == (400, "tx_mismatch")
    assert rpc.sent == []
    assert_no_trade(rpc)


def test_rejects_when_she_has_not_signed(rpc):
    q = buy_quote(rpc)
    r = submit(q, signed=q["tx_base64"])
    assert (r.status_code, r.json()["error"]) == (400, "not_signed")
    assert_no_trade(rpc)


def test_rejects_garbage(rpc):
    r = submit(buy_quote(rpc), signed="not base64!")
    assert (r.status_code, r.json()["error"]) == (400, "invalid_transaction")


@pytest.mark.parametrize("setup, code", [
    (lambda rpc: setattr(rpc, "err", TransactionErrorInstructionError(3, InstructionErrorCustom(1))), "tx_failed"),
    (lambda rpc: setattr(rpc, "fail_send", RPCException(SimpleNamespace(message="simulation failed"))), "tx_failed"),
    (lambda rpc: setattr(rpc, "fail_confirm", TransactionExpiredBlockheightExceededError("expired")), "quote_expired"),
])
def test_chain_failures_write_no_ledger_row(rpc, setup, code):
    q = buy_quote(rpc)
    setup(rpc)
    r = submit(q)
    assert (r.status_code, r.json()["error"]) == (409, code)
    assert_no_trade(rpc)


def test_reset_drops_open_and_finished_quotes(rpc):
    done, q = buy_quote(rpc), quote(side="buy", usd_amount=10).json()
    submit(done)
    api.post("/demo/reset", json={"wallet": W})
    assert q["quote_id"] not in vault.quotes and done["quote_id"] not in vault.submitted
