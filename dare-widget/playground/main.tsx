/**
 * Playground entry — renders the REAL <DareWidget> against the REAL local
 * backend (uvicorn dare.api:app on :8000). Clicking "Explain this answer" now
 * makes a genuine POST to /attribute — there is no mock. It uses the sample
 * record's own query/answer/chunks as the inputs.
 *
 * Requires: the backend running on :8000, and "http://localhost:5173" added to
 * api.py's CORS allow_origins (otherwise the browser blocks the response).
 */

import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { DareWidget } from "../src";
import { SAMPLE } from "./sample";

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
        <b>Q:</b> {SAMPLE.query}
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
        {SAMPLE.response}
      </div>

      <DareWidget
        apiUrl="http://localhost:8000"
        query={SAMPLE.query}
        answer={SAMPLE.response}
        chunks={SAMPLE.whole_chunk_attributions.map((c) => ({
          content: c.chunk_text,
          chunk_id: c.chunk_id,
          document_id: c.doc_id,
          score: c.retrieval_score,
        }))}
      />
    </div>
  </StrictMode>,
);
