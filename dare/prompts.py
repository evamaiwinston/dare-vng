"""Static RAG prompts — lifted verbatim from the backend's own LLM traces.

Source: data/luong_graph_report.html, a 195-question debug/eval capture embedding
each question's full `llm_trace`. Verified 2026-06-30: across all 195 questions
there is exactly ONE distinct prompt per agent role (4 total) — these are STATIC,
not per-query or versioned. They are NOT emitted by the live endpoint (which sends
actions only, no prompts) — see data/endpoint_output_inventory.md.

DARE uses SYNTHESIS_SYSTEM + build_generation_messages to reconstruct the exact
prompt the model saw when producing the answer we attribute, so ablation re-scoring
matches reality. If the backend changes these, this file goes stale silently —
re-lift from a fresh capture, or have the endpoint send `instruction`.
"""

SYNTHESIS_SYSTEM = "Bạn là trợ lý tổng hợp câu trả lời cuối cùng. Dựa trên các bằng chứng đã thu thập, hãy trả lời ĐÚNG TRỌNG TÂM câu hỏi bằng tiếng Việt, ngắn gọn và chính xác. KHÔNG trả lời thêm thông tin ngoài phạm vi câu hỏi. KHÔNG mở rộng sang chủ đề liên quan mà người dùng không hỏi. Nếu bằng chứng không đủ, không tự trả lời mà hãy nêu rõ phần còn thiếu."

AGENT_SYSTEM = "Bạn là trợ lý hỏi-đáp chính sách nội bộ VNG/ZPS. Khi cần thông tin từ tài liệu, HÃY gọi tool `search_knowledge` (có thể gọi nhiều lần để thu thập đủ bằng chứng). Khi cần nhớ lại hội thoại/ngữ cảnh dài hạn, gọi `recall_long_term_memory`. TUYỆT ĐỐI KHÔNG tự viết câu trả lời. Khi đã thu thập đủ bằng chứng, hãy gọi tool `generate_answer` để tạo câu trả lời cuối cùng: truyền vào `question` là câu hỏi của người dùng, và `chunk_ids` là các chunk_id (lấy từ kết quả search_knowledge) xếp theo THỨ TỰ QUAN TRỌNG GIẢM DẦN — chunk quan trọng nhất đặt trước, tối đa các chunk quan trọng nhất. Chỉ chọn các chunk thực sự liên quan tới câu hỏi."

DECOMPOSE_SYSTEM = "Bạn tách câu hỏi chính sách thành các sub-question nguyên tử và xác định loại thực thể/quan hệ liên quan trong schema để hỗ trợ truy hồi knowledge graph. Chỉ trả về JSON."

IRCOT_SYSTEM = "Bạn đang truy hồi lặp kết hợp suy luận từng bước (chain-of-thought) cho hệ thống hỏi-đáp chính sách. Suy luận dựa trên bằng chứng, rồi hoặc kết luận hoặc yêu cầu thêm. Chỉ trả về JSON."


def format_context(chunks: list[str]) -> str:
    """Reproduce the evidence block: `[i] <chunk>` joined by blank lines, numbered
    from 1 in the given order (the model is shown [N] markers, NOT chunk_ids, so
    order is load-bearing)."""
    return "\n\n".join(f"[{i}] {c}" for i, c in enumerate(chunks, 1))


def build_generation_messages(query: str, chunks: list[str]) -> list[dict]:
    """The literal [system, human] the generate_answer call sends, reconstructed
    from components. `chunks` = chunk TEXTS in the [1],[2],... order they were passed."""
    human = f"Câu hỏi: {query}\n\nBằng chứng:\n{format_context(chunks)}"
    return [
        {"role": "system", "content": SYNTHESIS_SYSTEM},
        {"role": "user", "content": human},
    ]
