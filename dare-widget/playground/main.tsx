/**
 * Playground entry — renders the REAL <DareWidget> against a MOCKED backend, so
 * you see the true end-to-end flow (button → loading → shadow-DOM'd view) with
 * no server. We intercept `fetch` for POST .../attribute and return the bundled
 * sample RecordSummary after a short fake delay; every other request passes
 * through. This exercises the actual component code in src/, not a mockup.
 */

import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { DareWidget } from "../src";
import { SAMPLE } from "./sample";

const realFetch = window.fetch.bind(window);
window.fetch = async (input: RequestInfo | URL, init?: RequestInit): Promise<Response> => {
  const url = typeof input === "string" ? input : input instanceof URL ? input.href : input.url;
  if (url.endsWith("/attribute") && (init?.method ?? "GET").toUpperCase() === "POST") {
    await new Promise((r) => setTimeout(r, 1200)); // simulate attribution latency
    return new Response(JSON.stringify(SAMPLE), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  }
  return realFetch(input, init);
};

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
        apiUrl="https://mock.local"
        query={SAMPLE.query}
        answer={SAMPLE.response}
        chunks={[{ content: "(mocked — the intercepted fetch ignores the body)" }]}
      />
    </div>
  </StrictMode>,
);
