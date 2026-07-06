/**
 * The state machine behind the widget's one network call.
 *
 * `api.ts` gives us a one-shot promise; this hook turns that into React state a
 * component can render: which of `idle | loading | loaded | error` we're in,
 * the `RecordSummary` once we have it, and the error if we don't. It also owns
 * the lifecycle-safety that a slow request needs — aborting an in-flight call
 * and never setting state after the component has unmounted.
 *
 * The component that uses this stays purely presentational: it reads `status`
 * and draws, and calls `run()` / `reset()`. No fetch, no promises, no cleanup
 * logic leaks into the JSX.
 */

import { useCallback, useEffect, useRef, useState } from "react";

import { attribute, DareApiError } from "./api";
import type { DareChunk, RecordSummary } from "./types";

export type AttributionStatus = "idle" | "loading" | "loaded" | "error";

/** The inputs the request is built from — the same three fields the host passes
 *  as props, forwarded straight through to `attribute()`. */
export interface UseAttributionInput {
  apiUrl: string;
  query: string;
  answer: string;
  chunks: DareChunk[];
}

export interface UseAttributionResult {
  status: AttributionStatus;
  summary: RecordSummary | null;
  error: DareApiError | null;
  /** Fire the (slow) attribution request. Ignored while already loading. */
  run: () => void;
  /** Return to idle and drop any result/error (e.g. to re-run). */
  reset: () => void;
}

export function useAttribution(input: UseAttributionInput): UseAttributionResult {
  const { apiUrl, query, answer, chunks } = input;

  const [status, setStatus] = useState<AttributionStatus>("idle");
  const [summary, setSummary] = useState<RecordSummary | null>(null);
  const [error, setError] = useState<DareApiError | null>(null);

  // Tracks whether this component is still mounted, so an async callback that
  // resolves after unmount doesn't call setState on a dead component (React
  // warns, and it's a memory leak). Flipped false by the cleanup below.
  const mountedRef = useRef(true);
  // The controller for the in-flight request, so we can abort it on unmount or
  // when a fresh run() supersedes it. null when no request is active.
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      // Component is going away mid-flight — cancel the request so it doesn't
      // linger; api.ts turns this into a (swallowed) AbortError.
      abortRef.current?.abort();
    };
  }, []);

  const run = useCallback(() => {
    // Guard: a second click while a request is already running is a no-op, so
    // we never fire two overlapping attributions from one widget.
    if (abortRef.current) return;

    const controller = new AbortController();
    abortRef.current = controller;
    setStatus("loading");
    setError(null);
    setSummary(null);

    attribute({ apiUrl, query, answer, chunks, signal: controller.signal })
      .then((result) => {
        if (!mountedRef.current || controller.signal.aborted) return;
        setSummary(result);
        setStatus("loaded");
      })
      .catch((err: unknown) => {
        // An abort is an intentional cancellation, not a failure to show.
        if (controller.signal.aborted || !mountedRef.current) return;
        setError(
          err instanceof DareApiError
            ? err
            : new DareApiError("unexpected error running attribution", 0),
        );
        setStatus("error");
      })
      .finally(() => {
        // Clear the active-request marker only if it's still ours (a later
        // run() may have replaced it), so run()'s guard reflects reality.
        if (abortRef.current === controller) abortRef.current = null;
      });
  }, [apiUrl, query, answer, chunks]);

  const reset = useCallback(() => {
    abortRef.current?.abort();
    abortRef.current = null;
    setStatus("idle");
    setSummary(null);
    setError(null);
  }, []);

  return { status, summary, error, run, reset };
}
