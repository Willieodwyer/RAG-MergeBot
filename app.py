# py -3.12 -m venv .venv
# pip install langchain langchain-core langchain-huggingface langchain-community
# pip install transformers sentence-transformers accelerate faiss-cpu
# pip install tree-sitter tree-sitter-cpp
# pip install bm25s
#
# For CPU PyTorch
#   pip install torch
# For CUDA PyTorch
#   Go to: https://pytorch.org/
#   Copy the installation suggestion
#   Something like: pip install torch torchvision --index-url https://download.pytorch.org/whl/cu126

from pathlib import Path

from agents import Agent, Runner, function_tool

from BM25Store import initialise_bm25_store
from Benchmark import benchmark
from VectorStore import initialize_vector_store, TOP_K, EMBEDDING_MODEL
from Inputs import *
from Prompts import *

# --------------------------------------------------
# Configuration
# --------------------------------------------------

REPO_PATH = Path("Core")
CACHE_PATH = Path("cache")

model_costs = {
    "gpt-6-astra": {"input": 10.0, "output": 50.0},
    "gpt-6.1-sol": {"input": 2.0, "output": 10.0},
    "gpt-6.1-terra": {"input": 1.0, "output": 5.0},
    "gpt-6.1-luna": {"input": 0.1, "output": 0.5},
    "gpt-5.4-mini": {"input": 0.75, "output": 4.5},
}
OPENAI_MODEL = "gpt-6-astra"

# --------------------------------------------------
# Repository context
# --------------------------------------------------

vector_store = None
bm25_store = None


@function_tool
def get_context(
        query: str | None = None,
        path: str | None = None,
        line_start: int | None = None,
        line_end: int | None = None,
) -> str:
    """
    Retrieve source code from the configured repository.

    Use query for semantic search across the codebase.
    Use path and optional line_start/line_end to inspect
    a specific source file and line range.

    Both query and path can be supplied together.
    """

    global vector_store

    query_result = []

    with benchmark(f"Get context: {query} | {path} | {line_start} | {line_end}"):

        # Inspect a specific source file

        if path:

            root = REPO_PATH.resolve()

            requested_path = Path(path)

            if not requested_path.is_absolute():
                requested_path = root / requested_path

            target = requested_path.resolve()

            if not target.is_relative_to(root):
                return "Error: requested file is outside the repository."

            if not target.is_file():
                return f"Error: file not found: {target}"

            try:
                lines = target.read_text(
                    encoding="utf-8",
                    errors="replace"
                ).splitlines()

            except OSError as exc:
                return f"Error reading file: {exc}"

            start = max(1, line_start or 1)

            end = min(
                len(lines),
                line_end if line_end is not None else start + 199
            )

            if start > len(lines) or end < start:
                return "Error: invalid line range."

            selected = lines[start - 1:end]

            temp_result = "\n".join(
                f"{i}: {line}"
                for i, line in enumerate(
                    selected,
                    start=start
                )
            )

            query_result.append(
                f"File: {target}\n"
                f"Lines {start}-{start + len(selected) - 1}:\n"
                f"{temp_result}"
            )

        # Semantic code search

        if query:
            if vector_store is None:
                return "Error: vector store has not been initialized."

            docs = vector_store.search(query, k=TOP_K)

            if not docs:
                query_result.append("No relevant code found.")

            else:
                for doc in docs:
                    query_result.append(
                        f"File: {doc['source']}\n"
                        f"Approximate starting line: {doc['line_start']}\n"
                        f"Similarity: {doc['score']:.4f}\n"
                        f"{doc['content']}"
                    )

        if not query_result:
            return "Error: provide either a query or a file path."

    result = "\n\n---\n\n".join(query_result)

    # print("\n--- CONTEXT ---")
    # print(result)
    # print("--- END CONTEXT ---\n")

    return result


@function_tool
def search_lines(
        query: str | None = None
) -> str:
    """
    BM25 search the codebase for singular strings
    """

    global bm25_store

    with benchmark(f"Search: {query}"):
        search_result = bm25_store.search(query)
        print(search_result)
        print()
        return search_result


# --------------------------------------------------
# OpenAI Agent
# --------------------------------------------------

def create_merge_request_agent():
    return Agent(
        name="Merge Request Expert",
        instructions=MergeRequestExpert,
        model=OPENAI_MODEL,
        tools=[get_context, search_lines]
    )


# --------------------------------------------------
# Main
# --------------------------------------------------

if __name__ == "__main__":
    print("OpenAI Merge Request Review Agent")
    print("---------------------------------")

    print(f"Model: {OPENAI_MODEL}")
    print(f"Local embeddings: {EMBEDDING_MODEL}")

    with benchmark("Initialize bm25 store"):
        bm25_store = initialise_bm25_store(
            CACHE_PATH,
            REPO_PATH
        )

    with benchmark("Initialize vector store"):
        vector_store = initialize_vector_store(
            CACHE_PATH,
            EMBEDDING_MODEL,
            REPO_PATH
        )

    with benchmark("Create Agent"):
        merge_request_agent = create_merge_request_agent()

    with benchmark("Run Merge Request Review"):
        result = Runner.run_sync(
            merge_request_agent,
            UserDiff,
            max_turns=50
        )

    print("\n--- REQUEST COST ---")
    usage = result.context_wrapper.usage
    print(f"Input tokens:  {usage.input_tokens:,}")
    print(f"Output tokens: {usage.output_tokens:,}")
    print(f"Total tokens:  {usage.total_tokens:,}")

    input_cost = (usage.input_tokens / 1_000_000) * model_costs[OPENAI_MODEL]["input"]
    output_cost = (usage.output_tokens / 1_000_000) * model_costs[OPENAI_MODEL]["output"]
    total_cost = input_cost + output_cost

    print(f"Input cost:  ${input_cost:.6f}")
    print(f"Output cost: ${output_cost:.6f}")
    print(f"Total cost:  ${total_cost:.6f}")

    print("\n--- MERGE REQUEST REVIEW ---\n")
    initial_review = result.final_output
    print(initial_review)

    with open(
            "result.txt",
            "w",
            encoding="utf-8"
    ) as file:
        file.write(str(initial_review))

    print("\nReview saved to result.txt")
