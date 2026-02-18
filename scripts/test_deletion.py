import os
import sys
import time

# Add project root to sys.path
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, ROOT)

from app.services.faiss_service import faiss_service
from langchain_core.documents import Document
from app.core.config import settings

def test_deletion():
    print("Starting deletion test...")
    
    # 1. Create a dummy file and chunks
    test_filename = "test_delete_me.txt"
    test_path = os.path.join(settings.UPLOAD_DIR, test_filename)
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    
    with open(test_path, "w") as f:
        f.write("This is a test file for deletion.")
    
    chunks = [
        Document(
            page_content="This is a test chunk.",
            metadata={"file_name": test_filename, "source": test_path}
        )
    ]
    
    # 2. Add to FAISS
    print(f"Adding documents for {test_filename} to FAISS...")
    faiss_service.add_documents(chunks)
    
    # Verify they were added
    initial_count = len(faiss_service.vector_db.docstore._dict)
    print(f"Initial doc count: {initial_count}")
    
    # 3. Delete documents by file
    print(f"Deleting documents for {test_filename}...")
    faiss_service.delete_documents_by_file(test_filename)
    
    # 4. Verify deletion
    final_count = len(faiss_service.vector_db.docstore._dict)
    print(f"Final doc count: {final_count}")
    
    # Check if test_filename exists in any metadata
    found = False
    for doc in faiss_service.vector_db.docstore._dict.values():
        if doc.metadata.get("file_name") == test_filename:
            found = True
            break
            
    if not found and final_count < initial_count:
        print("SUCCESS: Documents removed from FAISS/BM25.")
    else:
        print("FAILURE: Documents still exist in FAISS/BM25.")
        
    # Clean up file
    if os.path.exists(test_path):
        os.remove(test_path)
        print(f"Cleaned up test file: {test_path}")

if __name__ == "__main__":
    test_deletion()
