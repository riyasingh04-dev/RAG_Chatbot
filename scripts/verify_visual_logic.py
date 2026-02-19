import asyncio
import sys
import os
from unittest.mock import MagicMock

# Mock heavy dependencies before importing RAG components
sys.modules['langchain_community.vectorstores'] = MagicMock()
sys.modules['langchain_community.embeddings'] = MagicMock()
sys.modules['langchain_groq'] = MagicMock()
sys.modules['faiss'] = MagicMock()

# Add project root to path
sys.path.append(os.getcwd())

# Mock the services that RagRetriever depends on at module level
import app.services.faiss_service
app.services.faiss_service.faiss_service = MagicMock()
import app.services.reranker
app.services.reranker.reranker = MagicMock()
import app.services.llm_service
app.services.llm_service.llm_service = MagicMock()

from app.services.rag_pipeline import RagRetriever
from langchain_core.documents import Document
from app.services.prompts import get_sys_prompt

async def test_visual_retrieval_logic():
    print("\n--- Testing Visual Retrieval Logic ---")
    retriever = RagRetriever()
    
    # Test visual query detection
    query = "show graph of profits"
    is_visual = retriever._is_visual_query(query)
    print(f"Query: '{query}' -> Is visual? {is_visual}")
    assert is_visual == True
    
    query = "explain profits"
    is_visual = retriever._is_visual_query(query)
    print(f"Query: '{query}' -> Is visual? {is_visual}")
    assert is_visual == False

def test_prompt_visual_rules():
    print("\n--- Testing Prompt Visual Rules ---")
    role = "Research AI"
    context = "[Source: doc1.pdf (Pg 1)]\n[Image Reference: /static/graph.jpg]\nData about profits."
    query = "show graph of profits"
    
    # History can be a string as formatted in llm_service
    prompt = get_sys_prompt(role, context, "No history", query)
    
    print("Checking if VISUAL RESPONSE RULES are in prompt...")
    assert "VISUAL RESPONSE RULES" in prompt
    assert "### VISUAL PRIORITY ORDER" in prompt
    assert "[Image Reference: /static/extracted_images/]" in prompt or "/static/" in prompt
    print("Prompt check passed.")

if __name__ == "__main__":
    asyncio.run(test_visual_retrieval_logic())
    test_prompt_visual_rules()
    print("\nVerification script finished successfully.")
