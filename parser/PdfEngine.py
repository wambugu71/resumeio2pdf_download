import io
import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol, List, Dict, Any, Optional, Union
from contextlib import contextmanager
import pytesseract
import requests
from PIL import Image
from pypdf import PdfReader, PdfWriter
from pypdf.generic import AnnotationBuilder
from enum import Enum
from fastapi import HTTPException


class SupportedImageFormats(str, Enum):
    """Enumeration of supported image formats for document processing."""
    JPEG = "jpeg"
    PNG = "png"
    WEBP = "webp"


class ProcessingError(Exception):
    """Custom exception for document processing errors."""
    pass


class NetworkError(ProcessingError):
    """Exception raised for network-related errors."""
    pass


class DocumentValidationError(ProcessingError):
    """Exception raised for document validation errors."""
    pass


class HttpClientProtocol(Protocol):
    """Protocol defining the interface for HTTP client implementations."""
    
    def execute_request(self, url: str, headers: Dict[str, str]) -> requests.Response:
        """Execute an HTTP request."""
        ...


class ImageProcessorProtocol(Protocol):
    """Protocol defining the interface for image processing operations."""
    
    def convert_image_to_pdf(self, image_buffer: io.BytesIO) -> bytes:
        """Convert image data to PDF format."""
        ...


class MetadataHandlerProtocol(Protocol):
    """Protocol defining the interface for metadata handling."""
    
    def extract_page_info(self, raw_data: str) -> List[Dict[str, Any]]:
        """Extract page information from raw metadata."""
        ...


@dataclass
class ServiceConfiguration:
    """Configuration settings for the document service."""
    base_url: str = "https://ssr.resume.tools"
    metadata_endpoint: str = "/meta/{token}?cache={timestamp}"
    image_endpoint: str = "/to-image/{token}-{page}.{format}?cache={timestamp}&size={size}"
    default_resolution: int = 3000
    request_timeout: int = 30
    user_agent: str = field(default_factory=lambda: (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/136.0.0.0 Safari/537.36"
    ))


@dataclass
class DocumentSpecification:
    """Specification for document processing parameters."""
    access_token: str
    output_format: SupportedImageFormats = SupportedImageFormats.JPEG
    image_resolution: int = 3000
    enable_ocr: bool = True
    preserve_links: bool = True
    
    def __post_init__(self):
        """Validate the document specification."""
        if not self.access_token:
            raise DocumentValidationError("Access token cannot be empty")
        if self.image_resolution < 100:
            raise DocumentValidationError("Image resolution must be at least 100")


class TimestampGenerator:
    """Utility class for generating timestamps."""
    
    @staticmethod
    def get_current_utc_timestamp() -> str:
        """Generate current UTC timestamp in ISO format."""
        return datetime.utcnow().isoformat()[:-4] + "Z"


class HttpRequestExecutor(HttpClientProtocol):
    """Concrete implementation of HTTP client for making requests."""
    
    def __init__(self, config: ServiceConfiguration):
        self._config = config
    
    def execute_request(self, url: str, headers: Dict[str, str]) -> requests.Response:
        """Execute HTTP GET request with error handling."""
        try:
            response = requests.get(
                url, 
                headers=headers, 
                timeout=self._config.request_timeout
            )
            if response.status_code != 200:
                raise NetworkError(
                    f"HTTP request failed with status {response.status_code}: {response.text}"
                )
            return response
        except requests.RequestException as e:
            raise NetworkError(f"Network request failed: {str(e)}")


class DocumentMetadataProcessor(MetadataHandlerProtocol):
    """Processor for handling document metadata operations."""
    
    def extract_page_info(self, raw_metadata: str) -> List[Dict[str, Any]]:
        """Parse and extract page information from raw JSON metadata."""
        try:
            parsed_data: Dict[str, Any] = json.loads(raw_metadata)
            page_data = parsed_data.get("pages", [])
            if not page_data:
                raise DocumentValidationError("No page data found in metadata")
            return page_data
        except json.JSONDecodeError as e:
            raise DocumentValidationError(f"Invalid JSON metadata: {str(e)}")


class ImageToPdfConverter(ImageProcessorProtocol):
    """Converter for transforming images to PDF format using OCR."""
    
    def __init__(self, enable_ocr: bool = True):
        self._enable_ocr = enable_ocr
    
    def convert_image_to_pdf(self, image_buffer: io.BytesIO) -> bytes:
        """Convert image buffer to PDF bytes using Tesseract OCR."""
        try:
            if self._enable_ocr:
                return pytesseract.image_to_pdf_or_hocr(
                    Image.open(image_buffer), 
                    extension="pdf", 
                    config="--dpi 300"
                )
            else:
                # Fallback: create simple PDF without OCR
                img = Image.open(image_buffer)
                pdf_buffer = io.BytesIO()
                img.save(pdf_buffer, format='PDF')
                return pdf_buffer.getvalue()
        except Exception as e:
            raise ProcessingError(f"Image to PDF conversion failed: {str(e)}")


class UrlBuilder:
    """Builder class for constructing service URLs."""
    
    def __init__(self, config: ServiceConfiguration):
        self._config = config
    
    def build_metadata_url(self, token: str, timestamp: str) -> str:
        """Build URL for fetching document metadata."""
        endpoint = self._config.metadata_endpoint.format(
            token=token, 
            timestamp=timestamp
        )
        return self._config.base_url + endpoint
    
    def build_image_url(self, token: str, page_number: int, 
                       image_format: str, timestamp: str, resolution: int) -> str:
        """Build URL for fetching page images."""
        endpoint = self._config.image_endpoint.format(
            token=token,
            page=page_number,
            format=image_format,
            timestamp=timestamp,
            size=resolution
        )
        return self._config.base_url + endpoint


class LinkAnnotationBuilder:
    """Builder for creating PDF link annotations."""
    
    @staticmethod
    def create_link_annotation(link_data: Dict[str, Any], scale_factor: float) -> Dict[str, Any]:
        """Create a link annotation with proper scaling."""
        target_url = link_data.pop("url")
        scaled_coords = {key: value * scale_factor for key, value in link_data.items()}
        x_coord, y_coord, width, height = scaled_coords.values()
        
        return {
            'annotation': AnnotationBuilder.link(
                rect=(x_coord, y_coord, x_coord + width, y_coord + height),
                url=target_url
            ),
            'coordinates': (x_coord, y_coord, width, height)
        }


class RemoteDocumentFetcher:
    """Service for fetching document data from remote endpoints."""
    
    def __init__(self, http_client: HttpClientProtocol, 
                 url_builder: UrlBuilder, config: ServiceConfiguration):
        self._http_client = http_client
        self._url_builder = url_builder
        self._config = config
    
    def fetch_document_metadata(self, spec: DocumentSpecification, timestamp: str) -> str:
        """Fetch raw metadata for the document."""
        metadata_url = self._url_builder.build_metadata_url(spec.access_token, timestamp)
        headers = {"User-Agent": self._config.user_agent}
        response = self._http_client.execute_request(metadata_url, headers)
        return response.text
    
    def fetch_page_image(self, spec: DocumentSpecification, page_num: int, 
                        timestamp: str) -> io.BytesIO:
        """Fetch image data for a specific page."""
        image_url = self._url_builder.build_image_url(
            spec.access_token, page_num, spec.output_format.value,
            timestamp, spec.image_resolution
        )
        headers = {"User-Agent": self._config.user_agent}
        response = self._http_client.execute_request(image_url, headers)
        return io.BytesIO(response.content)


class PdfDocumentAssembler:
    """Assembler for creating PDF documents from processed components."""
    
    def __init__(self, image_converter: ImageProcessorProtocol,
                 link_builder: LinkAnnotationBuilder):
        self._image_converter = image_converter
        self._link_builder = link_builder
    
    def assemble_document(self, image_buffers: List[io.BytesIO], 
                         page_metadata: List[Dict[str, Any]]) -> bytes:
        """Assemble final PDF document from image buffers and metadata."""
        pdf_writer = PdfWriter()
        
        if not image_buffers or not page_metadata:
            raise DocumentValidationError("Cannot assemble document: missing image data or metadata")
        
        viewport_info = page_metadata[0].get("viewport", {})
        reference_width = viewport_info.get("width", 1)
        reference_height = viewport_info.get("height", 1)
        
        for page_index, image_buffer in enumerate(image_buffers):
            # Convert image to PDF page
            pdf_page_data = self._image_converter.convert_image_to_pdf(image_buffer)
            current_page = PdfReader(io.BytesIO(pdf_page_data)).pages[0]
            
            # Calculate scaling factor
            page_scale = max(
                current_page.mediabox.height / reference_height,
                current_page.mediabox.width / reference_width
            )
            
            pdf_writer.add_page(current_page)
            
            # Add link annotations if available
            if page_index < len(page_metadata):
                page_links = page_metadata[page_index].get("links", [])
                for link_info in page_links:
                    link_annotation_data = self._link_builder.create_link_annotation(
                        link_info.copy(), page_scale
                    )
                    pdf_writer.add_annotation(
                        page_number=page_index,
                        annotation=link_annotation_data['annotation']
                    )
        
        # Generate final PDF bytes
        with io.BytesIO() as output_stream:
            pdf_writer.write(output_stream)
            return output_stream.getvalue()


class DocumentProcessingOrchestrator:
    """Main orchestrator that coordinates the document processing workflow."""
    
    def __init__(self, config: ServiceConfiguration):
        self._config = config
        self._timestamp_gen = TimestampGenerator()
        self._http_client = HttpRequestExecutor(config)
        self._url_builder = UrlBuilder(config)
        self._metadata_processor = DocumentMetadataProcessor()
        self._image_converter = ImageToPdfConverter()
        self._link_builder = LinkAnnotationBuilder()
        self._document_fetcher = RemoteDocumentFetcher(
            self._http_client, self._url_builder, config
        )
        self._pdf_assembler = PdfDocumentAssembler(
            self._image_converter, self._link_builder
        )
    
    def process_document(self, specification: DocumentSpecification) -> bytes:
        """Execute the complete document processing workflow."""
        try:
            # Generate timestamp for caching
            processing_timestamp = self._timestamp_gen.get_current_utc_timestamp()
            
            # Fetch and process metadata
            raw_metadata = self._document_fetcher.fetch_document_metadata(
                specification, processing_timestamp
            )
            page_info = self._metadata_processor.extract_page_info(raw_metadata)
            
            # Fetch all page images
            page_images = []
            total_pages = len(page_info)
            
            for page_number in range(1, total_pages + 1):
                image_data = self._document_fetcher.fetch_page_image(
                    specification, page_number, processing_timestamp
                )
                page_images.append(image_data)
            
            # Assemble final PDF document
            pdf_document = self._pdf_assembler.assemble_document(page_images, page_info)
            
            return pdf_document
            
        except Exception as e:
            if isinstance(e, (ProcessingError, NetworkError, DocumentValidationError)):
                raise
            else:
                raise ProcessingError(f"Unexpected error during processing: {str(e)}")


class DocumentProcessorFacade:
    """Facade providing a simplified interface for document processing."""
    
    def __init__(self, custom_config: Optional[ServiceConfiguration] = None):
        self._config = custom_config or ServiceConfiguration()
        self._orchestrator = DocumentProcessingOrchestrator(self._config)
    
    def convert_remote_document_to_pdf(self, access_token: str, 
                                     output_format: SupportedImageFormats = SupportedImageFormats.JPEG,
                                     resolution: int = 3000) -> bytes:
        """Simplified method to convert remote document to PDF."""
        document_spec = DocumentSpecification(
            access_token=access_token,
            output_format=output_format,
            image_resolution=resolution
        )
        return self._orchestrator.process_document(document_spec)


class FileOutputManager:
    """Manager for handling file output operations."""
    
    @staticmethod
    @contextmanager
    def create_output_file(file_path: str):
        """Context manager for safe file output operations."""
        try:
            with open(file_path, 'wb') as file_handle:
                yield file_handle
        except IOError as e:
            raise ProcessingError(f"Failed to create output file: {str(e)}")


class ApplicationRunner:
    """Main application runner that coordinates the entire process."""
    
    def __init__(self):
        self._processor_facade = DocumentProcessorFacade()
        self._file_manager = FileOutputManager()
    
    def execute_document_conversion(self, token: str):
        """Execute the document conversion process with error handling."""
      
        try:
            # Process the document
            pdf_content = self._processor_facade.convert_remote_document_to_pdf(
                access_token=token,
                output_format=SupportedImageFormats.JPEG
            )
            return pdf_content
           
        except ProcessingError as pe:
            print(f"Processing Error: {pe}")
        except Exception as unexpected_error:
            print(f"Unexpected Error: {unexpected_error}")


def initialize_and_run_application():
    """Entry point function to initialize and run the application."""
    app_runner = ApplicationRunner()
    
    # Configuration
    document_token = "kuheXCCgfxrtJpkQL5KteJuC"
    output_file_path = "advanced_processed_document.pdf"
    bytes_doc =  app_runner.execute_document_conversion(document_token)
    print(bytes_doc)


if __name__ == "__main__":
    initialize_and_run_application()