"""Vault transaction shape and signing order, offline: no RPC calls reach the network."""

import asyncio

import pytest
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
