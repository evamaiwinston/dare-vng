# What the endpoint returns today (current `response` object)

This is the **actual live endpoint payload** — one line's `response` from `data/raw_responses.jsonl`, shown verbatim with long arrays/strings trimmed for readability (`… (+N more)` marks truncation). Nothing here is aspirational — it is exactly the current shape.

Top-level fields: `ablation`, `answer`, `answer_via_tool`, `knowledge_sources`, `memory_sources`, `mode`, `reasoning_trace`, `retrieval_detail`, `session_id`, `sources`, `step_timings`, `tools_used`, `total_step_time`, `usage`.

> Note: `llm_trace` (the prompts) is **not** in this payload — it exists only in the offline report, not from the endpoint.

```json
{
  "answer": "Nhân viên VNG ở cấp bậc 4.2 được hưởng định mức hỗ trợ taxi tối đa 4.500.000 đồng một tháng.",
  "answer_via_tool": true,
  "knowledge_sources": [
    {
      "chunk_id": "204adf0ff219c60f661bd8f95bff992833ab1979cefe4b1979deba7b403d892c",
      "document_id": "doc_a2734411efe0bd06",
      "score": 2.140087,
      "content": "## 2.3. Đối tượng sử dụng và định mức hàng tháng\n\nĐịnh mức hỗ trợ tùy thuộc vào cấp bậc, được quy định cụ thể như sau:\n\n …"
    }
  ],
  "memory_sources": [],
  "reasoning_trace": [
    {
      "step": 1,
      "tool": "search_knowledge",
      "args": {
        "query": "định mức hỗ trợ taxi cấp bậc 4.2 nhân viên VNG"
      },
      "result": "[1] (chunk_id=204adf0ff219c60f661bd8f95bff992833ab1979cefe4b1979deba7b403d892c)\n## 2.3. Đối tượng sử dụng và định mức hà …"
    },
    {
      "step": 2,
      "tool": "generate_answer",
      "args": {
        "question": "Nhân viên VNG ở cấp bậc 4.2 được hưởng định mức hỗ trợ taxi tối đa bao nhiêu một tháng?",
        "chunk_ids": [
          "204adf0ff219c60f661bd8f95bff992833ab1979cefe4b1979deba7b403d892c"
        ]
      },
      "result": "Nhân viên VNG ở cấp bậc 4.2 được hưởng định mức hỗ trợ taxi tối đa 4.500.000 đồng một tháng."
    }
  ],
  "tools_used": [
    "search_knowledge",
    "generate_answer"
  ],
  "step_timings": [
    {
      "step": 1,
      "kind": "llm",
      "name": "agent",
      "elapsed": 1.502
    },
    {
      "step": 2,
      "kind": "retrieval",
      "name": "search_knowledge.decompose_question",
      "elapsed": 2.921
    },
    "… (+7 more)"
  ],
  "total_step_time": 25.082,
  "retrieval_detail": {
    "sub_questions": [
      {
        "q": "Định mức hỗ trợ taxi cho nhân viên cấp bậc 4.2 là bao nhiêu?",
        "embed_elapsed": 7.795,
        "routes": {
          "chunk": {
            "elapsed": 0.022,
            "hits": 10,
            "chunk_ids": [
              "3ad8b4ca641b818e98ec26b38a9c6e4fe876354d619f6362bae54d89c7c20940",
              "96d99bb59a955ee1582952c3b253de254a9ab2311775d64b5d8ec2adbffd6ba1",
              "… (+1 more)"
            ]
          },
          "entity": {
            "elapsed": 0.022,
            "hits": 10,
            "seeds_added": [
              "4,500,000 VND/tháng",
              "1,500,000 VND/tháng",
              "… (+1 more)"
            ],
            "type_filter": [
              "amount",
              "organization",
              "… (+1 more)"
            ]
          },
          "triple": {
            "elapsed": 0.024,
            "hits": 10,
            "seeds_added": [
              "Định mức hỗ trợ taxi cấp 4.2",
              "4,500,000 VND/tháng",
              "… (+1 more)"
            ],
            "type_filter": [
              "applies_to",
              "has_amount",
              "… (+1 more)"
            ]
          },
          "community": {
            "elapsed": 0.004,
            "hits": 3,
            "seeds_added": [
              "20,000,000 đồng",
              "2,000,000 đồng",
              "… (+1 more)"
            ]
          }
        }
      },
      {
        "q": "Ai là tổ chức ban hành chính sách hỗ trợ taxi cho nhân viên cấp bậc 4.2?",
        "embed_elapsed": 0.408,
        "routes": {
          "chunk": {
            "elapsed": 0.009,
            "hits": 10,
            "chunk_ids": [
              "3ad8b4ca641b818e98ec26b38a9c6e4fe876354d619f6362bae54d89c7c20940",
              "8b9fa9f1a92229329c54d57f08726bee9b59481b7dede274e49c2f8d9e2d4266",
              "… (+1 more)"
            ]
          },
          "entity": {
            "elapsed": 0.02,
            "hits": 8,
            "seeds_added": [
              "Chính sách Trợ cấp Taxi",
              "Chính sách taxi",
              "… (+1 more)"
            ],
            "type_filter": [
              "amount",
              "organization",
              "… (+1 more)"
            ]
          },
          "triple": {
            "elapsed": 0.019,
            "hits": 7,
            "seeds_added": [
              "Định mức hỗ trợ taxi cấp 4.2",
              "Cấp bậc 4.2",
              "… (+1 more)"
            ],
            "type_filter": [
              "applies_to",
              "has_amount",
              "… (+1 more)"
            ]
          },
          "community": {
            "elapsed": 0.005,
            "hits": 3,
            "seeds_added": [
              "Chỗ gửi xe máy",
              "Hỗ trợ tiền gửi xe",
              "… (+1 more)"
            ]
          }
        }
      }
    ],
    "path_traversal": {
      "elapsed": 2.336,
      "seed_count": 335,
      "expanded_nodes": 335,
      "graph_chunks": 197,
      "inv_rels_filter": [
        "applies_to",
        "has_amount",
        "… (+1 more)"
      ]
    },
    "total_candidates": 198,
    "total_seeds": 14
  },
  "session_id": null,
  "usage": {
    "llm_calls": 5,
    "input_tokens": 5391,
    "output_tokens": 496,
    "total_tokens": 5887
  },
  "mode": "agent",
  "sources": [
    {
      "chunk_id": "204adf0ff219c60f661bd8f95bff992833ab1979cefe4b1979deba7b403d892c",
      "document_id": "doc_a2734411efe0bd06",
      "score": 2.140087,
      "content": "## 2.3. Đối tượng sử dụng và định mức hàng tháng\n\nĐịnh mức hỗ trợ tùy thuộc vào cấp bậc, được quy định cụ thể như sau:\n\n …"
    }
  ],
  "ablation": {
    "use_memory": false,
    "use_graph_rag": true,
    "memory": {
      "save_turns": true,
      "use_session_memory": true,
      "use_long_term_memory": true,
      "use_graph_expand": true,
      "use_rerank": true
    },
    "retrieval": {
      "use_chunk_vectors": true,
      "use_node_vectors": true,
      "use_triplet_vectors": true,
      "use_community_vectors": true,
      "use_graph_expand": true,
      "use_graph_boost": true,
      "use_decompose": true,
      "use_ircot": true
    }
  }
}
```