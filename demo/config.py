"""Demo configuration — the single place to edit the demo's run parameters.

These are read by app.py and passed through runner.py into the pipeline.
Changes take effect on the next app start: restart `python app.py`, or run
`gradio app.py` for auto-reload on save.
"""

from pathlib import Path

# Number of ablations the attribution runs.
# Higher = more stable scores but slower (each ablation is one LLM call).
NUM_ABLATIONS = 32

# Mock RAG-response file to demo with (file name, relative to this demo/ dir).
# Swap this to point the demo at a different mock case.
MOCK_DATA_FILE = "demo_data/cc_example.json"

# Resolved absolute path handed to the runner — no need to edit this.
MOCK_DATA_PATH = Path(__file__).resolve().parent / MOCK_DATA_FILE
