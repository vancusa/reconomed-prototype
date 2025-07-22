"""File handling utilities"""
import os
import uuid
from fastapi import HTTPException

def validate_file_type(file_content_type: str) -> bool:
    """Validate if file type is supported"""
    allowed_types = [
        "image/jpeg", 
        "image/png", 
        "image/jpg", 
        "application/pdf",
        "image/tiff",
        "image/bmp"
    ]
    return file_content_type in allowed_types

def generate_unique_filename(original_filename: str) -> str:
    """Generate unique filename preserving extension"""
    file_extension = original_filename.split(".")[-1] if "." in original_filename else "jpg"
    return f"{uuid.uuid4()}.{file_extension}"

def ensure_upload_directory():
    """Ensure upload directories exist"""
    directories = ["uploads", "static"]
    for directory in directories:
        os.makedirs(directory, exist_ok=True)

def save_uploaded_file(file_content: bytes, filename: str) -> str:
    """Save uploaded file and return file path"""
    try:
        ensure_upload_directory()
        file_path = f"uploads/{filename}"
        
        with open(file_path, "wb") as buffer:
            buffer.write(file_content)
            
        return file_path
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save file: {str(e)}")

def get_file_info(file_path: str) -> dict:
    """Get file information"""
    try:
        stat = os.stat(file_path)
        return {
            "size": stat.st_size,
            "created": stat.st_ctime,
            "modified": stat.st_mtime
        }
    except Exception:
        return {"size": 0, "created": None, "modified": None}