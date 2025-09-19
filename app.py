from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel
from typing import Union, Optional
import traceback
from datetime import datetime
from config import config
from pdfengine.pdfgenerator import (
    DocumentSpecification, 
    ApplicationRunner,
    SupportedImageFormats,
    ProcessingError,
    NetworkError,
    DocumentValidationError
)
import subprocess
import os
# Create FastAPI app instance
app = FastAPI(
    title=config.title,
    description=config.description,
    version=config.version,
    debug=config.debug
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.allow_origins,
    allow_credentials=config.allow_credentials,
    allow_methods=config.allow_methods,
    allow_headers=config.allow_headers,
)

# Pydantic models for input validation
class NumberInput(BaseModel):
    value: Union[int, float]

class NumberOutput(BaseModel):
    original_value: Union[int, float]
    doubled_value: Union[int, float]

class PDFGenerationRequest(BaseModel):
    token: str
    output_format: Optional[str] = "jpeg"
    resolution: Optional[int] = 3000
    enable_ocr: Optional[bool] = True
    preserve_links: Optional[bool] = True

class PDFGenerationResponse(BaseModel):
    message: str
    token: str
    file_size_bytes: int

# Root endpoint
@app.get("/")
async def root():
    return {
        "message": "Welcome to the Resume PDF Generator API!", 
        "endpoints": {
            "POST /generate-pdf": "Generate PDF from resume token",
            "POST /double": "Double a number",
            "GET /health": "Health check"
        }
    }

# PDF Generation endpoint
@app.post("/generate-pdf")
async def generate_pdf(request: PDFGenerationRequest):
    """
    Generate PDF from resume token using the existing PDF generation logic.
    
    - **token**: Resume token for PDF generation
    - **output_format**: Image format (jpeg, png, webp) - default: jpeg
    - **resolution**: Image resolution - default: 3000
    - **enable_ocr**: Enable OCR processing - default: true
    - **preserve_links**: Preserve clickable links - default: true
    
    Returns PDF file as bytes with appropriate headers.
    """
    try:
        print(f"[{datetime.now()}] --- PDF Generation starting for token: {request.token[:8]} ---")
        # Validate token
        if not request.token or request.token.strip() == "":
            raise HTTPException(status_code=400, detail="Token cannot be empty")
        
        # Validate output format
        try:
            output_format = SupportedImageFormats(request.output_format.lower())
        except ValueError:
            raise HTTPException(
                status_code=400, 
                detail=f"Unsupported output format: {request.output_format}. Supported formats: jpeg, png, webp"
            )
        
        # Validate resolution
        if request.resolution < config.min_resolution or request.resolution > config.max_resolution:
            raise HTTPException(
                status_code=400, 
                detail=f"Resolution must be between {config.min_resolution} and {config.max_resolution}"
            )
        
        # Create document specification
        document_spec = DocumentSpecification(
            access_token=request.token.strip(),
            output_format=output_format,
            image_resolution=request.resolution,
            enable_ocr=request.enable_ocr,
            preserve_links=request.preserve_links
        )
        
        # Initialize the application runner and generate PDF
        app_runner = ApplicationRunner()
        print(f"[{datetime.now()}] Calling execute_document_conversion...")
        pdf_bytes = app_runner.execute_document_conversion(request.token.strip())
        print(f"[{datetime.now()}] Document conversion finished. PDF size: {len(pdf_bytes) if pdf_bytes else 0} bytes.")
        
        if pdf_bytes is None:
            raise HTTPException(
                status_code=500, 
                detail="PDF generation failed - no content returned"
            )
        
        # Return PDF as binary response with appropriate headers
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename=resume_{request.token[:8]}.pdf",
                "Content-Length": str(len(pdf_bytes)),
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "Pragma": "no-cache",
                "Expires": "0"
            }
        )
        
    except DocumentValidationError as e:
        raise HTTPException(status_code=400, detail=f"Validation error: {str(e)}")
    except NetworkError as e:
        raise HTTPException(status_code=502, detail=f"Network error: {str(e)}")
    except ProcessingError as e:
        raise HTTPException(status_code=500, detail=f"Processing error: {str(e)}")
    except HTTPException:
        # Re-raise HTTPExceptions as-is
        raise
    except Exception as e:
        # Log the full traceback for debugging
        error_trace = traceback.format_exc()
        print(f"Unexpected error in PDF generation: {error_trace}")
        raise HTTPException(
            status_code=500, 
            detail=f"Internal server error: {str(e)}"
        )

# Double endpoint
@app.post("/double", response_model=NumberOutput)
async def double_number(input_data: NumberInput):
    try:
        doubled = input_data.value * 2
        return NumberOutput(
            original_value=input_data.value,
            doubled_value=doubled
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error processing input: {str(e)}")

# Health check endpoint
@app.get("/health")
async def health_check():
    return {"status": "healthy"}
port = int(os.environ.get("PORT", 8080))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app, 
        host=config.host, 
        port=port,
        reload=config.debug
    )
