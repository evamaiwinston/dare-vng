/**
 * Playground entry — renders the REAL <DareWidget> in one of two modes, set by
 * the USE_MOCK toggle below:
 *
 *   USE_MOCK = true  → OFFLINE. Intercepts POST /attribute and returns the
 *     bundled SAMPLE (English qa-0164) after a short delay, so the whole widget
 *     (button → loading → view) works with NO backend and NO model. Use this for
 *     UI development and demos, and whenever the model endpoint is unavailable.
 *
 *   USE_MOCK = false → LIVE. POSTs the real qa-0164 record in its VIETNAMESE
 *     original (playground/inputs.ts) to the backend on :8000, so attribution
 *     runs on the real text. Requires: uvicorn dare.api:app on :8000, and
 *     "http://localhost:5173" in api.py's CORS allow_origins.
 */

import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { DareWidget } from "../src";
import { QUERY, ANSWER, CHUNKS } from "./inputs";
import { SAMPLE } from "./sample";

// ── Toggle ────────────────────────────────────────────────────────────────
const USE_MOCK = true; // true = offline mock (SAMPLE), false = live backend
const API_URL = "http://localhost:8000";

// Active inputs: the bundled SAMPLE (English) offline, the real Vietnamese
// record live. In mock mode the intercepted fetch ignores the body, so these
// only drive the on-page Q/A display; live, they are what gets POSTed.
const query = USE_MOCK ? SAMPLE.query : QUERY;
const answer = USE_MOCK ? SAMPLE.response : ANSWER;
const chunks = USE_MOCK
  ? SAMPLE.whole_chunk_attributions.map((c) => ({
      content: c.chunk_text,
      chunk_id: c.chunk_id,
      document_id: c.doc_id,
      score: c.retrieval_score,
    }))
  : CHUNKS;

// Mock mode: intercept POST .../attribute and return SAMPLE after a short fake
// delay (so you still see button → loading → shadow-DOM'd view). Every other
// request passes through. This exercises the real component code, just with a
// canned response instead of the network.
if (USE_MOCK) {
  const realFetch = window.fetch.bind(window);
  window.fetch = async (input: RequestInfo | URL, init?: RequestInit): Promise<Response> => {
    const url = typeof input === "string" ? input : input instanceof URL ? input.href : input.url;
    if (url.endsWith("/attribute") && (init?.method ?? "GET").toUpperCase() === "POST") {
      await new Promise((r) => setTimeout(r, 900)); // simulate attribution latency
      return new Response(JSON.stringify(SAMPLE), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }
    return realFetch(input, init);
  };
}

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
      <h1 style={{ fontSize: 20 }}>
        dare-widget playground <span style={{ color: "#656d76", fontSize: 14 }}>({USE_MOCK ? "mock" : "live"})</span>
      </h1>
      <p style={{ color: "#656d76" }}>
        A simulated RAG turn. The answer below is the host app's; the widget under it is the drop-in.
        Click <b>Explain this answer</b>.
      </p>

      <div style={{ fontSize: 13, color: "#656d76", marginBottom: 4 }}>
        <b>Q:</b> {query}
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
        {answer}
      </div>

      <DareWidget apiUrl={API_URL} query={query} answer={answer} chunks={chunks} />
    </div>
  </StrictMode>,
);
