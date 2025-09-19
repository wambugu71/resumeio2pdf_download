"""
Production configuration for the Resume PDF Generator API
"""

import os
from pydantic import BaseModel
from typing import Optional
class APIConfig(BaseModel):
    """Configuration settings for the API server."""
    
    # Server settings
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = False
    
    # API settings
    title: str = "Resume PDF Generator API"
    description: str = "API for generating PDF documents from resume tokens"
    version: str = "1.0.0"
    
    # PDF generation settings
    default_resolution: int = 3000
    max_resolution: int = 10000
    min_resolution: int = 100
    request_timeout: int = 60
    
    # CORS settings
    allow_origins: list = ["*"]
    allow_credentials: bool = True
    allow_methods: list = ["*"]
    allow_headers: list = ["*"]
    
    # Rate limiting (for future implementation)
    rate_limit_enabled: bool = False
    max_requests_per_minute: int = 10
    
    @classmethod
    def from_env(cls) -> "APIConfig":
        """Create configuration from environment variables."""
        return cls(
            host=os.getenv("API_HOST", "0.0.0.0"),
            port=int(os.getenv("API_PORT", "8000")),
            debug=os.getenv("API_DEBUG", "false").lower() == "true",
            request_timeout=int(os.getenv("API_TIMEOUT", "60")),
            default_resolution=int(os.getenv("PDF_DEFAULT_RESOLUTION", "3000")),
            max_resolution=int(os.getenv("PDF_MAX_RESOLUTION", "10000")),
            min_resolution=int(os.getenv("PDF_MIN_RESOLUTION", "100")),
        )

# Default configuration instance
config = APIConfig.from_env()
