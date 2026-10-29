# py -3.12 -m venv .venv
# pip install langchain langchain-core langchain-huggingface langchain-community
# pip install transformers sentence-transformers accelerate faiss-cpu
#
# For CPU PyTorch
#   pip install torch
# For CUDA PyTorch
#   Go to: https://pytorch.org/
#   Copy the installation suggestion
#   Something like: pip install torch torchvision --index-url https://download.pytorch.org/whl/cu126

import os
import warnings
from pathlib import Path

import torch
from langchain.agents import create_agent
from langchain_community.document_loaders import TextLoader, DirectoryLoader
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_core.tools import tool
from langchain_huggingface import HuggingFaceEndpoint, ChatHuggingFace
from langchain_text_splitters import RecursiveCharacterTextSplitter

from config import *

VECTOR_DB_PATH = "vector_cache"

model_id = "openai/gpt-oss-120b"
model_id = "meta-llama/Llama-3.1-8B-Instruct"
model_id = "Qwen/Qwen2.5-72B-Instruct"
model_id = "deepseek-ai/DeepSeek-V4.1-Flash-1017" # Good model
model_id = "moonshotai/Kimi-K2.7-Code" # VERY EXPENSIVE - Did not find a legitimate leak
model_id = "Qwen/Qwen3.5-122B-A10B" # Good model - Found leaks!

embedding_model = "BAAI/bge-small-en-v1.5"
query = "Find 1 memory leak then return"

if __name__ == "__main__":
    warnings.filterwarnings("ignore")

    os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = 'true'
    os.environ["HF_TOKEN"] = HF_TOKEN

    print(f"PyTorch Version: {torch.__version__}")
    print(f"PyTorch Cuda:    {torch.version.cuda}")
    print(f"PyTorch IsAvail: {torch.cuda.is_available()}")
    print(f"PyTorch Device:  {torch.cuda.get_device_name(0)}")

    repo_path = r"C:\Users\william.odwyer\Projects\RAG\live"

    print(f"Start embeddings...")
    embeddings = HuggingFaceEmbeddings(
        model_name=embedding_model,
        model_kwargs={"device": "cuda"},
        encode_kwargs={
            "batch_size": 64,
        }
    )

    vector_path = VECTOR_DB_PATH + "/" + embedding_model
    if Path(vector_path).exists():
        print("Loading vector store...")
        vector_store = FAISS.load_local(
            vector_path,
            embeddings,
            allow_dangerous_deserialization=True
        )
    else:
        print("Building vector store...")

        # Vector store for document
        cpp_docs = DirectoryLoader(
            repo_path,
            glob="**/*.cpp",
            loader_cls=TextLoader
        ).load()

        hh_docs = DirectoryLoader(
            repo_path,
            glob="**/*.hh",
            loader_cls=TextLoader
        ).load()

        documents = cpp_docs + hh_docs
        print(f"Loaded {len(documents)} documents")

        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=500,
            chunk_overlap=100
        )
        print(f"Split documents...")
        chunks = text_splitter.split_documents(documents)

        print("Generating vector store...")
        vector_store = FAISS.from_documents(
            chunks,
            embeddings
        )

        vector_store.save_local(vector_path)
        print("Saved vector store!")

    retriever = vector_store.as_retriever(
        search_kwargs={"k": 3}
    )

    # Connect to a Hugging Face-hosted model
    llm = HuggingFaceEndpoint(
        repo_id=model_id,
        task="text-generation",
        max_new_tokens=2048,
        do_sample=False,
        huggingfacehub_api_token=HF_TOKEN
    )

    chat_model = ChatHuggingFace(llm=llm)


    @tool
    def get_context(
            query: str | None = None,
            path: str | None = None,
            line_start: int | None = None,
            line_end: int | None = None,
    ) -> str:
        """Retrieve code from the Live555 codebase.

        Use query for semantic search across the codebase.
        Use path and optional line_start/line_end to inspect a
        specific source file and line range.
        """
        # Option 1: Inspect a specific file and line range.
        if path:
            root = Path(repo_path).resolve()
            target = Path(path).resolve()

            # Restrict file access to the configured repository.
            if not target.is_relative_to(root):
                return "Error: requested file is outside the repository."

            if not target.is_file():
                return f"Error: file not found: {target}"

            try:
                lines = target.read_text(
                    encoding="utf-8",
                    errors="replace",
                ).splitlines()
            except OSError as exc:
                return f"Error reading file: {exc}"

            start = max(1, line_start or 1)
            end = min(len(lines), line_end or start + 199)

            if start > len(lines) or end < start:
                return "Error: requested line range is invalid."

            selected = lines[start - 1:end]

            return (
                    f"File: {target}\n"
                    f"Lines {start}-{start + len(selected) - 1}:\n"
                    + "\n".join(
                f"{i}: {line}"
                for i, line in enumerate(selected, start=start)
            )
            )

        # Option 2: Semantic search using FAISS.
        if query:
            docs = retriever.invoke(query)

            if not docs:
                return "No relevant code found."

            return "\n\n".join(
                f"File: {doc.metadata.get('source', 'Unknown')}\n"
                f"{doc.page_content}"
                for doc in docs
            )

        return "Error: provide either a query or a file path."


    tools = [get_context]

    # Create the tool-using agent
    agent = create_agent(
        model=chat_model,
        tools=tools,
        system_prompt=(
            "You are an expert C++ code reviewer specializing in memory management and resource ownership.\n"
            "1. Start by using get_context with a semantic query about memory leaks and resource ownership.\n"
            "2. Inspect promising files using path and line ranges.\n"
            "3. Look for missing delete/free, ownership violations, unreleased resources, and incorrect destructors.\n"
            "4. Stop when you identify one credible leak.\n"
            "5. Report the file, line numbers, evidence, and a concise explanation of the leak. Do not claim a leak without evidence."
        ),
    )

    # Run the agent with tools
    print()
    print(f"Tool-using agent ({model_id}):")
    result = agent.invoke({
        "messages": [
            {
                "role": "user",
                "content": query,
            }
        ]
    })

    print(result["messages"][-1].content)

    with open("result.txt", "w") as file:
        print(result, file=file)
