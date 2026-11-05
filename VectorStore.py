import hashlib
import json
import sys
from functools import lru_cache
from pathlib import Path
from tree_sitter import Language, Parser
import tree_sitter_cpp

import faiss
import numpy as np
import torch
from sentence_transformers import SentenceTransformer

from Utils import load_documents

CHUNK_SIZE = 1500  # Your target size in characters
CHUNK_OVERLAP = 100

BATCH_SIZE = 64
TOP_K = 3

EMBEDDING_MODEL = "BAAI/bge-small-en-v1.5"


# --------------------------------------------------
# Local embedding model
# --------------------------------------------------

@lru_cache(maxsize=2)
def get_embedding_model(model_name: str):
    device = "cuda" if torch.cuda.is_available() else "cpu"

    print(f"Loading embedding model: {model_name}")
    print(f"Embedding device: {device}")

    return SentenceTransformer(
        model_name,
        device=device
    )


def create_embeddings(texts, model_name: str):
    model = get_embedding_model(model_name)

    if not texts:
        dimension = model.get_sentence_embedding_dimension()
        return np.empty((0, dimension), dtype=np.float32)

    vectors = model.encode(
        texts,
        batch_size=BATCH_SIZE,
        convert_to_numpy=True,
        normalize_embeddings=True,
        show_progress_bar=False
    )

    return np.ascontiguousarray(vectors, dtype=np.float32)


def chunk_documents(documents):
    chunks = []

    for document in documents:
        content = document["content"]
        source = document["source"]

        start = 0
        while start < len(content):

            end = min(start + CHUNK_SIZE, len(content))

            chunk = content[start:end]

            if chunk.strip():
                line_start = content.count("\n", 0, start) + 1

                chunks.append({
                    "source": source,
                    "content": chunk,
                    "line_start": line_start
                })

            if end >= len(content):
                break

            start = end - CHUNK_OVERLAP

    return chunks


# --------------------------------------------------
# Cache validation
# --------------------------------------------------

def repository_fingerprint(repo_path: Path, embedding_model: str):
    files = []

    source_files = sorted(
        list(repo_path.rglob("*.cpp")) +
        list(repo_path.rglob("*.hh"))
    )

    for path in source_files:

        if path.is_file():
            stat = path.stat()

            files.append({
                "path": str(path.resolve()),
                "size": stat.st_size,
                "mtime_ns": stat.st_mtime_ns
            })

    payload = {
        "embedding_model": embedding_model,
        "chunk_size": CHUNK_SIZE,
        "chunk_overlap": CHUNK_OVERLAP,
        "files": files
    }

    serialized = json.dumps(
        payload,
        sort_keys=True
    ).encode("utf-8")

    return hashlib.sha256(serialized).hexdigest()


# --------------------------------------------------
# FAISS vector store
# --------------------------------------------------

class CodeVectorStore:

    def __init__(
            self,
            index,
            metadata,
            embedding_model: str
    ):
        self.index = index
        self.metadata = metadata
        self.embedding_model = embedding_model

    @classmethod
    def build(cls, chunks, embedding_model: str):

        if not chunks:
            raise RuntimeError(
                "No source code chunks were found."
            )

        print(
            f"Generating embeddings for {len(chunks)} chunks..."
        )

        texts = [
            chunk["content"]
            for chunk in chunks
        ]

        vectors = create_embeddings(
            texts,
            embedding_model
        )

        dimension = vectors.shape[1]

        index = faiss.IndexFlatIP(dimension)
        index.add(vectors)

        return cls(
            index,
            chunks,
            embedding_model
        )

    def save(self, path: Path):

        path.mkdir(
            parents=True,
            exist_ok=True
        )

        faiss.write_index(
            self.index,
            str(path / "index.faiss")
        )

        with open(
                path / "metadata.json",
                "w",
                encoding="utf-8"
        ) as file:
            json.dump(
                self.metadata,
                file,
                ensure_ascii=False,
                indent=2
            )

    @classmethod
    def load(
            cls,
            path: Path,
            embedding_model: str
    ):

        index = faiss.read_index(
            str(path / "index.faiss")
        )

        with open(
                path / "metadata.json",
                encoding="utf-8"
        ) as file:
            metadata = json.load(file)

        if index.ntotal != len(metadata):
            raise RuntimeError(
                "FAISS index and metadata have different sizes."
            )

        return cls(
            index,
            metadata,
            embedding_model
        )

    def search(self, query, k=TOP_K):

        if not query or not query.strip():
            return []

        if self.index.ntotal == 0:
            return []

        query_vector = create_embeddings(
            [query],
            self.embedding_model
        )

        scores, indices = self.index.search(
            query_vector,
            min(k, self.index.ntotal)
        )

        results = []

        for score, idx in zip(
                scores[0],
                indices[0]
        ):

            if idx < 0:
                continue

            chunk = self.metadata[idx].copy()
            chunk["score"] = float(score)

            results.append(chunk)

        return results


# --------------------------------------------------
# Initialize or load vector store
# --------------------------------------------------

def initialize_vector_store(
        vector_db_path: Path,
        embedding_model: str,
        repo_path: Path
):
    model_directory = embedding_model.replace("/", "--")

    vector_path = vector_db_path / model_directory / repo_path
    manifest_path = vector_path / "manifest.json"

    fingerprint = repository_fingerprint(
        repo_path,
        embedding_model
    )

    if ((vector_path / "index.faiss").exists()
            and (vector_path / "metadata.json").exists()
            and manifest_path.exists()):
        try:
            with open(manifest_path, encoding="utf-8") as file:
                manifest = json.load(file)

            if manifest.get("fingerprint") == fingerprint:
                print("Loading existing FAISS vector store...")

                return CodeVectorStore.load(vector_path, embedding_model)

        except (OSError, json.JSONDecodeError, RuntimeError) as exc:
            print(f"[WARNING] Vector cache is invalid: {exc}")

    print("Building FAISS vector store...")

    documents = load_documents(repo_path)
    print(f"Loaded {len(documents)} source files")

    chunks = chunk_documents(documents)
    print(f"Created {len(chunks)} chunks")

    vector_store = CodeVectorStore.build(
        chunks,
        embedding_model
    )

    vector_store.save(vector_path)

    with open(manifest_path, "w", encoding="utf-8") as file:
        json.dump({"fingerprint": fingerprint}, file, indent=2)

    print("Vector store saved!")

    return vector_store
