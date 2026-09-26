import { ConnectionProvider, WalletProvider } from "@solana/wallet-adapter-react";
import { WalletModalProvider } from "@solana/wallet-adapter-react-ui";
import type { PropsWithChildren } from "react";
import "@solana/wallet-adapter-react-ui/styles.css";

const endpoint = import.meta.env.VITE_SOLANA_RPC_URL ?? "https://api.devnet.solana.com";

export function SolanaProvider({ children }: PropsWithChildren) {
  return <ConnectionProvider endpoint={endpoint}><WalletProvider wallets={[]} autoConnect><WalletModalProvider>{children}</WalletModalProvider></WalletProvider></ConnectionProvider>;
}
