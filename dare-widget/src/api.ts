/**
 * The network client — the only module in the widget that touches the wire.
 *
 * One function, `attribute()`, POSTs to the DARE backend's `/attribute`
 * endpoint (dare/api.py) and returns a typed `RecordSummary`. All HTTP concerns
 * live here: URL assembly, JSON encoding, and mapping a failed response onto a
 * thrown `DareApiError`. The React layer never sees `fetch`, status codes, or
 * URLs — it just awaits this and gets a typed object or a typed error.
 *
 * This runs in the browser, cross-origin to the DARE host, so the request is
 * governed by the server's CORS config (api.py's `allow_origins`). This module
 * doesn't configure CORS — it just makes the request CORS decides to allow.
 */

import type { AttributeRequest, DareChunk, RecordSummary } from "./types";

/**
 * A failed `/attribute` call. `status` is the HTTP code when the server
 * answered (e.g. 400 "at least one chunk is required", 502 "attribution
 * failed"), or 0 when the request never completed (network error, DNS, CORS
 * block, or an aborted call). `detail` carries the server's own message when we
 * could parse one, so the UI can show why it failed.
 */
export class DareApiError extends Error {
  readonly status: number;
  readonly detail?: string;

  constructor(message: string, status: number, detail?: string) {
    super(message);
    this.name = "DareApiError";
    this.status = status;
    this.detail = detail;
  }
}

export interface AttributeOptions {
  /** Base URL of the DARE backend, e.g. "https://dare.yourhost.com".
   *  `/attribute` is appended; a trailing slash is fine. */
  apiUrl: string;
  query: string;
  answer: string;
  chunks: DareChunk[];
  /** Optional cancellation, so a caller can abort the (slow) request when the
   *  component unmounts or the user navigates away. */
  signal?: AbortSignal;
}

/** Pull FastAPI's error message out of a response body, tolerating its two
 *  shapes: a plain `{detail: "..."}` (HTTPException) and the `{detail: [...]}`
 *  array of a 422 validation error. Returns undefined if the body isn't the
 *  shape we expect, so a weird body never masks the status code. */
async function readErrorDetail(res: Response): Promise<string | undefined> {
  try {
    const body = (await res.json()) as { detail?: unknown };
    const detail = body?.detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail)) {
      // 422: array of {loc, msg, ...}. Join the human-readable messages.
      return detail
        .map((d) => (d && typeof d === "object" && "msg" in d ? String((d as { msg: unknown }).msg) : String(d)))
        .join("; ");
    }
  } catch {
    // Body wasn't JSON (e.g. an HTML error page or empty body); fall through.
  }
  return undefined;
}

/**
 * Attribute one RAG answer to its retrieved context.
 *
 * Sends `{query, answer, chunks}` to `${apiUrl}/attribute` and resolves to the
 * `RecordSummary` the backend computes. Rejects with a `DareApiError` on any
 * non-2xx response (carrying the server's detail) or on a transport failure.
 */
export async function attribute(opts: AttributeOptions): Promise<RecordSummary> {
  const { apiUrl, query, answer, chunks, signal } = opts;

  // Trim any trailing slashes so "https://host/" and "https://host" both work.
  const url = `${apiUrl.replace(/\/+$/, "")}/attribute`;
  const payload: AttributeRequest = { query, answer, chunks };

  let res: Response;
  try {
    res = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
      signal,
    });
  } catch (err) {
    // fetch only rejects on transport-level failures: network down, DNS,
    // aborted request, or a CORS block. status 0 flags "never got a response".
    if (err instanceof DOMException && err.name === "AbortError") {
      throw new DareApiError("attribution request was cancelled", 0);
    }
    throw new DareApiError(
      "could not reach the DARE server (network error, or CORS blocked the response)",
      0,
    );
  }

  if (!res.ok) {
    const detail = await readErrorDetail(res);
    throw new DareApiError(
      detail ?? `attribution failed (HTTP ${res.status})`,
      res.status,
      detail,
    );
  }

  return (await res.json()) as RecordSummary;
}
