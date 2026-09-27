"""The demo wallet Sofía uses on stage (BUILD_SPEC.md → Vault → Demo wallet and seed data).

One keypair at keys/demo-wallet.json (git-ignored), made with solana-keygen and imported into Phantom, so
seed_demo.py pre-runs the scripted trades with the same key she then uses live. Devnet only: it only ever
holds our test tokens, and it needs no SOL because the vault pays every fee.

Run from backend/:
    ./venv/bin/python -m scripts.demo_wallet            # make it if missing, print its address
    ./venv/bin/python -m scripts.demo_wallet --phantom  # also print the private key for Phantom's import
    ./venv/bin/python -m scripts.demo_wallet --new      # a fresh keypair for a rehearsal (the old one is kept)

Phantom: Testnet Mode on (Settings → Developer Settings), then Add / Connect Wallet → Import Private Key and
paste the --phantom output. After --new, import the new key the same way.
"""

import argparse
import shutil
import subprocess
from datetime import datetime

from solders.keypair import Keypair

from app import chain

DEMO_WALLET = chain.BACKEND / "keys" / "demo-wallet.json"


def create() -> None:
    """solana-keygen writes the same JSON byte array chain.save_keypair does; fall back to it without the CLI."""
    DEMO_WALLET.parent.mkdir(parents=True, exist_ok=True)
    try:
        subprocess.run(["solana-keygen", "new", "--no-bip39-passphrase", "--silent", "--outfile", str(DEMO_WALLET)],
                       check=True)
        DEMO_WALLET.chmod(0o600)
    except FileNotFoundError:
        chain.save_keypair(Keypair(), DEMO_WALLET)
    print(f"created {DEMO_WALLET}")


def load() -> Keypair:
    if not DEMO_WALLET.exists():
        raise SystemExit(f"No demo wallet at {DEMO_WALLET}. Run: ./venv/bin/python -m scripts.demo_wallet")
    return chain.load_keypair(DEMO_WALLET)


def main() -> None:
    parser = argparse.ArgumentParser(description=(__doc__ or "").split("\n\n")[0])
    parser.add_argument("--new", action="store_true", help="replace it with a fresh keypair, keeping the old file")
    parser.add_argument("--phantom", action="store_true", help="print the private key for Phantom's import")
    args = parser.parse_args()

    if args.new and DEMO_WALLET.exists():
        kept = DEMO_WALLET.with_name(f"demo-wallet-{datetime.now():%Y%m%d-%H%M%S}.json")
        shutil.move(DEMO_WALLET, kept)
        print(f"kept the old one as {kept.name}")
    if not DEMO_WALLET.exists():
        create()

    kp = load()
    print(f"demo wallet {kp.pubkey()}")
    if args.phantom:
        print(f"Phantom → Import Private Key (devnet test key; don't share it outside the team):\n{kp}")


if __name__ == "__main__":
    main()
