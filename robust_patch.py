import os
import sys
from unittest.mock import MagicMock

# 1. Mock the heavy-duty dependencies before anything else
sys.modules['langchain_community.embeddings'] = MagicMock()
sys.modules['langchain_huggingface'] = MagicMock()
sys.modules['langchain_groq'] = MagicMock()
sys.modules['faiss'] = MagicMock()

# Mock the embedding class specifically so it doesn't try to load torch/transformers
mock_embeddings = MagicMock()
sys.modules['app.services.faiss_service'].HuggingFaceEmbeddings = MagicMock(return_value=mock_embeddings)

# Add project root to path
sys.path.append(os.getcwd())

# 2. Patch the config to ensure correct paths
from app.core.config import settings
settings.TEXT_ONLY_MODE = False

# 3. Load the index via our service (it might still fail if it tries to load faiss.dll)
# If it does, we'll fall back to the direct pickle method but more carefully.
try:
    from app.services.faiss_service import faiss_service
    
    if faiss_service.vector_db is None:
        print("Vector DB failed to load via service. Trying direct pickle manipulation...")
        raise Exception("Service load failed")

    print(f"Service loaded index. Patching {len(faiss_service.vector_db.docstore._dict)} docs...")
    count = 0
    for doc_id, doc in faiss_service.vector_db.docstore._dict.items():
        file_name = doc.metadata.get("file_name")
        page = doc.metadata.get("page")
        if file_name and page is not None:
            image_filename = f"{file_name}_{page}.jpg"
            image_path = os.path.join("static", "extracted_images", image_filename)
            if os.path.exists(image_path):
                doc.metadata["image_url"] = f"/static/extracted_images/{image_filename}"
                count += 1
    
    if count > 0:
        # We need to save it. save_local might call faiss.write_index which is mocked.
        # So we use pickle directly.
        pkl_path = os.path.join(settings.INDEX_PATH, "index.pkl")
        with open(pkl_path, "wb") as f:
            # We assume it's (index, docstore, index_to_docstore_id)
            pickle_data = (
                faiss_service.vector_db.index, 
                faiss_service.vector_db.docstore, 
                faiss_service.vector_db.index_to_docstore_id
            )
            import pickle
            pickle.dump(pickle_data, f)
        print(f"Successfully patched {count} docs.")
    else:
        print("No matches found.")

except Exception as e:
    print(f"Service method failed: {e}. Trying fallback...")
    # Direct pickle fallback
    import pickle
    pkl_path = "db/faiss_index/index.pkl"
    if os.path.exists(pkl_path):
        with open(pkl_path, "rb") as f:
            data = pickle.load(f)
        
        # Unpack based on length
        index_to_id = None
        if len(data) == 2:
            idx, store = data
        else:
            idx, store, index_to_id = data
            
        print(f"Direct load success. Store type: {type(store)}")
        
        # Iterate over store - we saw it was a dict or had _dict
        docs_dict = getattr(store, '_dict', store)
        if isinstance(docs_dict, dict):
            count = 0
            for d_id, doc in docs_dict.items():
                # If doc is a string, we can't patch metadata. 
                # But LangChain usually pickles the whole Document object.
                if hasattr(doc, 'metadata'):
                    file_name = doc.metadata.get("file_name")
                    page = doc.metadata.get("page")
                    if file_name and page is not None:
                        img_fn = f"{file_name}_{page}.jpg"
                        if os.path.exists(f"static/extracted_images/{img_fn}"):
                            doc.metadata["image_url"] = f"/static/extracted_images/{img_fn}"
                            count += 1
            
            if count > 0:
                with open(pkl_path, "wb") as f:
                    if index_to_id:
                        pickle.dump((idx, store, index_to_id), f)
                    else:
                        pickle.dump((idx, store), f)
                print(f"Direct patch successful: {count} docs.")
            else:
                print("No docs patched in direct mode.")
