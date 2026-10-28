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
from pathlib import Path
from textwrap import dedent

from huggingface_hub import InferenceClient, HfApi
from langchain_classic.agents import create_tool_calling_agent, AgentExecutor
from langchain_community.document_loaders import TextLoader, DirectoryLoader
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_core.prompts import PromptTemplate, ChatPromptTemplate, MessagesPlaceholder
from langchain_core.tools import Tool
from langchain_huggingface import HuggingFaceEndpoint, ChatHuggingFace
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langgraph.prebuilt import create_react_agent
from transformers.models.idefics import modeling_idefics

from config import *

import torch

import warnings

VECTOR_DB_PATH = "vector_cache"

query = "memory leaks resource ownership delete destructor"
model_id = "Qwen/Qwen2.5-Coder-7B-Instruct"
embedding_model = "BAAI/bge-small-en-v1.5"

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

    docs = retriever.invoke(query)

    context = "\n".join(
        doc.page_content for doc in docs
    )

    # print(context)

    prompt_template = PromptTemplate.from_template(
        dedent("""\
        You are a helpful assistant.

        Use ONLY the provided context to answer.

        Context:
        {context}

        Question:
        {question}

        Answer:
        """)
    )

    client = InferenceClient(
        api_key=HF_TOKEN
    )

    prompt = prompt_template.format(
        context=context,
        question=query
    )

    response = client.chat.completions.create(
        model=model_id,
        messages=[
            {
                "role": "user",
                "content": prompt
            }
        ],
        max_tokens=512
    )

    print()
    print("Response: ")
    print(response.choices[0].message.content)
