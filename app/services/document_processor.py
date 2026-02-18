import os
import time
import json
from typing import List
import pandas as pd
import nbformat
from bs4 import BeautifulSoup
from langchain_community.document_loaders import PyPDFLoader, TextLoader, Docx2txtLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_core.documents import Document
from loguru import logger
from app.core.config import settings

class DocumentProcessor:
    def __init__(self, chunk_size: int = 1500, chunk_overlap: int = 300):
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            length_function=len,
            separators=["\n\n", "\n", " ", ""]
        )

    def load_document(self, file_path: str) -> List[Document]:
        """Loads a document with OCR support and metadata enrichment."""
        ext = os.path.splitext(file_path)[-1].lower()
        file_name = os.path.basename(file_path)
        
        logger.info(f"Loading document: {file_name}")
        
        try:
            docs = []
            if ext == ".pdf":
                # Regular PDF loading
                loader = PyPDFLoader(file_path)
                docs = loader.load()
                
                docs = loader.load()
                
                # --- Visual RAG: Extract Images for Page Previews ---
                if not settings.TEXT_ONLY_MODE:
                    try:
                        import pytesseract
                        from pdf2image import convert_from_path
                        
                        # Ensure output directory exists (relative to app root or static folder)
                        # We'll save to d:\RAG_Chatbot\static\extracted_images
                        output_dir = os.path.join(os.getcwd(), "static", "extracted_images")
                        os.makedirs(output_dir, exist_ok=True)
                        
                        # Configure Poppler
                        poppler_path = settings.POPPLER_PATH.strip('"\'') if settings.POPPLER_PATH else None
                        if poppler_path and not os.path.exists(poppler_path):
                             # Try auto-correction logic again just in case
                             if os.path.exists(os.path.join(poppler_path, "Library", "bin")):
                                 poppler_path = os.path.join(poppler_path, "Library", "bin")
                             elif os.path.exists(os.path.join(poppler_path, "bin")):
                                 poppler_path = os.path.join(poppler_path, "bin")
    
                        logger.info(f"Generating page previews for: {file_name}")
                        images = convert_from_path(file_path, poppler_path=poppler_path)
                        
                        # Save images and update doc metadata
                        # We map images to docs by page number. PyPDFLoader pages are 0-indexed.
                        for i, image in enumerate(images):
                            image_filename = f"{file_name}_{i}.jpg"
                            image_path = os.path.join(output_dir, image_filename)
                            image.save(image_path, "JPEG")
                            
                            # Find the matching document chunk (or chunks) for this page
                            # Note: PyPDFLoader might split a page into multiple docs if using specific splitters, 
                            # but standard load() usually gives one doc per page.
                            for doc in docs:
                                if doc.metadata.get("page") == i:
                                    doc.metadata["image_url"] = f"/static/extracted_images/{image_filename}"
                                    
                        logger.info(f"Saved {len(images)} page previews for {file_name}")
    
                    except Exception as img_err:
                        logger.error(f"Failed to generate page previews for {file_name}: {img_err}")
                        # Non-fatal: continue with text only
                else:
                    logger.info(f"Skipping page preview generation for {file_name} (TEXT_ONLY_MODE enabled)")
                # ----------------------------------------------------

                # check if the PDF is scanned or empty
                text_content = "".join([doc.page_content for doc in docs]).strip()
                if len(text_content) < 100:
                    logger.warning(f"PDF {file_name} seems to be scanned or empty. Attempting OCR...")
                    try:
                        import pytesseract
                        from pdf2image import convert_from_path
                        
                        # Apply manual paths if configured and not placeholders
                        if settings.TESSERACT_PATH:
                            logger.error(f"DEBUG: TESSERACT_PATH from settings is: '{settings.TESSERACT_PATH}'")
                            logger.error(f"DEBUG: TESSERACT_PATH from os.environ is: '{os.environ.get('TESSERACT_PATH')}'")
                            
                            clean_t_path = settings.TESSERACT_PATH.strip('"\'')
                            if "setup" in clean_t_path.lower() and clean_t_path.endswith(".exe"):
                                raise Exception(f"TESSERACT_PATH points to an INSTALLER. Please run the installer first, then point to 'C:\\Program Files\\Tesseract-OCR\\tesseract.exe'")
                            
                            if not os.path.exists(clean_t_path):
                                raise Exception(f"Tesseract path does not exist: {clean_t_path}")
                                
                            pytesseract.pytesseract.tesseract_cmd = clean_t_path
                            logger.info(f"Using custom Tesseract path: {clean_t_path}")
                        
                        poppler_path = settings.POPPLER_PATH.strip('"\'') if settings.POPPLER_PATH else None
                        if poppler_path:
                            # Validation for Poppler path
                            if not poppler_path.lower().endswith("bin"):
                                logger.warning(f"POPPLER_PATH might be missing '/bin'. Checking subfolders...")
                                potential_bin = os.path.join(poppler_path, "Library", "bin")
                                if os.path.exists(potential_bin):
                                    poppler_path = potential_bin
                                    logger.info(f"Automatically corrected Poppler path to: {poppler_path}")
                                else:
                                    potential_bin = os.path.join(poppler_path, "bin")
                                    if os.path.exists(potential_bin):
                                        poppler_path = potential_bin
                                        logger.info(f"Automatically corrected Poppler path to: {poppler_path}")

                            if not os.path.exists(poppler_path):
                                raise Exception(f"Poppler path does not exist: {poppler_path}. It must be the 'bin' folder.")
                            
                            logger.info(f"Using custom Poppler path: {poppler_path}")

                        # Check if tesseract is available
                        try:
                            tesseract_version = pytesseract.get_tesseract_version()
                            logger.info(f"Tesseract version: {tesseract_version}")
                        except Exception as t_err:
                            logger.error(f"Tesseract not found: {t_err}")
                            raise Exception("Tesseract OCR not found. Please install it and/or set TESSERACT_PATH in .env")

                        # Convert PDF pages to images
                        logger.info(f"Converting PDF to images for OCR: {file_name}")
                        start_time = time.time()
                        images = convert_from_path(file_path, poppler_path=poppler_path)
                        logger.info(f"Converted {len(images)} pages in {time.time() - start_time:.2f}s")
                        
                        ocr_docs = []
                        for i, image in enumerate(images):
                            logger.info(f"Processing page {i+1}/{len(images)} for {file_name}...")
                            page_start = time.time()
                            text = pytesseract.image_to_string(image)
                            logger.info(f"Page {i+1} OCR finished in {time.time() - page_start:.2f}s")
                            if text.strip():
                                ocr_docs.append(Document(
                                    page_content=text,
                                    metadata={"source": file_path, "page": i+1}
                                ))
                        
                        if ocr_docs:
                            docs = ocr_docs
                            logger.info(f"OCR successful for {file_name}. Extracted {len(ocr_docs)} pages.")
                        else:
                            logger.warning(f"No text extracted via OCR for {file_name}")
                            
                    except Exception as ocr_err:
                        error_msg = str(ocr_err)
                        if "poppler" in error_msg.lower():
                            logger.error(f"Poppler not found: {error_msg}. OCR skipped.")
                        elif "tesseract" in error_msg.lower():
                            logger.error(f"Tesseract not found: {error_msg}. OCR skipped.")
                        else:
                            logger.error(f"OCR failed for {file_name}: {ocr_err}")
                        
                        # Re-raise IF it's a specific configuration error the user needs to see
                        if "INSTALLER" in error_msg or "path does not exist" in error_msg or "Tesseract OCR not found" in error_msg:
                            raise ocr_err

                        # Fallback: if we have some text from PyPDFLoader, keep it.
                        if not docs:
                            logger.error(f"Absolutely no text could be extracted from {file_name}")
            
            elif ext == ".docx":
                loader = Docx2txtLoader(file_path)
                docs = loader.load()
            
            elif ext == ".txt":
                loader = TextLoader(file_path)
                docs = loader.load()
            
            elif ext == ".csv":
                try:
                    df = pd.read_csv(file_path)
                    # convert rows to a readable text representation
                    text = df.to_string(index=False)
                    docs = [Document(page_content=text)]
                except Exception as csv_err:
                    logger.error(f"Failed to load CSV {file_name}: {csv_err}")
                    return []

            elif ext in [".xlsx", ".xls"]:
                try:
                    sheets = pd.read_excel(file_path, sheet_name=None)
                    docs = []
                    for sheet_name, df in sheets.items():
                        text = f"Sheet: {sheet_name}\n{df.to_string(index=False)}"
                        docs.append(Document(page_content=text))
                except Exception as xl_err:
                    logger.error(f"Failed to load Excel file {file_name}: {xl_err}")
                    return []

            elif ext == ".json":
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    pretty = json.dumps(data, indent=2, ensure_ascii=False)
                    docs = [Document(page_content=pretty)]
                except Exception as json_err:
                    logger.error(f"Failed to load JSON {file_name}: {json_err}")
                    return []

            elif ext == ".ipynb":
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        notebook = nbformat.read(f, as_version=4)

                    cells = []
                    for cell in notebook.cells:
                        if cell.get("cell_type") == "markdown":
                            cells.append(cell.get("source", ""))
                        elif cell.get("cell_type") == "code":
                            cells.append("Code:\n" + cell.get("source", ""))

                    docs = [Document(page_content="\n\n".join(cells))]
                except Exception as nb_err:
                    logger.error(f"Failed to load notebook {file_name}: {nb_err}")
                    return []

            elif ext == ".py":
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        code = f.read()
                    docs = [Document(page_content=code)]
                except Exception as py_err:
                    logger.error(f"Failed to load python file {file_name}: {py_err}")
                    return []

            elif ext in [".html", ".htm"]:
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        soup = BeautifulSoup(f, "html.parser")
                        
                    # Remove script and style elements
                    for script in soup(["script", "style"]):
                        script.decompose()
                        
                    text = soup.get_text(separator="\n")
                    # Clean up whitespace
                    lines = (line.strip() for line in text.splitlines())
                    chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
                    text = '\n'.join(chunk for chunk in chunks if chunk)
                    
                    if len(text) < 50:
                        raise Exception("Uploaded file contains insufficient readable text")
                        
                    docs = [Document(page_content=text)]
                except Exception as html_err:
                    logger.error(f"Failed to load HTML file {file_name}: {html_err}")
                    # Raise validation error to user if strictly invalid
                    if "insufficient readable text" in str(html_err):
                         raise html_err
                    return []
            
            
            else:
                logger.warning(f"Unsupported extension: {ext}")
                return []

            # Enrich metadata
            for doc in docs:
                doc.metadata.update({
                    "source": file_path,
                    "file_name": file_name,
                    "document_type": ext,
                    "indexed_at": time.time()
                })
                
            return docs
            
        except Exception as e:
            logger.error(f"Error loading {file_path}: {e}")
            if "TESSERACT_PATH" in str(e) or "Poppler path" in str(e) or "Tesseract path" in str(e):
                raise e # Propagate configuration errors to the UI
            return []

    def process_documents(self, file_paths: List[str]) -> List[Document]:
        """Processes multiple documents and returns enriched chunks."""
        all_docs = []
        for path in file_paths:
            docs = self.load_document(path)
            all_docs.extend(docs)
        
        if not all_docs:
            logger.warning("No documents were loaded.")
            return []
            
        chunks = self.text_splitter.split_documents(all_docs)
        
        # Add chunk_id to metadata
        import uuid
        for i, chunk in enumerate(chunks):
            chunk.metadata["chunk_id"] = str(uuid.uuid4())
            chunk.metadata["chunk_index"] = i
            
        logger.info(f"Created {len(chunks)} chunks from {len(file_paths)} files.")
        
        return chunks

document_processor = DocumentProcessor()

