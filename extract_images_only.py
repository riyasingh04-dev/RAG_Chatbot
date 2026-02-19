import os
from pdf2image import convert_from_path
from loguru import logger

def extract_images_from_existing():
    upload_dir = "data/uploads"
    output_dir = "static/extracted_images"
    os.makedirs(output_dir, exist_ok=True)
    
    # Path to Poppler from .env (hardcoded for this fix script based on what I saw)
    poppler_path = r"C:\Users\Riya Singh\Downloads\Release-24.08.0-0\poppler-24.08.0\Library\bin"
    
    files = [f for f in os.listdir(upload_dir) if f.lower().endswith('.pdf')]
    
    for filename in files:
        file_path = os.path.join(upload_dir, filename)
        logger.info(f"Processing {filename}...")
        try:
            images = convert_from_path(file_path, poppler_path=poppler_path)
            for i, image in enumerate(images):
                image_filename = f"{filename}_{i}.jpg"
                image_path = os.path.join(output_dir, image_filename)
                if not os.path.exists(image_path):
                    image.save(image_path, "JPEG")
                    logger.info(f"Saved {image_filename}")
        except Exception as e:
            logger.error(f"Failed to process {filename}: {e}")

if __name__ == "__main__":
    extract_images_from_existing()
