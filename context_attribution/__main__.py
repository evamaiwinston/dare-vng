import argparse

from context_attribution.context_cite import run_pipeline


def main():
    parser = argparse.ArgumentParser(
        prog="python -m context_attribution",
        description="Run the context attribution pipeline (live backend or mock data).",
    )
    parser.add_argument(
        "query",
        nargs="?",
        default=None,
        help="The query to attribute. Required for live backend; optional with --mock.",
    )
    parser.add_argument(
        "--mock",
        metavar="PATH",
        default=None,
        help="Skip the backend and load this mock JSON file instead (demo mode).",
    )
    parser.add_argument(
        "--num-ablations",
        type=int,
        default=32,
        help="Number of ablations (default: 32).",
    )
    args = parser.parse_args()

    source = "mock" if args.mock else "backend"
    print(f"Source: {source}" + (f" ({args.mock})" if args.mock else ""))
    if args.query:
        print(f"Query: {args.query}")
    print()

    result = run_pipeline(
        query=args.query,
        source=source,
        mock_path=args.mock,
        num_ablations=args.num_ablations,
    )

    print(f"\nQuery: {result['query']}")
    print(f"Sources: {result['num_sources']}\n")
    print(result["attributions"].data.to_string())


if __name__ == "__main__":
    main()
