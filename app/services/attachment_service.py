import mimetypes
from typing import Tuple

ALLOWED_EXTENSIONS = {
    ".pdf",
    ".png",
    ".jpg",
    ".jpeg",
    ".tif",
    ".tiff",
    ".webp",
    ".xls",
    ".xlsx",
    ".csv",
    ".doc",
    ".docx",
    ".txt",
    ".rtf",
    ".html",
    ".htm",
    ".md",
}

EXTENSION_MIME_MAP = {
    ".pdf": "application/pdf",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".tif": "image/tiff",
    ".tiff": "image/tiff",
    ".webp": "image/webp",
    ".xls": "application/vnd.ms-excel",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".csv": "text/csv",
    ".doc": "application/msword",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".txt": "text/plain",
    ".rtf": "application/rtf",
    ".html": "text/html",
    ".htm": "text/html",
    ".md": "text/markdown",
}

class AttachmentService:
    @staticmethod
    def detect_content_type(filename: str, fallback_content_type: str = "application/octet-stream") -> str:
        ext = ""
        if "." in filename:
            ext = "." + filename.rsplit(".", 1)[-1].lower()
        
        if ext in EXTENSION_MIME_MAP:
            return EXTENSION_MIME_MAP[ext]
        
        guessed, _ = mimetypes.guess_type(filename)
        return guessed or fallback_content_type

    @staticmethod
    def is_allowed_file(filename: str) -> bool:
        if "." not in filename:
            return False
        ext = "." + filename.rsplit(".", 1)[-1].lower()
        return ext in ALLOWED_EXTENSIONS

    @staticmethod
    def format_file_size(size_in_bytes: int) -> str:
        if not size_in_bytes:
            return "0 B"
        if size_in_bytes < 1024:
            return f"{size_in_bytes} B"
        elif size_in_bytes < 1024 * 1024:
            return f"{size_in_bytes / 1024:.1f} KB"
        else:
            return f"{size_in_bytes / (1024 * 1024):.2f} MB"
