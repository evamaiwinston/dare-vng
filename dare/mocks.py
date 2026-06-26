"""Discovery of mock RAG-response files for CLI and demo testing.

A single flat folder (``mock_data/`` at the repo root) is the one place to drop
test files — no registry to edit. Both the CLI (``dare --mock <name>``) and the
demo build their choices from ``list_mocks()``, so a new
file appears in both the moment it lands in the folder.

Each mock is a JSON RAG response in the shape ``load_mock`` / ``prepare_inputs``
expect (an ``answer`` string and a ``knowledge_sources`` list).
"""

from pathlib import Path

# Repo-root/mock_data — shared by the CLI and the demo, decoupled from demo/.
MOCK_DIR = Path(__file__).resolve().parent.parent / "mock_data"


def list_mocks() -> list[Path]:
    """All non-empty mock files in MOCK_DIR, sorted by name.

    Empty files are skipped so a stubbed-but-unpopulated case never shows up as
    a runnable choice.
    """
    if not MOCK_DIR.is_dir():
        return []
    return sorted(p for p in MOCK_DIR.glob("*.json") if p.stat().st_size > 0)


def mock_names() -> list[str]:
    """Bare stems of the available mocks (e.g. 'cc_example'), for menus/help."""
    return [p.stem for p in list_mocks()]


def resolve_mock(name: str | Path) -> Path:
    """Resolve a mock reference to a concrete file path.

    Accepts, in order: an existing path (used as-is), a bare name or filename
    matched against MOCK_DIR (with or without the ``.json`` suffix). Raises
    FileNotFoundError listing the available names when nothing matches.
    """
    p = Path(name)
    if p.is_file():
        return p

    stem = p.name[:-5] if p.name.endswith(".json") else p.name
    candidate = MOCK_DIR / f"{stem}.json"
    if candidate.is_file():
        return candidate

    available = ", ".join(mock_names()) or "(none found)"
    raise FileNotFoundError(
        f"No mock named {stem!r} in {MOCK_DIR}. Available: {available}"
    )
