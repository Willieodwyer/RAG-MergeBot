import bm25s
from pathlib import Path

from Utils import load_documents


class BM25Store:
    def __init__(self, retriever: bm25s.BM25, corpus: list):
        self.retriever = retriever
        self.corpus = corpus

    def search(self, query: str):
        result = []
        results, scores = self.retriever.retrieve(
            bm25s.tokenize([query]),
            k=10,
        )

        for rank, (doc_idx, score) in enumerate(
                zip(results[0], scores[0]),
                start=1):
            doc = self.corpus[int(doc_idx)]
            if score > 0.0:
                result.append(f"{doc['source']}:{doc['line']} {doc['text']}")

        return result


def initialise_bm25_store(
        db_path: Path,
        repo_path: Path
):
    store_path = db_path / "BM25" / repo_path

    documents = load_documents(repo_path)
    print(f"Loaded {len(documents)} source files")

    # Build line-level corpus with metadata
    corpus = []

    for doc in documents:
        for line_no, line in enumerate(doc["content"].splitlines(), start=1):
            if not line.strip():
                continue

            corpus.append({
                "text": line.strip(),
                "source": doc["source"],
                "line": line_no
            })

    print(f"Indexed {len(corpus)} source lines")

    # Build BM25 index
    texts = [item["text"] for item in corpus]

    retriever = bm25s.BM25()
    retriever.index(bm25s.tokenize(texts))

    return BM25Store(retriever, corpus)
