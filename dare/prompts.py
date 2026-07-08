"""Static RAG synthesis prompt — lifted verbatim from the backend's own LLM traces.

Source: data/labels/luong_graph_report.html, a 195-question debug/eval capture
embedding each question's full `llm_trace`. Verified 2026-06-30: across all 195
questions the synthesis agent uses exactly ONE distinct prompt — it is STATIC, not
per-query or versioned. It is NOT emitted by the live endpoint (which sends actions
only, no prompts).

`SYNTHESIS_SYSTEM` is the generation instruction. Passing it as the `instruction`
argument (batch `--instruction`, or attribute_one) folds it into the ablation set so
its causal effect is measured alongside the context. The attribution engine wraps the
context in ContextCite's own template — it does NOT reproduce the verbatim generation
prompt. If the backend changes this prompt, this file goes stale silently — re-lift
from a fresh capture, or have the endpoint send `instruction`.
"""

SYNTHESIS_SYSTEM = "Bạn là trợ lý tổng hợp câu trả lời cuối cùng. Dựa trên các bằng chứng đã thu thập, hãy trả lời ĐÚNG TRỌNG TÂM câu hỏi bằng tiếng Việt, ngắn gọn và chính xác. KHÔNG trả lời thêm thông tin ngoài phạm vi câu hỏi. KHÔNG mở rộng sang chủ đề liên quan mà người dùng không hỏi. Nếu bằng chứng không đủ, không tự trả lời mà hãy nêu rõ phần còn thiếu."
