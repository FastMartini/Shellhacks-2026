"""6 PM checkpoint test run, headless half: one hard-coded buy of 1 AKAM through the real quote → sign → submit
path on devnet. A local keypair stands in for Phantom and signs first; the vault co-signs and sends.

This proves the transaction lands. Whether Phantom shows a warning still needs the browser check.

Run from backend/ after setup_devnet:  ./venv/bin/python -m scripts.vault_test_run
"""

import asyncio

from solders.keypair import Keypair
from solders.transaction import Transaction
from spl.token.instructions import get_associated_token_address

from app import chain, config
from app.chain import BACKEND

DEMO_WALLET = BACKEND / "keys" / "demo-wallet.json"
PRICE = 116.00  # hard-coded for the test; /trade/quote will use price_at
QTY_UNITS = 1 * config.UNITS
USD_UNITS = round(PRICE * config.UNITS)


async def balance(rpc, owner, mint) -> float:
    resp = await rpc.get_token_account_balance(get_associated_token_address(owner, mint))
    return float(resp.value.ui_amount_string)


async def main() -> None:
    if not DEMO_WALLET.exists():
        chain.save_keypair(Keypair(), DEMO_WALLET)
    sofia, vault, mints = chain.load_keypair(DEMO_WALLET), chain.vault(), chain.mints()
    print(f"demo wallet {sofia.pubkey()} (holds no SOL)")

    async with chain.client() as rpc:
        sig = await chain.faucet(rpc, vault, mints["dUSD"], sofia.pubkey(), 1000 * config.UNITS)
        print(f"faucet  {explorer(sig)}")

        # /trade/quote: unsigned legacy tx, vault as fee payer, fresh blockhash; keep the message for the check
        # and the blockhash's last valid height for the confirm.
        latest = (await rpc.get_latest_blockhash()).value
        message = chain.swap_message(vault.pubkey(), sofia.pubkey(), mints["dUSD"], USD_UNITS,
                                     mints["AKAM"], QTY_UNITS, latest.blockhash)
        unsigned = chain.unsigned_tx(message)

        # Front-end: she signs first (Phantom's signTransaction), serialized without the vault's signature.
        tx = Transaction.from_bytes(unsigned)
        tx.partial_sign([sofia], latest.blockhash)

        # /trade/submit
        sig = await chain.cosign_and_send(rpc, vault, bytes(tx), message,
                                          last_valid_block_height=latest.last_valid_block_height)
        print(f"buy     {explorer(sig)}")
        print(f"balances: {await balance(rpc, sofia.pubkey(), mints['dUSD'])} dUSD, "
              f"{await balance(rpc, sofia.pubkey(), mints['AKAM'])} AKAM")


def explorer(sig) -> str:
    return f"https://explorer.solana.com/tx/{sig}?cluster=devnet"


if __name__ == "__main__":
    asyncio.run(main())
