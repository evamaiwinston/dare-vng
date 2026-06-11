import sys
from context_attribution.context_cite import fetch_backend, prepare_inputs, attribute_response


def main():
    if len(sys.argv) < 2:
        print("Usage: python -m context_attribution \"<query>\"")
        sys.exit(1)

    query = sys.argv[1]
    print(f"Query: {query}\n")

    data = fetch_backend(query)
    context, response = prepare_inputs(data)
    result = attribute_response(context, query, response)
    print(result)


if __name__ == "__main__":
    main()
