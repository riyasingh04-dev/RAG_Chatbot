import os
import sys

# Add project root to path
sys.path.append(os.getcwd())

from app.services.document_processor import document_processor
from app.services.faiss_service import faiss_service
from app.core.config import settings
from loguru import logger

def reprocess_all():
    upload_dir = settings.UPLOAD_DIR
    files = [os.path.join(upload_dir, f) for f in os.listdir(upload_dir) if os.path.isfile(os.path.join(upload_dir, f))]
    
    if not files:
        print("No files found in upload directory.")
        return

    print(f"Reprocessing {len(files)} files to extract images...")
    
    # Force TEXT_ONLY_MODE to False for this session
    settings.TEXT_ONLY_MODE = False
    
    # Process and re-index
    # Note: This will add new chunks. Ideally we should clear the index first or update metadata.
    # For now, we'll just process them to ensure images are generated in static/extracted_images.
    chunks = document_processor.process_documents(files)
    
    if chunks:
        print(f"Successfully processed {len(chunks)} chunks.")
        print("Re-indexing to include image metadata...")
        faiss_service.add_documents(chunks)
        print("Re-indexing complete. New chunks with images are now available.")
    else:
        print("Failed to process documents.")

if __name__ == "__main__":
    # Ensure static directory exists
    os.makedirs("static/extracted_images", exist_ok=True)
    reprocess_all()
