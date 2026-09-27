import { ApiRequestError, apiRequest } from "./client";
import type { TransactionRow } from "./types";

// A submit lands or its blockhash lapses within about 90 s of the quote (spec section 3). After that the backend can
// say for sure whether the trade went through, so keep resubmitting until then, with some margin.
const SUBMIT_WINDOW_MS = 120_000;
const SUBMIT_RETRY_MS = 2_000;
const UNKNOWN_OUTCOME = "Still no answer after 2 minutes, so we can't tell whether this trade went through. Check your balances in Phantom before you trade again.";

// The trade may have landed: devnet stopped answering, the same quote is still being sent, or the backend's reply
// was lost (fetch throws a TypeError).
function mayHaveLanded(error: unknown) {
  return error instanceof TypeError
    || (error instanceof ApiRequestError && (error.code === "chain_unavailable" || error.code === "submit_in_progress"));
}

// Posts a signed quote. While the trade may have landed it submits the same quote again, never a new one: the backend
// checks whether it went through, so this can't trade twice. Anything else is thrown as is.
export async function submitSignedTrade(quoteId: string, signedTxBase64: string): Promise<TransactionRow> {
  const body = JSON.stringify({ quote_id: quoteId, signed_tx_base64: signedTxBase64 });
  const deadline = Date.now() + SUBMIT_WINDOW_MS;
  for (;;) {
    try {
      return await apiRequest<TransactionRow>("/trade/submit", { method: "POST", body });
    } catch (requestError) {
      if (!mayHaveLanded(requestError)) throw requestError;
      if (Date.now() >= deadline) throw new Error(UNKNOWN_OUTCOME);
      await new Promise((resolve) => setTimeout(resolve, SUBMIT_RETRY_MS));
    }
  }
}
