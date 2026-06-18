"""Demo configuration — the single place to edit the demo's run parameters.

Read by app.py and passed through runner.py into the pipeline. Changes take
effect on the next app start: restart `python app.py`, or run `gradio app.py`
for auto-reload on save.
"""

from pathlib import Path

# Number of ablations the attribution runs.
# Higher = more stable scores but slower (each ablation is one LLM call).
NUM_ABLATIONS = 32

_DEMO_DIR = Path(__file__).resolve().parent


# --- Demo cases ---------------------------------------------------------------
#
# Each case is a dropdown entry: a mock file + an optional response sub-span to
# cite. `start`/`end` are character offsets into the *attributed response*
# (the truncated text ContextCite scores); both None attributes the whole
# response. The query shown in the box comes from the case file's own "query".
#
# The first four reuse two example files with different cited spans.
CASES = [
    {
        "label": "ContextCite example — first sentence",
        "file": "demo_data/cc_example.json",
        "start": 0,
        "end": None,   # TODO: end char of the first sentence
    },
    {
        "label": "ContextCite example — chars 0–145",
        "file": "demo_data/cc_example.json",
        "start": 0,
        "end": 145,
    },
    {
        "label": "Demo mock — full answer",
        "file": "demo_data/demo_mock_data.json",
        "start": None,
        "end": None,
    },
    {
        "label": "Demo mock — last 2 sentences",
        "file": "demo_data/demo_mock_data.json",
        "start": 372,  
        "end": 642,
    },
    {
        "label": "Case 05 — hallucination",
        "file": "demo_data/test_cases/case_05_hallucination.json",
        "start": None,
        "end": None,
    },
    {
        "label": "Case 06 — alt wording",
        "file": "demo_data/test_cases/case_06_alt_wording.json",
        "start": None,
        "end": None,
    },
    {
        "label": "Case 07 — repeat sources",
        "file": "demo_data/test_cases/case_07_repeat_sources.json",
        "start": None,
        "end": None,
    },
    {
        "label": "Case 08 — small hallucination",
        "file": "demo_data/test_cases/case_08_small_hallucination.json",
        "start": None,
        "end": None,
    },
    # case_09_entity_swap.json is empty — add once populated.
]


def case_by_label(label: str) -> dict:
    """Look up a case by its dropdown label (falls back to the first case)."""
    for case in CASES:
        if case["label"] == label:
            return case
    return CASES[0]


def case_path(case: dict) -> Path:
    """Resolve a case's mock file to an absolute path."""
    return _DEMO_DIR / case["file"]
