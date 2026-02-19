import os
import sys

# Add project root to path
sys.path.append(os.getcwd())

from app.services.faiss_service import faiss_service
from app.core.config import settings
from loguru import logger

def patch_index_metadata():
    if faiss_service.vector_db is None:
        print("Vector DB is not loaded.")
        return

    print("Patching FAISS index metadata with image URLs...")
    count = 0
    for doc_id, doc in faiss_service.vector_db.docstore._dict.items():
        file_name = doc.metadata.get("file_name")
        page = doc.metadata.get("page")
        
        # document_processor uses 0-indexed pages for images
        if file_name and page is not None:
            image_filename = f"{file_name}_{page}.jpg"
            image_path = os.path.join("static", "extracted_images", image_filename)
            
            if os.path.exists(image_path):
                doc.metadata["image_url"] = f"/static/extracted_images/{image_filename}"
                count += 1
    
    if count > 0:
        print(f"Patched {count} documents with image_url.")
        print("Saving index...")
        faiss_service.vector_db.save_local(faiss_service.index_path)
        print("Index saved successfully.")
    else:
        print("No documents were patched. Please check if images exist in static/extracted_images.")

if __name__ == "__main__":
    patch_index_metadata()
