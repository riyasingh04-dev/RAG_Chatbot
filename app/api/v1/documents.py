from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, status
from typing import List
from app.services.document_processor import document_processor
from app.services.faiss_service import faiss_service
from app.core.config import settings
import os
import shutil
from loguru import logger

router = APIRouter()
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
