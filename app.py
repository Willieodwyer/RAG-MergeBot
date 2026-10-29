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
from textwrap import dedent

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
MAX_NEW_TOKENS = 20480

model_id = "openai/gpt-oss-120b"
model_id = "meta-llama/Llama-3.1-8B-Instruct"
model_id = "Qwen/Qwen2.5-72B-Instruct"
model_id = "deepseek-ai/DeepSeek-V4.1-Flash-1017" # Good model
model_id = "moonshotai/Kimi-K2.7-Code" # VERY EXPENSIVE - Did not find a legitimate leak
model_id = "Qwen/Qwen3.8-2.4T-A95B" # Too big - Timed out
model_id = "google/gemma-4-31B-it"
model_id = "Qwen/Qwen3.5-122B-A10B" # Good model - Found leaks - Found MR issues - Cheap!

embedding_model = "BAAI/bge-small-en-v1.5"
user_input = '''diff --git a/ExternalLibraries/Live555/groupsock/NetAddress.cpp b/ExternalLibraries/Live555/groupsock/NetAddress.cpp
index 8432025088..2216622e17 100644
--- a/ExternalLibraries/Live555/groupsock/NetAddress.cpp
+++ b/ExternalLibraries/Live555/groupsock/NetAddress.cpp
@@ -254,7 +254,11 @@ NetAddressList::NetAddressList(char const* hostname, int addressFamily)
 
   // Next, set up the list:
   fAddressArray = new NetAddress*[fNumAddresses];
-  if (fAddressArray == NULL) return;
+  if (fAddressArray == NULL)
+  {
+    freeaddrinfo(addrinfoResultPtr);
+    return;
+  }
 
   unsigned i = 0;
   p = addrinfoResultPtr;
diff --git a/ExternalLibraries/Live555/liveMedia/RTSPClient.cpp b/ExternalLibraries/Live555/liveMedia/RTSPClient.cpp
index 66485b4a75..099177b60f 100644
--- a/ExternalLibraries/Live555/liveMedia/RTSPClient.cpp
+++ b/ExternalLibraries/Live555/liveMedia/RTSPClient.cpp
@@ -264,6 +264,8 @@ Boolean RTSPClient::parseRTSPURL(char const* url,
 				 portNumBits& portNum,
 				 char const** urlSuffix) {
   do {
+    username = password = NULL; // default return values
+
     // Parse the URL as "rtsp://[<username>[:<password>]@]<server-address-or-name>[:<port>][/<stream-name>]" (or "rtsps://...")
     char const* rtspPrefix = "rtsp://";
     unsigned const rtspPrefixLength = 7;
@@ -289,7 +291,6 @@ Boolean RTSPClient::parseRTSPURL(char const* url,
 
     // Check whether "<username>[:<password>]@" occurs next.
     // We do this by checking whether '@' appears before the end of the URL, or before the first '/'.
-    username = password = NULL; // default return values
     char const* colonPasswordStart = NULL;
     char const* lastAtPtr = NULL;
     for (char const* p = from; *p != '\0' && *p != '/'; ++p) {
@@ -774,10 +775,15 @@ Boolean RTSPClient::setRequestFields(RequestRecord* request,
     char* password;
     NetAddress destAddress;
     portNumBits urlPortNum;
-    if (!parseRTSPURL(fBaseURL, username, password, destAddress, urlPortNum, (char const**)&cmdURL)) return False;
-    if (cmdURL[0] == '\0') cmdURL = (char*)"/";
-    delete[] username;
-    delete[] password;
+    const bool success = parseRTSPURL(fBaseURL, username, password, destAddress, urlPortNum, (char const**)&cmdURL);
+    delete[] username; // Unused
+    delete[] password; // Unused
+
+    if (!success)
+      return false;
+
+    if (cmdURL[0] == '\0')
+      cmdURL = (char*)"/";
 
     struct sockaddr_storage serverAddr;
     copyAddress(serverAddr, &destAddress);
@@ -909,16 +915,24 @@ int RTSPClient::openConnection() {
     NetAddress destAddress;
     portNumBits urlPortNum;
     char const* urlSuffix;
+    portNumBits destPortNum = {};
 
-    if (!parseRTSPURL(fBaseURL, username, password, destAddress, urlPortNum, &urlSuffix)) break;
-    if (urlPortNum == 322) fTLS.isNeeded = True; // port 322 is a special case: "rtsps"
-    portNumBits destPortNum = fTunnelOverHTTPPortNum == 0 ? urlPortNum : fTunnelOverHTTPPortNum;
+    const bool success = parseRTSPURL(fBaseURL, username, password, destAddress, urlPortNum, &urlSuffix);
+    if (success)
+    {
+      if (urlPortNum == 322) fTLS.isNeeded = True; // port 322 is a special case: "rtsps"
+       destPortNum = fTunnelOverHTTPPortNum == 0 ? urlPortNum : fTunnelOverHTTPPortNum;
 
-    if (username != NULL || password != NULL) {
-      fCurrentAuthenticator.setUsernameAndPassword(username, password);
-      delete[] username;
-      delete[] password;
+      if (username != NULL || password != NULL) {
+        fCurrentAuthenticator.setUsernameAndPassword(username, password);
+      }
     }
+
+    delete[] username;
+    delete[] password;
+
+    if (!success)
+      break;
     
     // We don't yet have a TCP socket (or we used to have one, but it got closed).  Set it up now.
     copyAddress(fServerAddress, &destAddress);
diff --git a/ExternalLibraries/Live555/liveMedia/SIPClient.cpp b/ExternalLibraries/Live555/liveMedia/SIPClient.cpp
index a4f6835f26..f2cc1f050c 100644
--- a/ExternalLibraries/Live555/liveMedia/SIPClient.cpp
+++ b/ExternalLibraries/Live555/liveMedia/SIPClient.cpp
@@ -134,6 +134,7 @@ SIPClient::~SIPClient() {
   delete[] (char*)fOurAddressStr;
   delete[] (char*)fApplicationName;
   delete[] (char*)fMIMESubtype;
+  delete[] (char*)fUserName;
 }
 
 void SIPClient::reset() {
'''

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
        max_new_tokens=MAX_NEW_TOKENS,
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
    merge_request_agent = create_agent(
        model=chat_model,
        tools=tools,
        system_prompt=(dedent("""\
        You are an expert software engineer conducting rigorous, evidence-based merge request (MR) code reviews. You specialize in identifying correctness defects, regressions, resource-management errors, security vulnerabilities, and other substantive issues introduced by code changes.
        Your primary objective is to identify genuine, actionable bugs in the supplied diff, not to perform a general code audit or suggest stylistic improvements.
        Review workflow
        Understand the diff
        Identify the files, functions, and behaviours changed by the MR.
        Treat added and modified lines as the primary review targets.
        Examine removed code when necessary to understand behavioural changes.
        Use the surrounding diff and available context to understand the intended change.
        Do not assume that the diff is correct simply because it compiles or follows existing patterns.
        Identify potential defectsSystematically consider whether the changes introduce:
        Memory leaks, double frees, use-after-free, buffer overflows, or invalid memory access.
        Resource leaks involving memory, file descriptors, sockets, locks, or other owned resources.
        Incorrect allocation/deallocation, ownership, object lifetimes, or destructor behaviour.
        Logic errors, incorrect conditions, unintended control flow, or broken invariants.
        Null-pointer dereferences, uninitialized variables, and invalid state transitions.
        Error-handling failures, missing cleanup, or incorrect return values.
        Concurrency defects, data races, deadlocks, and synchronization errors.
        Security vulnerabilities, including improper input validation, authentication or authorization failures, and unsafe handling of sensitive data.
        Regressions in existing behaviour, API contracts, protocol handling, and compatibility.
        Incorrect assumptions about boundary conditions, failure paths, or unusual but valid inputs.
        Prioritize issues that can cause incorrect behaviour, crashes, security exposure, resource exhaustion, or significant operational failures.
        Verify potential findings using repository context
        Use get_context with a focused semantic query when repository knowledge is needed.
        Use get_context with a file path and line range to inspect relevant implementations, callers, callees, constructors, destructors, and cleanup paths.
        For resource-management issues, trace ownership and lifetime from acquisition to release, including failure paths.
        For logic defects, verify the relevant preconditions, postconditions, state transitions, and downstream effects.
        Check whether the suspected behaviour is already handled elsewhere before reporting a defect.
        Use repository context to confirm or reject hypotheses, not to search indiscriminately for unrelated problems.
        Do not assume that code outside the diff is defective merely because it is imperfect.
        Establish sufficient evidenceBefore reporting a finding, determine:
        Which changed line introduces or enables the defect.
        Under what concrete conditions the defect occurs.
        What the actual consequence is.
        Why the existing implementation does not prevent the problem.
        Whether the issue is genuinely introduced by this MR, rather than being an unrelated pre-existing defect.
        Do not report speculative issues, unsupported assumptions, hypothetical problems without a credible execution path, or stylistic preferences. If the available context is insufficient to establish a defect, investigate further or omit the finding.
        Prioritize findings
        Assign each finding a severity:
        P1 — Critical: A severe defect requiring immediate attention, such as a major security vulnerability, data loss, or a widespread service outage.
        P2 — High: A significant functional, security, or reliability defect that should be fixed before merging.
        P3 — Medium: A concrete defect with a limited or conditional impact that should be addressed.
        P4 — Low: A minor but demonstrable defect with limited impact.
        Base severity on impact, likelihood, scope, and the conditions required to trigger the defect. Do not inflate severity merely because a code path appears unsafe.
        Produce actionable review findingsFor each confirmed issue:
        Provide a concise title beginning with the priority, such as [P1], [P2], [P3], or [P4].
        Identify the exact changed file and line or minimal line range associated with the defect.
        Explain the concrete failure scenario and resulting impact.
        Explain why the changed code causes the problem.
        Suggest a specific correction when the appropriate fix can be established.
        Keep each finding focused on one independently actionable issue. Avoid duplicate findings for the same underlying defect.
        Review constraints
        Focus on defects introduced by the MR.
        Findings must be grounded in the supplied diff and, when necessary, verified repository context.
        Do not invent file names, line numbers, execution paths, API contracts, or runtime behaviour.
        Do not claim that tests fail, code was executed, or a vulnerability was reproduced unless this was actually established.
        Do not treat the absence of tests as a bug by itself.
        Do not report formatting, naming, refactoring, or design preferences unless they cause a demonstrable defect.
        Do not report an issue solely because a theoretical risk exists; establish a credible trigger and consequence.
        When the code is correct or no actionable defect can be established, explicitly state that no findings were identified.
        Prefer a small number of high-confidence findings over a large number of speculative observations.
        Stop investigating a particular hypothesis once it has been disproved. Continue reviewing other meaningful changes rather than stopping at the first potential issue.
        Never claim that the entire MR is safe simply because no defects were found in the reviewed changes.
        Output format
        Return a concise merge request review.
        For each finding, use the following structure:
        [P<n>] Short, specific description of the defect
        Location: path/to/file.cpp:line
        Problem: Describe the concrete conditions under which the defect occurs.
        Impact: Explain the observable consequence.
        Suggested fix: Describe the minimal correction, when known.
        Order findings by severity, with the most important first.
        If no actionable defects are identified, return: No actionable findings identified.
        Optionally include a brief review limitation only when missing context materially affects confidence in the review.
        Do not include a general code-quality essay, a summary of every file changed, or a list of speculative concerns.
        Use markdown format
        Short, concise
        Use emojis
        Add final conclusion at the end
        """)
        ),
    )

    # Run the agent with tools
    print()
    print(f"Tool-using agent ({model_id}):")
    result = merge_request_agent.invoke({
        "messages": [
            {
                "role": "user",
                "content": user_input,
            }
        ]
    })

    initial_review = result["messages"][-1].content

    print(initial_review)

    with open(file="result.txt", mode="w", encoding="utf-8") as file:
        print(result, file=file)
