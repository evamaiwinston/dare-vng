# Target endpoint response — mock JSON of everything I need

One mock `response` object showing the **ideal** payload for attribution: what the endpoint sends **today**, plus the fields that must be **added**. Inline tags on every field:

- `// [HAVE]` — endpoint already returns this
- `// [ENHANCE]` — field exists but needs more in it
- `// [NEW]` — **not sent today; must be added** (the asks)

Values use the taxi-allowance example (`qa-luongvh-0001`) for realism.

```jsonc
{
  "answer": "Nhân viên VNG cấp bậc 4.2 được hưởng định mức hỗ trợ taxi tối đa 4.500.000 đồng/tháng.", // [HAVE]
  "answer_via_tool": true,            // [HAVE]
  "mode": "agent",                    // [HAVE]
  "session_id": "sess_8f21…",         // [HAVE]
  "ablation": {                       // [HAVE] retrieval config flags
    "use_memory": false,
    "use_graph_rag": true
  },
  "usage": {                          // [HAVE]
    "llm_calls": 5, "input_tokens": 5391, "output_tokens": 496, "total_tokens": 5887
  },
  "total_step_time": 25.082,          // [HAVE]
  "step_timings": [                   // [HAVE]
    { "step": 1, "kind": "llm", "name": "agent", "elapsed": 1.502 }
  ],
  "tools_used": ["search_knowledge", "generate_answer"], // [HAVE]

  // ─────────────────────────────────────────────────────────────────────
  // FINAL GENERATION — the single biggest gap. Today this lives ONLY in the
  // offline report's `llm_trace`; the endpoint sends nothing. This is exactly
  // what the model was fed + produced. THIS is the attributable unit.
  // ─────────────────────────────────────────────────────────────────────
  "final_generation": {               // [NEW]
    "model": "local-model-mini",      // [NEW]
    "messages": [                     // [NEW] the literal input, in order
      { "role": "system", "content": "Bạn là trợ lý tổng hợp câu trả lời cuối cùng. …" },
      { "role": "human",  "content": "Câu hỏi: …\n\nBằng chứng:\n[1] …\n[2] …" }
    ],
    "response": "Nhân viên VNG cấp bậc 4.2 …", // [NEW] raw model output (== answer)
    "evidence_order": ["204adf0f…", "921fe465…"] // [NEW] chunk_id per [i] block, in prompt order
  },

  // ─────────────────────────────────────────────────────────────────────
  // SOURCES — what the generator actually saw. Keep ONE authoritative list
  // (we verified `sources` == the [1..N] evidence). Add per-chunk PROVENANCE.
  // ─────────────────────────────────────────────────────────────────────
  "sources": [                        // [HAVE] + [NEW] provenance fields
    {
      "chunk_id": "204adf0ff219c60f…",        // [HAVE]
      "document_id": "doc_a2734411efe0bd06",  // [HAVE]
      "score": 2.140087,                      // [HAVE] retrieval score
      "content": "## 2.3. Đối tượng sử dụng và định mức hàng tháng …", // [HAVE]
      "used_in_generation": true,             // [NEW] did it reach final_generation?
      "provenance": [                         // [NEW] HOW this chunk was surfaced
        {
          "route": "triple",                  // chunk | entity | triple | community
          "seed_id": "trip_5f0a…",            // stable KG id of the seed
          "triple": { "subject": "Định mức hỗ trợ taxi cấp 4.2", "relation": "applies_to", "object": "4,500,000 VND/tháng" },
          "path": [                           // edges walked to reach this chunk
            { "src_node": "ent_4_2", "relation": "applies_to", "dst_node": "amt_4500000", "hop": 1 },
            { "src_node": "amt_4500000", "relation": "mentioned_in", "dst_node": "204adf0f…", "hop": 2 }
          ],
          "hop": 2,
          "score": 0.91
        }
      ]
    }
  ],

  "knowledge_sources": [              // [HAVE] retrieved superset (pre-selection)
    { "chunk_id": "3ad8b4ca…", "document_id": "doc_…", "score": 1.83, "content": "…",
      "used_in_generation": false }  // [NEW] flag so we can tell retrieved-but-unused
  ],
  "memory_sources": [],              // [HAVE]

  // ─────────────────────────────────────────────────────────────────────
  // AGENT TRACE — reconstructable control flow + the prompts. Today the
  // endpoint sends only a flat `reasoning_trace` of actions, no prompts.
  // ─────────────────────────────────────────────────────────────────────
  "agent_trace": [                    // [ENHANCE] of today's reasoning_trace
    {
      "step": 1,                      // [HAVE]
      "parent_step": null,            // [NEW] for the control-flow DAG
      "agent_id": "router",           // [NEW] which agent acted
      "agent_role": "retrieval_planner", // [NEW]
      "tool": "search_knowledge",     // [HAVE]
      "prompt": [                     // [NEW] this step's actual LLM input
        { "role": "system", "content": "…agent system prompt…" },
        { "role": "human",  "content": "…" }
      ],
      "tool_calls": [                 // [NEW] structured calls the model emitted
        { "name": "search_knowledge", "args": { "query": "định mức hỗ trợ taxi cấp bậc 4.2" } }
      ],
      "emitted_keywords": ["định mức", "taxi", "cấp bậc 4.2"], // [NEW] explicit
      "result": {                     // [ENHANCE] structured, not a truncated string
        "chunk_ids": ["204adf0f…"],   // chunk_ids ACTUALLY used (reliable, not the request)
        "n_hits": 10
      },
      "handoff": null                 // [NEW] { "from": "router", "to": "synthesizer", "reason": "…" }
    }
  ],

  // ─────────────────────────────────────────────────────────────────────
  // RETRIEVAL DETAIL — biggest mechanical gaps: graph routes carry no ids/
  // chunk links, and traversal is counts-only with no shape.
  // ─────────────────────────────────────────────────────────────────────
  "retrieval_detail": {
    "sub_questions": [
      {
        "q": "Định mức hỗ trợ taxi cho nhân viên cấp bậc 4.2 là bao nhiêu?", // [HAVE]
        "embed_elapsed": 7.795,        // [HAVE]
        "emitted_keywords": ["định mức hỗ trợ taxi", "cấp bậc 4.2"], // [NEW] terms → routes
        "routes": {
          "chunk": {                   // [HAVE] already good
            "elapsed": 0.022, "hits": 10,
            "results": [               // [ENHANCE] add per-chunk score (was id-only)
              { "chunk_id": "3ad8b4ca…", "score": 1.88 }
            ]
          },
          "entity": {                  // [ENHANCE] today: only seed strings
            "elapsed": 0.022, "hits": 10, "type_filter": ["amount"],
            "matches": [               // [NEW] ids + score + resolved chunks
              { "entity_id": "ent_4_2", "name": "4,500,000 VND/tháng", "score": 0.88,
                "resolved_chunk_ids": ["204adf0f…"] }
            ]
          },
          "triple": {                  // [ENHANCE] today: only seed strings
            "elapsed": 0.024, "hits": 10, "type_filter": ["applies_to"],
            "matches": [               // [NEW] the field that lets you ISOLATE triples
              { "triple_id": "trip_5f0a…",
                "subject": "Định mức hỗ trợ taxi cấp 4.2", "relation": "applies_to", "object": "4,500,000 VND/tháng",
                "score": 0.91, "resolved_chunk_ids": ["204adf0f…"] }
            ]
          },
          "community": {               // [ENHANCE] today: only seed strings
            "elapsed": 0.004, "hits": 3,
            "matches": [               // [NEW]
              { "community_id": "comm_12", "name": "Hỗ trợ chi phí", "score": 0.40,
                "resolved_chunk_ids": ["921fe465…"] }
            ]
          }
        }
      }
    ],

    "path_traversal": {                // [ENHANCE] today: counts only
      "elapsed": 2.336,
      "seed_count": 335,               // [HAVE] keep counts
      "expanded_nodes": 335,           // [HAVE]
      "graph_chunks_count": 197,       // [HAVE] keep as a count
      "inv_rels_filter": ["applies_to"], // [HAVE]
      "seeds": [                       // [NEW] which route each seed came from
        { "seed_id": "trip_5f0a…", "from_route": "triple" }
      ],
      "edges": [                       // [NEW] the actual graph walk (THE shape)
        { "src_node": "ent_4_2", "relation": "applies_to", "dst_node": "amt_4500000", "hop": 1 }
      ],
      "node_to_chunk": [               // [NEW] how traversal nodes map to chunks
        { "node_id": "amt_4500000", "chunk_id": "204adf0f…" }
      ],
      "graph_chunks": ["204adf0f…", "921fe465…"] // [NEW] the actual ids, not just a count
    },

    "total_candidates": 198,           // [HAVE]
    "total_seeds": 14                  // [HAVE]
  }
}
```

## Cross-cutting requirements (not a single field)

- **[NEW] Stable, queryable KG ids.** `entity_id` / `triple_id` / `community_id` / `node_id` / `chunk_id` / `document_id` must be **persistent and re-queryable after the run**, so a tool can re-enter the KG and replay a traversal.
- **[NEW] One consistent `chunk_id` space** across `sources`, `routes`, `path_traversal`, and the KG. (The gold/test set currently uses a *different* id space — 0 overlap with retrieval ids — so confirm the internal chain stays unified.)
- **[CONFIRM] `sources` vs `knowledge_sources`.** Document which list = "what the generator saw." We verified it's **`sources`** — provenance + `used_in_generation` should be attached there.

## The one-line ask
> Today the endpoint sends **counts** and the agent's **requests**. Add **prompts and provenance**: emit `final_generation.messages`, and for every chunk in `sources` give `provenance` (route → seed/triple → path → hop) using **stable KG ids** — plus the real `edges`/`graph_chunks` ids in `path_traversal`.
