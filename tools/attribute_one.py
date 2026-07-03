"""Legacy single-record CLI (was `dare/__main__.py`, i.e. `python -m dare`).

Old-path: attributes ONE query/mock via `run_pipeline` (whole-response Styler table),
predating the per-unit `attribute_by_sentence` + `summary` pipeline. Superseded by the
batch workflow — use `python -m dare.batch --corpus <file>` instead. Kept here as a dev
tool for one-off single-record / span attribution. Run: `python tools/attribute_one.py …`.
"""

import argparse
import sys

from dare.attribution import run_pipeline
from tools.mocks import list_mocks, mock_names, resolve_mock


def main():
    parser = argparse.ArgumentParser(
        prog="dare",
        description="Run the context attribution pipeline (live backend or mock data).",
    )
    parser.add_argument(
        "query",
        nargs="?",
        default=None,
        help="The query to attribute. Required, unless the mock file carries its "
             "own 'query' field.",
    )
    parser.add_argument(
        "--mock",
        metavar="NAME_OR_PATH",
        default=None,
        help="Skip the backend and use this mock instead. Accepts a name from "
             "mock_data/ (e.g. 'demo_mock_data') or a path. See --list-mocks.",
    )
    parser.add_argument(
        "--list-mocks",
        action="store_true",
        help="List the mock files available in mock_data/ and exit.",
    )
    parser.add_argument(
        "--num-ablations",
        type=int,
        default=32,
        help="Number of ablations (default: 32).",
    )
    parser.add_argument(
        "--start-idx",
        type=int,
        default=None,
        help="Cite only a sub-span of the response: start character offset into "
             "the response. Omitted = from the beginning.",
    )
    parser.add_argument(
        "--end-idx",
        type=int,
        default=None,
        help="Cite only a sub-span of the response: end character offset into the "
             "response. Omitted = to the end. Both omitted = whole response.",
    )
    args = parser.parse_args()

    if args.list_mocks:
        mocks = list_mocks()
        if not mocks:
            print("No mock files found in mock_data/.")
        else:
            print(f"Available mocks in mock_data/ ({len(mocks)}):")
            for name in mock_names():
                print(f"  {name}")
        return

    # Resolve the mock reference (name or path) up front for a clear error.
    mock_path = None
    if args.mock:
        try:
            mock_path = resolve_mock(args.mock)
        except FileNotFoundError as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(2)

    source = "mock" if mock_path else "backend"
    print(f"Source: {source}" + (f" ({mock_path.name})" if mock_path else ""))
    if args.query:
        print(f"Query: {args.query}")
    if args.start_idx is not None or args.end_idx is not None:
        print(f"Response span: [{args.start_idx}, {args.end_idx})")
    print()

    try:
        result = run_pipeline(
            query=args.query,
            source=source,
            mock_path=mock_path,
            num_ablations=args.num_ablations,
            start_idx=args.start_idx,
            end_idx=args.end_idx,
        )
    except ValueError as e:
        # Missing query (no CLI arg and none in the mock) and other input errors
        # are refusals, not crashes — report cleanly and exit non-zero.
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(2)

    print(f"\nQuery: {result['query']}")
    print(f"Sources: {result['num_sources']}\n")
    print(result["attributions"].data.to_string())


if __name__ == "__main__":
    main()
