/**
 * Playground entry — renders the REAL <DareWidget> against the REAL local
 * backend (uvicorn dare.api:app on :8000). Clicking "Explain this answer" makes
 * a genuine POST to /attribute — there is no mock.
 *
 * Inputs are the REAL qa-0164 record in its VIETNAMESE original (playground/
 * inputs.ts) — the text the model actually generated — so attribution runs on
 * the real answer, not the English gloss in sample.ts.
 *
 * Requires: the backend running on :8000, and "http://localhost:5173" added to
 * api.py's CORS allow_origins (otherwise the browser blocks the response).
 */

import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { DareWidget } from "../src";
import { QUERY, ANSWER, CHUNKS } from "./inputs";

const page: React.CSSProperties = {
  maxWidth: 1120,
  margin: "40px auto",
  padding: "0 20px",
  fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Arial, sans-serif",
  color: "#1f2328",
};

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <div style={page}>
      <h1 style={{ fontSize: 20 }}>dare-widget playground</h1>
      <p style={{ color: "#656d76" }}>
        A simulated RAG turn. The answer below is the host app's; the widget under it is the drop-in.
        Click <b>Explain this answer</b>.
      </p>

      <div style={{ fontSize: 13, color: "#656d76", marginBottom: 4 }}>
        <b>Q:</b> {QUERY}
      </div>
      <div
        style={{
          border: "1px solid #d0d7de",
          borderRadius: 12,
          padding: 16,
          marginBottom: 16,
          whiteSpace: "pre-wrap",
          background: "#fff",
        }}
      >
        {ANSWER}
      </div>

      <DareWidget
        apiUrl="http://localhost:8000"
        query={QUERY}
        answer={ANSWER}
        chunks={CHUNKS}
      />
    </div>
  </StrictMode>,
);
