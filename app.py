from fastapi import FastAPI, UploadFile, File, HTTPException, Query
from fastapi.responses import JSONResponse
from markitdown import MarkItDown
import uvicorn
import uuid
import logging
import os
from pathlib import Path

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("MarkItDownAPI")

app = FastAPI(title="MarkItDown Resilient API")
md = MarkItDown()

# HARD INFRASTRUCTURE LIMIT: The client cannot override this.
HARD_MAX_MB = int(os.getenv("HARD_MAX_MB", 150))

def get_safe_extension(filename: str) -> str:
    if not filename or "." not in filename:
        return ""
    ext = filename.rsplit(".", 1)[-1].lower()
    return f".{ext}" if ext.isalnum() else ""

@app.post("/convert")
def convert_file(
    file: UploadFile = File(...),
    # Allow client to request a limit, defaulting to 100MB
    max_size_mb: int = Query(100, description="Max file size in MB")
):
    original_name = file.filename if file.filename else "unnamed_upload"
    safe_log_name = original_name.replace("\n", "").replace("\r", "")
    
    logger.info(f"INITIATED: Receiving {safe_log_name}")

    # ZERO TRUST CLAMPING: Take the lowest value between client request and server hard limit
    effective_max_mb = min(max_size_mb, HARD_MAX_MB)
    max_file_bytes = effective_max_mb * 1024 * 1024

    logger.info(f"ENFORCING LIMIT: {effective_max_mb}MB for request {safe_log_name}")

    safe_ext = get_safe_extension(original_name)
    temp_path = Path(f"/tmp/{uuid.uuid4().hex}{safe_ext}")
    
    file_size = 0
    try:
        with open(temp_path, "wb") as buffer:
            while chunk := file.file.read(8192):
                file_size += len(chunk)
                if file_size > max_file_bytes:
                    raise ValueError(f"File exceeds requested/clamped limit of {effective_max_mb}MB")
                buffer.write(chunk)

        logger.info(f"PROCESSING: {safe_log_name} -> mapped to {temp_path} (Size: {file_size} bytes)")

        result = md.convert(str(temp_path))
        
        if not result or not result.text_content:
            raise RuntimeError("MarkItDown returned empty content or failed silently.")

        logger.info(f"SUCCESS: {safe_log_name} parsed successfully.")
        return JSONResponse(status_code=200, content={"text": result.text_content})

    except ValueError as ve:
        logger.warning(f"REJECTED: {safe_log_name} - {str(ve)}")
        raise HTTPException(status_code=413, detail=str(ve))
    except Exception as e:
        logger.error(f"FAILED: Parsing {safe_log_name} - Exception: {str(e)}")
        raise HTTPException(status_code=500, detail="Document parsing failed or format is unsupported.")
    finally:
        file.file.close()
        if temp_path.exists():
            try:
                temp_path.unlink()
            except OSError as cleanup_error:
                logger.error(f"CLEANUP ERROR: Failed to remove temp file {temp_path}: {cleanup_error}")
