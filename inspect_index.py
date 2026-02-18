"""
Diagnostic script to inspect FAISS index and verify indexed documents.
Run this to see what documents are actually in the knowledge base.
"""

from app.services.faiss_service import faiss_service
from loguru import logger

def inspect_faiss_index():
    """Inspect the FAISS index to see what documents are stored."""
    
    if not faiss_service.vector_db:
        print("❌ No FAISS index found!")
        return
    
    # Get all documents from the docstore
    docstore = faiss_service.vector_db.docstore
    all_docs = list(docstore._dict.values())
    
    print(f"\n📊 Total documents in index: {len(all_docs)}")
    print("=" * 80)
    
    # Group by filename
    file_groups = {}
    for doc in all_docs:
        filename = doc.metadata.get('file_name', 'Unknown')
        if filename not in file_groups:
            file_groups[filename] = []
        file_groups[filename].append(doc)
    
    # Display summary
    print(f"\n📁 Files indexed: {len(file_groups)}")
    for filename, docs in file_groups.items():
        print(f"\n  📄 {filename}")
        print(f"     Chunks: {len(docs)}")
        print(f"     First chunk preview: {docs[0].page_content[:100]}...")
    
    print("\n" + "=" * 80)
    
    # Test retrieval with specific query
    print("\n🔍 Testing retrieval with query: 'Riya experience'")
    from app.services.rag_pipeline import rag_retriever
    results = rag_retriever.retrieve("Riya experience")
    
    print(f"\n📋 Retrieved {len(results)} documents:")
    for i, doc in enumerate(results, 1):
        print(f"\n  {i}. {doc.metadata.get('file_name', 'Unknown')}")
        print(f"     Content: {doc.page_content[:150]}...")
    
    print("\n" + "=" * 80)
    
    # Test with comparison query
    print("\n🔍 Testing retrieval with query: 'compare Piyush and Riya experience'")
    results = rag_retriever.retrieve("compare Piyush and Riya experience")
    
    print(f"\n📋 Retrieved {len(results)} documents:")
    for i, doc in enumerate(results, 1):
        print(f"\n  {i}. {doc.metadata.get('file_name', 'Unknown')}")
        print(f"     Content: {doc.page_content[:150]}...")

if __name__ == "__main__":
    inspect_faiss_index()
