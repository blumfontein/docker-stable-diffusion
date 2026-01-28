"""FastAPI application for Stable Diffusion 3.5 image generation.

This module provides an OpenAI-compatible REST API for text-to-image generation
using the Stable Diffusion 3.5 model.
"""

from __future__ import annotations

import asyncio
import logging
import os
import secrets
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from functools import partial
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

# Thread pool executor for running blocking generation in background
executor: ThreadPoolExecutor | None = None

# Async lock for backpressure - prevents concurrent generation requests
generation_lock: asyncio.Lock | None = None

# Generation timeout in seconds
GENERATION_TIMEOUT = 120

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


async def verify_api_key(authorization: Optional[str] = Header(None)) -> None:
    """Verify the Bearer token from the Authorization header.

    This dependency validates the Bearer token sent in the Authorization header
    against the API_KEY environment variable. If API_KEY is not configured, all
    requests are allowed (development mode).

    Args:
        authorization: The Authorization header value (expected format: "Bearer <token>").

    Raises:
        HTTPException: 401 if Authorization header is missing, malformed, or token is invalid.
    """
    # If API_KEY is not configured, allow all requests (dev mode)
    if not API_KEY:
        return

    # Check for missing Authorization header
    if not authorization or not authorization.strip():
        logger.warning("Request rejected: missing Authorization header")
        raise HTTPException(
            status_code=401,
            detail={
                "error": "Authorization header is required. "
                "Please provide 'Authorization: Bearer <token>' header.",
                "code": "missing_api_key",
                "param": None,
            },
        )

    # Parse Bearer token from Authorization header
    auth_value = authorization.strip()
    if not auth_value.startswith("Bearer "):
        logger.warning("Request rejected: invalid Authorization header format")
        raise HTTPException(
            status_code=401,
            detail={
                "error": "Invalid Authorization header format. "
                "Expected 'Bearer <token>'.",
                "code": "invalid_auth_format",
                "param": None,
            },
        )

    token = auth_value[len("Bearer "):]
    if not token or not token.strip():
        logger.warning("Request rejected: empty Bearer token")
        raise HTTPException(
            status_code=401,
            detail={
                "error": "Bearer token is empty. "
                "Please provide a valid token.",
                "code": "missing_api_key",
                "param": None,
            },
        )

    # Use constant-time comparison to prevent timing attacks
    if not secrets.compare_digest(token.strip(), API_KEY):
        logger.warning("Request rejected: invalid Bearer token")
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
    Also initializes and cleans up the thread pool executor.
    """
    global generator, executor, generation_lock

    logger.info("Starting up Stable Diffusion API server...")

    # Initialize async lock for backpressure control
    generation_lock = asyncio.Lock()
    logger.info("Generation lock initialized")

    # Initialize thread pool executor for async generation
    # Use max_workers=1 to prevent concurrent GPU access issues
    executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="sd_generator")
    logger.info("Thread pool executor initialized")

    # Initialize and load the model
    generator = ImageGenerator()
    try:
        generator.load_model()
        logger.info("Model loaded successfully")
        # Warmup the model to prepare for inference
        generator.warmup()
        logger.info("Model warmed up, API ready to serve requests")
    except Exception as e:
        logger.error(f"Failed to load model during startup: {e}")
        # Continue running but model will not be available
        # Health check will report model_loaded=False

    yield

    # Cleanup on shutdown
    logger.info("Shutting down API server...")
    if generator is not None:
        generator.unload_model()
    if executor is not None:
        executor.shutdown(wait=True)
        logger.info("Thread pool executor shutdown complete")
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
        401: {"model": ErrorResponse, "description": "Unauthorized"},
        429: {"model": ErrorResponse, "description": "Server busy (backpressure)"},
        500: {"model": ErrorResponse, "description": "Server error"},
        503: {"model": ErrorResponse, "description": "Service unavailable"},
    },
    summary="Generate Images",
    description="Generate images from a text prompt using Stable Diffusion 3.5",
)
async def generate_images(
    request: ImageGenerationRequest,
    _: None = Depends(verify_api_key),
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

    # Check if executor is available
    if executor is None:
        raise HTTPException(
            status_code=503,
            detail={
                "error": "Service is not ready. Please wait for startup to complete.",
                "code": "service_not_ready",
                "param": None,
            },
        )

    # Check if generation lock is available
    if generation_lock is None:
        raise HTTPException(
            status_code=503,
            detail={
                "error": "Service is not ready. Please wait for startup to complete.",
                "code": "service_not_ready",
                "param": None,
            },
        )

    # Backpressure: return 429 if another request is already being processed
    if generation_lock.locked():
        raise HTTPException(
            status_code=429,
            detail={
                "error": "Server is busy processing another request. Please try again later.",
                "code": "rate_limit_exceeded",
                "param": None,
            },
        )

    try:
        async with generation_lock:
            # Run blocking generation in thread pool executor to avoid blocking event loop
            loop = asyncio.get_running_loop()
            generate_fn = partial(
                generator.generate_image,
                prompt=request.prompt,
                size=request.size,
                n=request.n,
            )
            # Wrap in wait_for with timeout to prevent hanging requests
            images_b64 = await asyncio.wait_for(
                loop.run_in_executor(executor, generate_fn),
                timeout=GENERATION_TIMEOUT,
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

    except asyncio.TimeoutError:
        logger.error(f"Generation timed out after {GENERATION_TIMEOUT} seconds")
        raise HTTPException(
            status_code=500,
            detail={
                "error": f"Image generation timed out after {GENERATION_TIMEOUT} seconds.",
                "code": "timeout",
                "param": None,
            },
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
