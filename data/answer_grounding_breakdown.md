# Answer-score & grounding breakdown

Source: `data/luong_graph_report.html` (embedded `const DATA`), 195 graded QA responses.  
Labels: `answer_score` (0-10), `doc_hit` (right document retrieved), `chunk_hit` (right chunk retrieved).  
**Correctness rule: an answer is CORRECT iff `answer_score >= 7`.** (null-score/error counts as incorrect.)

- Total records: **195** (graded: 194, null-score/error: 1)
- Mean answer_score: **7.90**
- **Correct (>= 7): 146 (74.9%)   |   Incorrect: 49 (25.1%)**

## A. Answer-score distribution (0-10)

| score | n | % |
|------:|--:|--:|
| 10 | 102 | 52.3% |
| 9 | 22 | 11.3% |
| 8 | 18 | 9.2% |
| 7 | 4 | 2.1% | ← threshold
| 6 | 6 | 3.1% |
| 5 | 13 | 6.7% |
| 4 | 3 | 1.5% |
| 3 | 6 | 3.1% |
| 2 | 5 | 2.6% |
| 1 | 1 | 0.5% |
| 0 | 14 | 7.2% |
| (null) | 1 | 0.5% |

## B. Grounding overall

- `doc_hit` (right document): **166/195 (85.1%)**
- `chunk_hit` (right chunk):  **152/195 (77.9%)**
- `chunk_hit_partial`:        **152/195 (77.9%)**

## C. Correct vs incorrect x grounded  (correct := score >= 7)

| group | metric | n | grounded | not grounded |
|-------|--------|--:|---------:|-------------:|
| CORRECT | doc_hit | 146 | 125 (86%) | 21 |
| INCORRECT | doc_hit | 49 | 41 (84%) | 8 |
| CORRECT | chunk_hit | 146 | 120 (82%) | 26 |
| INCORRECT | chunk_hit | 49 | 32 (65%) | 17 |

## D. Breakdown by question type, difficulty, answerability

### by `type`

| type | n | mean score | correct% | doc_hit% | chunk_hit% |
|---|--:|--:|--:|--:|--:|
| single_hop | 70 | 9.0 | 90% | 91% | 81% |
| multi_hop | 65 | 7.4 | 66% | 95% | 94% |
| temporal_reasoning | 20 | 7.4 | 75% | 85% | 75% |
| abstention | 20 | 5.9 | 55% | 30% | 10% |
| quantitative_reasoning | 20 | 7.9 | 70% | 85% | 85% |

### by `difficulty`

| difficulty | n | mean score | correct% | doc_hit% | chunk_hit% |
|---|--:|--:|--:|--:|--:|
| medium | 88 | 7.6 | 73% | 77% | 68% |
| easy | 58 | 9.1 | 90% | 88% | 79% |
| hard | 49 | 7.1 | 61% | 96% | 94% |

### by `answerability`

| answerability | n | mean score | correct% | doc_hit% | chunk_hit% |
|---|--:|--:|--:|--:|--:|
| answerable | 175 | 8.1 | 77% | 91% | 86% |
| unanswerable | 20 | 5.9 | 55% | 30% | 10% |

## E. Notable buckets (qa_ids), correct := score >= 7

**Incorrect AND not chunk-grounded (retrieval miss + wrong answer)** — 17:

`qa-khoiva-0030`, `qa-khoiva-0039`, `qa-khoiva-0052`, `qa-khoiva-0062`, `qa-khoiva-0064`, `qa-luongvh-0011`, `qa-luongvh-0013`, `qa-luongvh-0025`, `qa-luongvh-0065`, `qa-luongvh-0079`, `qa-luongvh-0096`, `qa-luongvh-0129`, `qa-luongvh-0130`, `qa-luongvh-0132`, `qa-luongvh-0133`, `qa-luongvh-0136`, `qa-luongvh-0139`

**Incorrect BUT chunk-grounded (right chunk, still wrong → reasoning/generation failure)** — 32:

`qa-0160`, `qa-0162`, `qa-0165`, `qa-0166`, `qa-khoiva-0006`, `qa-khoiva-0009`, `qa-khoiva-0018`, `qa-khoiva-0020`, `qa-khoiva-0022`, `qa-khoiva-0023`, `qa-khoiva-0027`, `qa-khoiva-0032`, `qa-khoiva-0033`, `qa-khoiva-0040`, `qa-khoiva-0045`, `qa-khoiva-0051`, `qa-luongvh-0014`, `qa-luongvh-0017`, `qa-luongvh-0020`, `qa-luongvh-0026`, `qa-luongvh-0028`, `qa-luongvh-0081`, `qa-luongvh-0089`, `qa-luongvh-0117`, `qa-luongvh-0123`, `qa-luongvh-0125`, `qa-luongvh-0128`, `qa-luongvh-0141`, `qa-luongvh-0146`, `qa-luongvh-0153`, `qa-luongvh-0158`, `qa-luongvh-0159`

**Correct WITHOUT chunk hit (right answer despite a chunk miss)** — 26:

`qa-0164`, `qa-khoiva-0070`, `qa-luongvh-0003`, `qa-luongvh-0009`, `qa-luongvh-0010`, `qa-luongvh-0033`, `qa-luongvh-0038`, `qa-luongvh-0047`, `qa-luongvh-0053`, `qa-luongvh-0054`, `qa-luongvh-0059`, `qa-luongvh-0064`, `qa-luongvh-0082`, `qa-luongvh-0083`, `qa-luongvh-0084`, `qa-luongvh-0090`, `qa-luongvh-0091`, `qa-luongvh-0097`, `qa-luongvh-0098`, `qa-luongvh-0120`, `qa-luongvh-0126`, `qa-luongvh-0131`, `qa-luongvh-0135`, `qa-luongvh-0137`, `qa-luongvh-0138`, `qa-luongvh-0145`
