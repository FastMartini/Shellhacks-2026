"""Devnet side of the vault (BUILD_SPEC.md → Vault). The vault is fee payer and mint authority for dUSD and
every stock mint, so a trade is one legacy transaction: burn what she pays with, mint what she gets.

Signing order matters: she signs first (Phantom), then `cosign_and_send` adds the vault's signature.
"""

import json
import os
from pathlib import Path

from solana.rpc.async_api import AsyncClient
from solana.rpc.commitment import Confirmed
from solders.hash import Hash
from solders.keypair import Keypair
from solders.message import Message
from solders.pubkey import Pubkey
from solders.signature import Signature
from solders.transaction import Transaction
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


def load_keypair(path: Path) -> Keypair:
    """Reads the solana-keygen format: a JSON array of 64 bytes."""
    return Keypair.from_bytes(bytes(json.loads(path.read_text())))


def save_keypair(kp: Keypair, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
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
                 get_mint: Pubkey, get_units: int, blockhash: Hash) -> Message:
    """Burn `pay_units` of her `pay_mint`, mint `get_units` of `get_mint` to her. Buy: pay dUSD, get stock.
    Sell: the mirror. The vault pays the fee and the rent for her token account if it's missing."""
    return Message.new_with_blockhash([
        create_idempotent_associated_token_account(vault_key, owner, get_mint),
        burn(BurnParams(program_id=TOKEN_PROGRAM_ID, account=get_associated_token_address(owner, pay_mint),
                        mint=pay_mint, owner=owner, amount=pay_units)),
        _mint_ix(vault_key, get_mint, owner, get_units),
    ], vault_key, blockhash)


def unsigned_tx(message: Message) -> bytes:
    """What /trade/quote hands the front-end as tx_base64 (after base64)."""
    return bytes(Transaction.new_unsigned(message))


async def cosign_and_send(rpc: AsyncClient, vault_kp: Keypair, signed_tx: bytes, expected: Message) -> Signature:
    """/trade/submit: refuse anything but the quoted message, add the vault's signature, send, wait for confirmed."""
    tx = Transaction.from_bytes(signed_tx)
    if bytes(tx.message) != bytes(expected):
        raise ValueError("signed transaction does not match the quote")
    tx.partial_sign([vault_kp], tx.message.recent_blockhash)
    tx.verify()  # raises if her signature is missing or wrong
    sig = (await rpc.send_raw_transaction(bytes(tx))).value
    await rpc.confirm_transaction(sig, Confirmed, sleep_seconds=POLL_S)
    return sig


async def faucet(rpc: AsyncClient, vault_kp: Keypair, dusd: Pubkey, owner: Pubkey, units: int) -> Signature:
    """Mints dUSD to her. Only the vault signs, so she needs no SOL."""
    blockhash = (await rpc.get_latest_blockhash()).value.blockhash
    tx = Transaction.new_signed_with_payer([
        create_idempotent_associated_token_account(vault_kp.pubkey(), owner, dusd),
        _mint_ix(vault_kp.pubkey(), dusd, owner, units),
    ], vault_kp.pubkey(), [vault_kp], blockhash)
    sig = (await rpc.send_raw_transaction(bytes(tx))).value
    await rpc.confirm_transaction(sig, Confirmed, sleep_seconds=POLL_S)
    return sig
