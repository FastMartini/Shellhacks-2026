"""One-time devnet setup (BUILD_SPEC.md → Vault → Setup checklist). Safe to re-run: it only creates what's missing.

1. Vault keypair at keys/vault-keypair.json (git-ignored). Share it with the team privately.
2. Devnet SOL for the vault, by airdrop. If the airdrop is rate-limited, paste the vault address into
   faucet.solana.com and re-run.
3. dUSD + one mint per stock, 6 decimals, vault as mint authority, written to mints.json (committed).

Run from backend/:  ./venv/bin/python -m scripts.setup_devnet
"""

import asyncio
import json

from solana.rpc.commitment import Confirmed
from solders.keypair import Keypair
from solders.system_program import CreateAccountParams, create_account
from solders.transaction import Transaction
from spl.token.constants import MINT_LEN, TOKEN_PROGRAM_ID
from spl.token.instructions import initialize_mint
from spl.token.models import InitializeMintParams

from app import chain, config

LAMPORTS_PER_SOL = 1_000_000_000


async def fund(rpc, vault: Keypair) -> None:
    balance = (await rpc.get_balance(vault.pubkey())).value
    if balance >= LAMPORTS_PER_SOL // 2:
        print(f"vault balance {balance / LAMPORTS_PER_SOL} SOL")
        return
    try:
        sig = (await rpc.request_airdrop(vault.pubkey(), 2 * LAMPORTS_PER_SOL)).value
        await rpc.confirm_transaction(sig, Confirmed, sleep_seconds=chain.POLL_S)
        print("airdropped 2 SOL to the vault")
    except Exception as e:
        raise SystemExit(f"Airdrop failed ({e}). Fund {vault.pubkey()} at faucet.solana.com, then re-run.")


async def create_mint(rpc, vault: Keypair) -> str:
    mint = Keypair()
    rent = (await rpc.get_minimum_balance_for_rent_exemption(MINT_LEN)).value
    blockhash = (await rpc.get_latest_blockhash()).value.blockhash
    tx = Transaction.new_signed_with_payer([
        create_account(CreateAccountParams(from_pubkey=vault.pubkey(), to_pubkey=mint.pubkey(), lamports=rent,
                                           space=MINT_LEN, owner=TOKEN_PROGRAM_ID)),
        initialize_mint(InitializeMintParams(decimals=6, program_id=TOKEN_PROGRAM_ID, mint=mint.pubkey(),
                                             mint_authority=vault.pubkey())),
    ], vault.pubkey(), [vault, mint], blockhash)
    await rpc.confirm_transaction((await rpc.send_raw_transaction(bytes(tx))).value, Confirmed,
                                  sleep_seconds=chain.POLL_S)
    return str(mint.pubkey())


async def main() -> None:
    if not chain.VAULT_KEYPAIR.exists():
        chain.save_keypair(Keypair(), chain.VAULT_KEYPAIR)
        print(f"created {chain.VAULT_KEYPAIR}")
    vault = chain.vault()
    print(f"vault {vault.pubkey()}")

    existing = json.loads(chain.MINTS_PATH.read_text()) if chain.MINTS_PATH.exists() else {}
    async with chain.client() as rpc:
        await fund(rpc, vault)
        for name in ["dUSD", *config.SYMBOLS]:
            if name not in existing:
                existing[name] = await create_mint(rpc, vault)
                chain.MINTS_PATH.write_text(json.dumps(existing, indent=2) + "\n")  # after each, so a crash resumes
                print(f"{name} mint {existing[name]}")
    print(f"mints.json has {len(existing)} mints")


if __name__ == "__main__":
    asyncio.run(main())
