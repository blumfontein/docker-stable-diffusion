"""FastAPI application for Stable Diffusion 3.5 image generation.

This module provides an OpenAI-compatible REST API for text-to-image generation
using the Stable Diffusion 3.5 model.
"""

from __future__ import annotations

import logging
import os
import secrets
import time
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import JSONResponse

from app.generator import ImageGenerator
from app.models import (
    ErrorResponse,
    HealthResponse,
    ImageData,
    ImageGenerationRequest,
    ImageGenerationResponse,
    ResponseFormat,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Global generator instance
generator: ImageGenerator | None = None

# API Key configuration
API_KEY: Optional[str] = os.getenv("API_KEY")
if API_KEY:
    # Strip whitespace from API key
    API_KEY = API_KEY.strip() if API_KEY.strip() else None

if not API_KEY:
    logger.warning(
        "API_KEY environment variable is not set. "
        "API authentication is DISABLED. "
        "Set API_KEY to enable authentication."
    )


async def verify_api_key(x_api_key: Optional[str] = Header(None)) -> None:
    """Verify the API key from the X-API-Key header.

    This dependency validates the API key sent in the request header against
    the API_KEY environment variable. If API_KEY is not configured, all
    requests are allowed (development mode).

    Args:
        x_api_key: The API key from the X-API-Key header.

    Raises:
        HTTPException: 401 if API key is missing or invalid.
    """
    # If API_KEY is not configured, allow all requests (dev mode)
    if not API_KEY:
        return

    # Check for missing API key
    if not x_api_key or not x_api_key.strip():
        logger.warning("Request rejected: missing API key")
        raise HTTPException(
            status_code=401,
            detail={
                "error": "API key is required. Please provide X-API-Key header.",
                "code": "missing_api_key",
                "param": None,
            },
        )

    # Use constant-time comparison to prevent timing attacks
    if not secrets.compare_digest(x_api_key, API_KEY):
        logger.warning("Request rejected: invalid API key")
        raise HTTPException(
            status_code=401,
            detail={
                "error": "Invalid API key provided.",
                "code": "invalid_api_key",
                "param": None,
            },
        )


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Lifespan context manager for model loading and cleanup.

    Loads the Stable Diffusion model at startup and unloads it at shutdown.
    """
    global generator

    logger.info("Starting up Stable Diffusion API server...")

    # Initialize and load the model
    generator = ImageGenerator()
    try:
        generator.load_model()
        logger.info("Model loaded successfully, API ready to serve requests")
    except Exception as e:
        logger.error(f"Failed to load model during startup: {e}")
        # Continue running but model will not be available
        # Health check will report model_loaded=False

    yield

    # Cleanup on shutdown
    logger.info("Shutting down API server...")
    if generator is not None:
        generator.unload_model()
    logger.info("Cleanup complete")


# Create FastAPI application
app = FastAPI(
    title="Stable Diffusion 3.5 API",
    description="OpenAI-compatible REST API for text-to-image generation using Stable Diffusion 3.5",
    version="1.0.0",
    lifespan=lifespan,
)


@app.get(
    "/health",
    response_model=HealthResponse,
    summary="Health Check",
    description="Check the health status of the API and model loading state",
)
async def health_check() -> HealthResponse:
    """Health check endpoint.

    Returns the service health status and whether the model is loaded.
    """
    model_loaded = generator is not None and generator.is_loaded
    return HealthResponse(
        status="healthy" if model_loaded else "degraded",
        model_loaded=model_loaded,
    )


@app.post(
    "/v1/images/generations",
    response_model=ImageGenerationResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Validation error"},
        500: {"model": ErrorResponse, "description": "Server error"},
        503: {"model": ErrorResponse, "description": "Service unavailable"},
    },
    summary="Generate Images",
    description="Generate images from a text prompt using Stable Diffusion 3.5",
)
async def generate_images(
    request: ImageGenerationRequest,
) -> ImageGenerationResponse:
    """Generate images from a text prompt.

    This endpoint follows the OpenAI /v1/images/generations API specification.

    Args:
        request: Image generation request with prompt and parameters.

    Returns:
        ImageGenerationResponse with generated image data.

    Raises:
        HTTPException: If model is not loaded or generation fails.
    """
    # Check if model is loaded
    if generator is None or not generator.is_loaded:
        raise HTTPException(
            status_code=503,
            detail={
                "error": "Model is not loaded. Please wait for startup to complete.",
                "code": "model_not_loaded",
                "param": None,
            },
        )

    try:
        # Generate images
        images_b64 = generator.generate_image(
            prompt=request.prompt,
            size=request.size,
            n=request.n,
        )

        # Build response based on requested format
        image_data_list = []
        for b64_image in images_b64:
            if request.response_format == ResponseFormat.B64_JSON:
                image_data_list.append(ImageData(b64_json=b64_image))
            else:
                # URL format not supported for local generation
                # Return b64_json anyway as fallback
                image_data_list.append(ImageData(b64_json=b64_image))

        return ImageGenerationResponse(
            created=int(time.time()),
            data=image_data_list,
        )

    except RuntimeError as e:
        error_msg = str(e)
        if "out of memory" in error_msg.lower():
            raise HTTPException(
                status_code=500,
                detail={
                    "error": error_msg,
                    "code": "gpu_out_of_memory",
                    "param": None,
                },
            )
        raise HTTPException(
            status_code=500,
            detail={
                "error": error_msg,
                "code": "generation_failed",
                "param": None,
            },
        )
    except Exception as e:
        logger.error(f"Unexpected error during image generation: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": f"Image generation failed: {str(e)}",
                "code": "internal_error",
                "param": None,
            },
        )


@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc: HTTPException) -> JSONResponse:
    """Custom exception handler for consistent error responses."""
    if isinstance(exc.detail, dict):
        return JSONResponse(
            status_code=exc.status_code,
            content=exc.detail,
        )
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": str(exc.detail),
            "code": "http_error",
            "param": None,
        },
    )


if __name__ == "__main__":
    import os

    import uvicorn

    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))

    uvicorn.run(
        "app.main:app",
        host=host,
        port=port,
        reload=False,
    )
