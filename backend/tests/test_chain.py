"""Vault transaction shape and signing order, offline: no RPC calls reach the network."""

import asyncio
import json
import os

import httpx2
import pytest
from solana.rpc.core import RPCException
from solders.hash import Hash
from solders.keypair import Keypair
from solders.signature import Signature
from solders.transaction import Transaction, TransactionError
from solders.transaction_status import InstructionErrorCustom, TransactionErrorInstructionError

from app import chain

VAULT, SOFIA, DUSD, AKAM = Keypair(), Keypair(), Keypair().pubkey(), Keypair().pubkey()
BLOCKHASH = Hash.new_unique()


class FakeRpc:
    def __init__(self, err=None):
        self.sent, self.err = None, err

    async def send_raw_transaction(self, raw):
        self.sent = Transaction.from_bytes(raw)
        return type("Resp", (), {"value": self.sent.signatures[0]})()

    async def confirm_transaction(self, sig, commitment=None, sleep_seconds=0.5, last_valid_block_height=None):
        # Like solana-py's: returns once the status reaches confirmed, whether or not the transaction failed.
        self.last_valid_block_height = last_valid_block_height
        return type("Resp", (), {"value": [type("Status", (), {"err": self.err})()]})()


def buy_message():
    return chain.swap_message(VAULT.pubkey(), SOFIA.pubkey(), DUSD, 116_000_000, AKAM, 1_000_000, BLOCKHASH)


def signed_by_sofia(message):
    tx = Transaction.from_bytes(chain.unsigned_tx(message))
    tx.partial_sign([SOFIA], BLOCKHASH)
    return bytes(tx)


def test_vault_pays_the_fee_and_both_sign():
    msg = buy_message()
    assert msg.account_keys[0] == VAULT.pubkey()  # first account is the fee payer
    assert msg.header.num_required_signatures == 2
    assert Transaction.from_bytes(chain.unsigned_tx(msg)).signatures == [Signature.default()] * 2


def test_sets_its_own_compute_budget_so_phantom_leaves_the_message_alone():
    msg = buy_message()
    programs = [str(msg.account_keys[ix.program_id_index]) for ix in msg.instructions]
    assert programs[:2] == ["ComputeBudget111111111111111111111111111111"] * 2


def test_cosign_sends_a_fully_signed_transaction():
    rpc, msg = FakeRpc(), buy_message()
    sig = asyncio.run(chain.cosign_and_send(rpc, VAULT, signed_by_sofia(msg), msg))
    rpc.sent.verify()
    assert sig == rpc.sent.signatures[0]


def test_cosign_raises_when_the_transaction_confirms_with_an_error():
    # e.g. two trades sent within a second both pass preflight, then the second burn (instruction 3) comes up short.
    rpc, msg = FakeRpc(err=TransactionErrorInstructionError(3, InstructionErrorCustom(1))), buy_message()
    with pytest.raises(RuntimeError, match="failed"):
        asyncio.run(chain.cosign_and_send(rpc, VAULT, signed_by_sofia(msg), msg))


def test_cosign_waits_only_until_the_quoted_blockhash_expires():
    rpc, msg = FakeRpc(), buy_message()
    asyncio.run(chain.cosign_and_send(rpc, VAULT, signed_by_sofia(msg), msg, last_valid_block_height=1_000))
    assert rpc.last_valid_block_height == 1_000


def test_cosign_refuses_a_transaction_that_differs_from_the_quote():
    rpc, quoted = FakeRpc(), buy_message()
    tampered = chain.swap_message(VAULT.pubkey(), SOFIA.pubkey(), DUSD, 1, AKAM, 1_000_000, BLOCKHASH)
    with pytest.raises(ValueError):
        asyncio.run(chain.cosign_and_send(rpc, VAULT, signed_by_sofia(tampered), quoted))
    assert rpc.sent is None


def test_cosign_refuses_when_she_has_not_signed():
    rpc, msg = FakeRpc(), buy_message()
    with pytest.raises(TransactionError):
        asyncio.run(chain.cosign_and_send(rpc, VAULT, chain.unsigned_tx(msg), msg))
    assert rpc.sent is None


def over_http(on_send, landed):
    """chain.client() with only its HTTP transport faked, so solana-py's own retry still runs.
    on_send(n, request, reply) answers the n-th sendTransaction; the signature has a confirmed status if `landed`."""
    calls = []

    def handler(request):
        body = json.loads(request.content)
        calls.append(body["method"])

        def reply(**result_or_error):
            return httpx2.Response(200, json={"jsonrpc": "2.0", "id": body["id"], **result_or_error})

        if body["method"] == "sendTransaction":
            return on_send(calls.count("sendTransaction"), request, reply)
        if body["method"] == "getBlockHeight":
            return reply(result=100)
        status = {"slot": 1, "confirmations": None, "err": None, "status": {"Ok": None}, "confirmationStatus": "confirmed"}
        return reply(result={"context": {"slot": 1}, "value": [status if landed else None]})

    rpc = chain.client()
    rpc._provider.session = httpx2.AsyncClient(transport=httpx2.MockTransport(handler))
    return rpc, calls


def preflight_error(err, message):
    return {"code": -32002, "message": f"Transaction simulation failed: {message}",
            "data": {"accounts": None, "err": err, "innerInstructions": None, "loadedAccountsDataSize": 0,
                     "logs": [], "replacementBlockhash": None, "returnData": None, "unitsConsumed": 0}}


async def cosign_over(rpc, msg):
    async with rpc:
        return await chain.cosign_and_send(rpc, VAULT, signed_by_sofia(msg), msg, last_valid_block_height=200)


def test_a_resend_that_finds_the_trade_already_landed_confirms_it():
    # The first send landed but its reply was lost, so solana-py sent the same bytes again, and devnet refused that
    # copy as already processed. The trade happened: confirm it rather than report it as failed.
    def on_send(n, request, reply):
        if n == 1:
            raise httpx2.ReadTimeout("reply lost", request=request)
        return reply(error=preflight_error("AlreadyProcessed", "This transaction has already been processed"))

    rpc, calls = over_http(on_send, landed=True)
    msg = buy_message()
    assert asyncio.run(cosign_over(rpc, msg)) == VAULT.sign_message(bytes(msg))  # the fee payer's signature
    assert calls[:3] == ["sendTransaction", "sendTransaction", "getSignatureStatuses"]


def test_a_send_devnet_rejects_still_fails():
    def on_send(n, request, reply):
        return reply(error=preflight_error("BlockhashNotFound", "Blockhash not found"))

    rpc, _ = over_http(on_send, landed=False)
    with pytest.raises(RPCException):
        asyncio.run(cosign_over(rpc, buy_message()))


@pytest.mark.skipif(os.name == "nt", reason="POSIX file modes")
def test_saved_keypair_is_readable_only_by_its_owner(tmp_path):
    path = tmp_path / "keys" / "vault-keypair.json"
    chain.save_keypair(VAULT, path)
    assert path.stat().st_mode & 0o777 == 0o600  # the vault key is mint authority for every token
    assert chain.load_keypair(path).pubkey() == VAULT.pubkey()
