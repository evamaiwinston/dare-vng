"""Verify the runner.py path against the CLI on the same mock input.

Calls run_attribution(source="mock") and prints the response and the raw
score table (attributions.data) so the output can be diffed against
`python -m context_attribution --mock demo/demo_mock_data.json`.

The pipeline is deterministic for a fixed input (ablation masks are seeded;
the LLM is queried at temperature 0 with prompt_logprobs), so the score
table should match the CLI exactly.
"""

from runner import run_attribution, DEFAULT_MOCK_PATH

result = run_attribution(source="mock", mock_path=DEFAULT_MOCK_PATH, num_ablations=32)

print(f"\nQuery: {result['query']}")
print(f"Sources: {result['num_sources']}\n")
print("--- response ---")
print(result["response"])
print("\n--- attributions (raw score table) ---")
print(result["attributions"].data.to_string())
