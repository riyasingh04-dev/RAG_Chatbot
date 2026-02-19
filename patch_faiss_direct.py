import os
import sys
import pickle

def patch_faiss_manually():
    index_path = "db/faiss_index"
    pkl_path = os.path.join(index_path, "index.pkl")
    
    if not os.path.exists(pkl_path):
        print("index.pkl not found.")
        return

    print("Loading index.pkl...")
    try:
        with open(pkl_path, "rb") as f:
            data = pickle.load(f)
        
        # Determine format
        if isinstance(data, tuple):
            if len(data) == 2:
                index, docstore = data
                index_to_docstore_id = None
            elif len(data) == 3:
                index, docstore, index_to_docstore_id = data
            else:
                print(f"Unknown tuple size: {len(data)}")
                return
        else:
            print(f"Unknown data type: {type(data)}")
            return
        
        # Access documents based on structure
        # If docstore is a dict, use it. If it has _dict, use that.
        docs_dict = {}
        if hasattr(docstore, '_dict'):
            docs_dict = docstore._dict
        elif isinstance(docstore, dict):
            docs_dict = docstore
        else:
            # Maybe it's a generic docstore with a search function or something?
            # Let's try to inspect it
            print(f"Docstore type: {type(docstore)}")
            print(f"Docstore attributes: {dir(docstore)}")
            return

        print(f"Loaded {len(docs_dict)} documents.")
        count = 0
        for doc_id, doc in docs_dict.items():
            file_name = doc.metadata.get("file_name")
            page = doc.metadata.get("page")
            
            if file_name and page is not None:
                image_filename = f"{file_name}_{page}.jpg"
                image_path = os.path.join("static", "extracted_images", image_filename)
                
                if os.path.exists(image_path):
                    doc.metadata["image_url"] = f"/static/extracted_images/{image_filename}"
                    count += 1
        
        if count > 0:
            print(f"Patched {count} documents.")
            print("Saving index.pkl...")
            with open(pkl_path, "wb") as f:
                if index_to_docstore_id is not None:
                    pickle.dump((index, docstore, index_to_docstore_id), f)
                else:
                    pickle.dump((index, docstore), f)
            print("Done.")
        else:
            print("No documents matched images.")
            
    except Exception as e:
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    patch_faiss_manually()
