import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import App from "./App";
import { SolanaProvider } from "./providers/SolanaProvider";
import "./styles.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <SolanaProvider><App /></SolanaProvider>
  </StrictMode>,
);
