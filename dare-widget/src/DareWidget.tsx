/**
 * DareWidget — the single component a host app imports and drops in.
 *
 * It is the WHOLE widget, not just a button: the trigger is only its idle state.
 * The component walks the request lifecycle (idle → loading → error / loaded)
 * via the useAttribution hook, and once loaded renders the two-column
 * AttributionView. All of it lives inside a Shadow DOM so the host page's CSS
 * can't reach in and ours can't leak out — the drop-in isolation promise.
 *
 *   import { DareWidget } from "dare-widget";
 *   <DareWidget apiUrl="https://dare.host" query={q} answer={a} chunks={ks} />
 */

import { useEffect, useRef, useState } from "react";
import type { ReactNode } from "react";
import { createPortal } from "react-dom";

import { AttributionView } from "./AttributionView";
import type { Calibration } from "./AttributionView";
import { STYLES } from "./styles";
import type { DareChunk } from "./types";
import { useAttribution } from "./useAttribution";

/**
 * Mounts `children` inside a shadow root on a host <div>, with the stylesheet
 * injected once. React events still work across the portal (React propagates
 * through its own tree, not the DOM tree), so clicks inside the shadow root
 * reach our handlers normally.
 */
function ShadowHost({ children }: { children: ReactNode }) {
  const hostRef = useRef<HTMLDivElement>(null);
  const [root, setRoot] = useState<ShadowRoot | null>(null);

  useEffect(() => {
    const host = hostRef.current;
    if (host && !root) {
      // Reuse an existing root if one is already attached (StrictMode re-runs
      // effects; attachShadow twice would throw).
      setRoot(host.shadowRoot ?? host.attachShadow({ mode: "open" }));
    }
  }, [root]);

  return (
    <div ref={hostRef}>
      {root &&
        createPortal(
          <>
            <style>{STYLES}</style>
            {children}
          </>,
          root,
        )}
    </div>
  );
}

export interface DareWidgetProps {
  /** Base URL of the DARE backend, e.g. "https://dare.yourhost.com". */
  apiUrl: string;
  /** The user's question. */
  query: string;
  /** The RAG answer to attribute. */
  answer: string;
  /** The retrieved chunks — pass the RAG response's `knowledge_sources` as-is. */
  chunks: DareChunk[];
  /** Override the provisional bucket/shade thresholds (see DEFAULT_CALIBRATION). */
  calibration?: Calibration;
}

export function DareWidget({ apiUrl, query, answer, chunks, calibration }: DareWidgetProps) {
  const { status, summary, error, run, reset } = useAttribution({ apiUrl, query, answer, chunks });

  return (
    <ShadowHost>
      <div className="card">
        {status === "idle" && (
          <button className="trigger" onClick={run}>
            Explain this answer
          </button>
        )}

        {status === "loading" && (
          <div className="status">
            <span className="spinner" />
            Attributing this answer to its sources… this can take a little while.
          </div>
        )}

        {status === "error" && (
          <div className="error">
            Couldn't attribute this answer: {error?.detail ?? error?.message ?? "unknown error"}
            <div>
              <button onClick={run}>Try again</button>
            </div>
          </div>
        )}

        {status === "loaded" && summary && (
          <>
            <div className="wm-head">
              <span className="wm-title">Answer attribution</span>
              <button className="drawer-close" onClick={reset} title="Hide" aria-label="Hide">
                ✕
              </button>
            </div>
            <AttributionView summary={summary} calibration={calibration} />
            <div className="footer">Descriptive attribution, relative to this answer · powered by DARE</div>
          </>
        )}
      </div>
    </ShadowHost>
  );
}
