"""Demo configuration — the single place to edit the demo's run parameters.

Read by app.py and passed through runner.py into the pipeline. Changes take
effect on the next app start: restart `python app.py`, or run `gradio app.py`
for auto-reload on save.

The list of selectable mocks is no longer hard-coded here — it is discovered
from the shared mock_data/ folder (see tools.mocks). Drop a JSON
file in there and it appears in both the CLI and the demo automatically.
"""

# Number of ablations the attribution runs.
# Higher = more stable scores but slower (each ablation is one LLM call).
NUM_ABLATIONS = 32

# Fixed reference for the green Score shading: the score that renders as full
# green. FIXED (absolute), not relative to each run's max — so a given score
# always shows the same intensity across cases/runs. Scores <= 0 render white;
# scores >= GREEN_MAX render full green. Tune to your score range.
GREEN_MAX = 50.0
