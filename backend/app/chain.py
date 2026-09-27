"""Devnet side of the vault (BUILD_SPEC.md → Vault). The vault is fee payer and mint authority for dUSD and
every stock mint, so a trade is one legacy transaction: burn what she pays with, mint what she gets.

Signing order matters: she signs first (Phantom), then `cosign` adds the vault's signature.
"""

import asyncio
import json
import os
from pathlib import Path

from solana.exceptions import SolanaRpcException
from solana.rpc.async_api import AsyncClient
from solana.rpc.commitment import Confirmed
from solana.rpc.core import RPCException, TransactionExpiredBlockheightExceededError, UnconfirmedTxError
from solders.compute_budget import set_compute_unit_limit, set_compute_unit_price
from solders.hash import Hash
from solders.keypair import Keypair
from solders.message import Message
from solders.pubkey import Pubkey
from solders.signature import Signature
from solders.transaction import Transaction
from solders.transaction_status import TransactionConfirmationStatus
from spl.token.constants import TOKEN_PROGRAM_ID
from spl.token.instructions import (
    burn, create_idempotent_associated_token_account, get_associated_token_address, mint_to,
)
from spl.token.models import BurnParams, MintToParams

from . import config  # noqa: F401  loads .env (SOLANA_RPC_URL, VAULT_KEYPAIR)

BACKEND = Path(__file__).resolve().parent.parent
RPC_URL = os.getenv("SOLANA_RPC_URL", "https://api.devnet.solana.com")
VAULT_KEYPAIR = Path(os.getenv("VAULT_KEYPAIR", BACKEND / "keys" / "vault-keypair.json"))
MINTS_PATH = BACKEND / "mints.json"
# The public devnet RPC rate-limits status polling; a Helius URL in SOLANA_RPC_URL is faster and roomier.
POLL_S = 2.0
# A network error while waiting for confirmation is retried this many times before giving up.
CONFIRM_ATTEMPTS = 5
# Phantom adds its own compute budget (and so changes the message she signs) to any transaction without one,
# which would fail the quote check. Setting both here keeps the message as quoted. ~40k CU used; fee is the vault's.
COMPUTE_UNITS = 100_000
MICROLAMPORTS_PER_CU = 1_000


def load_keypair(path: Path) -> Keypair:
    """Reads the solana-keygen format: a JSON array of 64 bytes."""
    return Keypair.from_bytes(bytes(json.loads(path.read_text())))


def save_keypair(kp: Keypair, path: Path) -> None:
    """Owner-only (0600) before the key is written: the vault key is mint authority for every token."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.touch(mode=0o600)
    path.chmod(0o600)  # touch leaves an existing file's mode alone
    path.write_text(json.dumps(list(bytes(kp))))


def vault() -> Keypair:
    return load_keypair(VAULT_KEYPAIR)


def mints() -> dict[str, Pubkey]:
    """{"dUSD": Pubkey, "AKAM": Pubkey, ...} from mints.json."""
    return {k: Pubkey.from_string(v) for k, v in json.loads(MINTS_PATH.read_text()).items()}


def client() -> AsyncClient:
    return AsyncClient(RPC_URL, commitment=Confirmed)


def _mint_ix(vault_key: Pubkey, mint: Pubkey, owner: Pubkey, units: int):
    return mint_to(MintToParams(program_id=TOKEN_PROGRAM_ID, mint=mint,
                                dest=get_associated_token_address(owner, mint),
                                mint_authority=vault_key, amount=units))


def swap_message(vault_key: Pubkey, owner: Pubkey, pay_mint: Pubkey, pay_units: int,
                 get_mint: Pubkey, get_units: int, blockhash: Hash, fee_payer: Pubkey | None = None) -> Message:
    """Burn `pay_units` of her `pay_mint`, mint `get_units` of `get_mint` to her. Buy: pay dUSD, get stock.
    Sell: the mirror. The vault pays the fee and the rent for her token account if it's missing."""
    return Message.new_with_blockhash([
        set_compute_unit_limit(COMPUTE_UNITS),
        set_compute_unit_price(MICROLAMPORTS_PER_CU),
        create_idempotent_associated_token_account(vault_key, owner, get_mint),
        burn(BurnParams(program_id=TOKEN_PROGRAM_ID, account=get_associated_token_address(owner, pay_mint),
                        mint=pay_mint, owner=owner, amount=pay_units)),
        _mint_ix(vault_key, get_mint, owner, get_units),
    ], fee_payer or vault_key, blockhash)


async def token_balance(rpc: AsyncClient, owner: Pubkey, mint: Pubkey) -> int:
    """Her balance of `mint` in base units; 0 if her token account doesn't exist yet.

    Reads the account directly: an SPL token account is mint (32 bytes), owner (32), then amount (u64 LE).
    """
    account = (await rpc.get_account_info(get_associated_token_address(owner, mint))).value
    return int.from_bytes(bytes(account.data)[64:72], "little") if account else 0


def unsigned_tx(message: Message) -> bytes:
    """What /trade/quote hands the front-end as tx_base64 (after base64)."""
    return bytes(Transaction.new_unsigned(message))


async def confirm(rpc: AsyncClient, sig: Signature, last_valid_block_height: int | None = None) -> None:
    """Waits for `confirmed`, then raises if the transaction failed: confirm_transaction returns either way.
    Given the blockhash's last valid height, it gives up once the transaction can no longer land, not after 90 s.
    Raises UnconfirmedTxError if it landed but hadn't confirmed by then: check again later."""
    for attempt in range(CONFIRM_ATTEMPTS):
        try:
            resp = await rpc.confirm_transaction(sig, Confirmed, sleep_seconds=POLL_S,
                                                 last_valid_block_height=last_valid_block_height)
            break
        except TransactionExpiredBlockheightExceededError:
            # confirm_transaction stops at the expiry without a last look, and a resubmit after a lost connection
            # may ask even later: check the signature, history included, before calling it expired.
            resp = await rpc.get_signature_statuses([sig], search_transaction_history=True)
            if resp.value[0] is None:
                raise
            if resp.value[0].confirmation_status not in (TransactionConfirmationStatus.Confirmed,
                                                         TransactionConfirmationStatus.Finalized):
                # Only processed, so it could still drop with its fork. It can't land anywhere else now, so the
                # next look finds it confirmed or gone.
                raise UnconfirmedTxError(f"{sig} has been processed but not confirmed")
            break
        except SolanaRpcException:  # a dropped connection says nothing about the transaction: ask again
            if attempt == CONFIRM_ATTEMPTS - 1:
                raise
            await asyncio.sleep(POLL_S)
    status = resp.value[0]
    if status is None or status.err is not None:
        raise RuntimeError(f"transaction {sig} failed: {status.err if status else 'no status'}")


async def send_and_confirm(rpc: AsyncClient, tx: Transaction, last_valid_block_height: int | None = None) -> Signature:
    """Sends a fully signed transaction and waits for `confirmed`.

    The signature is known before sending, so a network error on the send doesn't lose a transaction that
    reached the cluster: with a blockhash expiry to wait for, it keeps checking that signature until the
    transaction confirms, fails, or can no longer land. The same bytes can only land once, so it can't trade twice,
    even though solana-py resends a request whose reply was lost.
    """
    sig = tx.signatures[0]
    try:
        await rpc.send_raw_transaction(bytes(tx))
    except SolanaRpcException:
        if last_valid_block_height is None:  # nothing bounds the wait, so don't guess
            raise
    except RPCException:
        # If solana-py's resend follows a copy that landed, devnet refuses it as already processed. Only a
        # signature devnet has never seen is a real rejection.
        if (await rpc.get_signature_statuses([sig])).value[0] is None:
            raise
    await confirm(rpc, sig, last_valid_block_height)
    return sig


def cosign(vault_kp: Keypair, signed_tx: bytes, expected: Message) -> Transaction:
    """/trade/submit's checks: refuse anything but the quoted message, then add the vault's signature to hers."""
    tx = Transaction.from_bytes(signed_tx)
    if bytes(tx.message) != bytes(expected):
        raise ValueError("signed transaction does not match the quote")
    tx.partial_sign([vault_kp], tx.message.recent_blockhash)
    tx.verify()  # raises if her signature is missing or wrong
    return tx


async def cosign_and_send(rpc: AsyncClient, vault_kp: Keypair, signed_tx: bytes, expected: Message,
                          last_valid_block_height: int | None = None) -> Signature:
    """cosign, send, wait for confirmed. Pass the quote's last_valid_block_height (from get_latest_blockhash) so a
    dropped transaction fails fast."""
    return await send_and_confirm(rpc, cosign(vault_kp, signed_tx, expected), last_valid_block_height)


async def faucet(rpc: AsyncClient, vault_kp: Keypair, dusd: Pubkey, owner: Pubkey, units: int) -> Signature:
    """Mints dUSD to her. Only the vault signs, so she needs no SOL."""
    latest = (await rpc.get_latest_blockhash()).value
    tx = Transaction.new_signed_with_payer([
        create_idempotent_associated_token_account(vault_kp.pubkey(), owner, dusd),
        _mint_ix(vault_kp.pubkey(), dusd, owner, units),
    ], vault_kp.pubkey(), [vault_kp], latest.blockhash)
    return await send_and_confirm(rpc, tx, latest.last_valid_block_height)
