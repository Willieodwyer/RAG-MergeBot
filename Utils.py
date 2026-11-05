from pathlib import Path


# --------------------------------------------------
# Repository loading and chunking
# --------------------------------------------------


def load_documents(repo_path: Path):
    if not repo_path.is_dir():
        raise FileNotFoundError(f"Repository directory not found: {repo_path}")

    documents: list[dict[str, str]] = []

    cpp_extensions = {
        "*.cpp",
        "*.cc",
        "*.cxx",
        "*.c++",
        "*.h",
        "*.hh",
        "*.hpp",
        "*.hxx",
        "*.h++",
        "*.ipp",
        "*.tpp",
        "*.txx",
        "*.inl",
        "*.inc",
        "*.ixx",
        "*.cppm",
        "*.mpp",
        "*.cu",
        "*.cuh",
    }

    files = [
        file
        for pattern in cpp_extensions
        for file in repo_path.rglob(pattern)
    ]

    for path in files:

        if not path.is_file():
            continue

        try:
            content = path.read_text(
                encoding="utf-8",
                errors="replace"
            )

        except OSError as exc:
            print(f"[WARNING] Cannot read {path}: {exc}")
            continue

        if content.strip():
            doc = {
                "source": str(path),
                "content": content
            }
            documents.append(doc)

    return documents
