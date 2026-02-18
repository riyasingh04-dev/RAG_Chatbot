from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, status
from typing import List
from app.services.document_processor import document_processor
from app.services.faiss_service import faiss_service
from app.core.config import settings
import os
import shutil
from loguru import logger

router = APIRouter()
@router.get("")
async def list_documents():
    """Returns a list of all uploaded filenames."""
    if not os.path.exists(settings.UPLOAD_DIR):
        return []
    files = [f for f in os.listdir(settings.UPLOAD_DIR) if os.path.isfile(os.path.join(settings.UPLOAD_DIR, f))]
    return files

@router.post("/upload")
async def upload_documents(files: List[UploadFile] = File(...)):
    uploaded_paths = []
    for file in files:
        file_path = os.path.join(settings.UPLOAD_DIR, file.filename)
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        uploaded_paths.append(file_path)
    
    # Use the new document_processor which has OCR and metadata enrichment
    try:
        chunks = document_processor.process_documents(uploaded_paths)
        if chunks:
            # Use the new faiss_service which has BM25 and Hybrid Search
            faiss_service.add_documents(chunks)
            return {"message": "Files indexed successfully", "files": [f.filename for f in files]}
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, 
                detail="No text extracted from documents. If these are scans/handwritten, ensure Tesseract and Poppler are installed."
            )
    except Exception as e:
        logger.error(f"Upload failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@router.get("/status")
async def get_status():
    return {"status": "online", "model": settings.MODEL_NAME}

@router.delete("/{filename}")
async def delete_document(filename: str):
    try:
        # 1. Delete from storage
        file_path = os.path.join(settings.UPLOAD_DIR, filename)
        if os.path.exists(file_path):
            os.remove(file_path)
            logger.info(f"Deleted file from storage: {file_path}")
        else:
            logger.warning(f"File not found in storage: {file_path}")

        # 2. Delete page previews if they exist
        output_dir = os.path.join(os.getcwd(), "static", "extracted_images")
        if os.path.exists(output_dir):
            for img_file in os.listdir(output_dir):
                if img_file.startswith(filename):
                    try:
                        os.remove(os.path.join(output_dir, img_file))
                        logger.info(f"Deleted preview image: {img_file}")
                    except Exception as e:
                        logger.error(f"Failed to delete preview image {img_file}: {e}")

        # 3. Delete from FAISS & BM25
        faiss_service.delete_documents_by_file(filename)

        return {"message": "File and embeddings deleted successfully", "filename": filename}
    except Exception as e:
        logger.error(f"Deletion failed for {filename}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Deletion failed: {str(e)}"
        )
