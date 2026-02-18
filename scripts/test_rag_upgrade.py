import os
import sys
import asyncio
from typing import List

# Mocking app context
sys.path.append(os.getcwd())

from app.services.document_processor import document_processor
from app.services.faiss_service import faiss_service
from app.services.rag_pipeline import rag_retriever
from app.services.llm_service import llm_service
from langchain_core.documents import Document

async def test_pipeline():
    print("--- 1. Testing Document Processing ---")
    # Mock some chunks
    chunks = [
        Document(page_content="Candidate: John Doe. Weaknesses: Lack of experience in Rust.", metadata={"source": "resume.pdf", "file_name": "resume.pdf"}),
        Document(page_content="John Doe has a strong background in Python and RAG systems.", metadata={"source": "resume.pdf", "file_name": "resume.pdf"}),
        Document(page_content="Company policy: We value continuous learning.", metadata={"source": "policy.txt", "file_name": "policy.txt"})
    ]
    
    print(f"Adding {len(chunks)} mock chunks to FAISS and BM25...")
    faiss_service.add_documents(chunks)
    
    print("\n--- 2. Testing Hybrid Retrieval ---")
    query = "What are John Doe's weaknesses?"
    docs = rag_retriever.retrieve(query)
    
    print(f"Retrieved {len(docs)} documents.")
    for i, doc in enumerate(docs):
        print(f"Doc {i+1} [Source: {doc.metadata.get('file_name')}]: {doc.page_content[:50]}...")
        
    print("\n--- 3. Testing Context Generation ---")
    context = await rag_retriever.get_relevant_context(query)
    print("Formatted Context Preview:")
    print(context[:200])
    
    print("\n--- 4. Testing Role-Based Reasoning (Interviewer AI) ---")
    history = []
    role = "Interviewer AI"
    
    print(f"Generating streaming response for role: {role}...")
    full_response = ""
    async for chunk in llm_service.generate_response(query, context, role, history):
        full_response += chunk
        # print(chunk, end="", flush=True) # Uncomment for full output
    
    print("\nResponse matches expected SWOT analysis patterns?")
    if "Strengths" in full_response or "Weaknesses" in full_response:
        print("YES - Response contains SWOT analysis sections.")
    else:
        print("NO - Response might be too short or failed.")

    print("\nVerification Complete.")

if __name__ == "__main__":
    asyncio.run(test_pipeline())
