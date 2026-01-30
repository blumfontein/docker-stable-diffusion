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
from dataclasses import dataclass
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


@dataclass
class QueuedRequest:
    """Request queued for GPU processing.

    Holds the image generation request and a future that will be
    resolved when processing completes.
    """

    request: ImageGenerationRequest
    future: asyncio.Future


# Global generator instance
generator: ImageGenerator | None = None

# Thread pool executor for running blocking generation in background
executor: ThreadPoolExecutor | None = None

# Request queue for GPU image generation
request_queue: asyncio.Queue[QueuedRequest] | None = None

# Background task for queue worker
queue_worker_task: asyncio.Task | None = None

# Generation timeout in seconds (configurable via environment variable)
GENERATION_TIMEOUT = int(os.getenv("GENERATION_TIMEOUT", "120"))
logger.info(f"GENERATION_TIMEOUT configured to {GENERATION_TIMEOUT} seconds")

# Max workers for thread pool executor (configurable via environment variable)
MAX_WORKERS = int(os.getenv("MAX_WORKERS", "1"))
logger.info(f"MAX_WORKERS configured to {MAX_WORKERS}")

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


async def queue_worker() -> None:
    """Background worker to process queued image generation requests.

    This coroutine runs continuously, pulling requests from the request_queue
    and processing them sequentially. It uses the thread pool executor to run
    the blocking generation calls without blocking the event loop.

    The worker processes requests one at a time to ensure sequential GPU access,
    preventing concurrent generation issues. Results or exceptions are set on
    the Future object associated with each request.

    This function is designed to run as a background task started during application
    startup via asyncio.create_task().
    """
    logger.info("Queue worker started")

    while True:
        queued_request: Optional[QueuedRequest] = None
        try:
            # Block until a request is available in the queue
            queued_request = await request_queue.get()
            queue_depth = request_queue.qsize()
            logger.info(
                f"Processing request from queue (remaining in queue: {queue_depth})"
            )

            # Extract request data
            request = queued_request.request
            future = queued_request.future

            # Check if generator is available
            if generator is None or not generator.is_loaded:
                error_msg = "Model is not loaded"
                logger.error(f"Queue worker error: {error_msg}")
                future.set_exception(
                    RuntimeError(error_msg)
                )
                continue

            # Check if executor is available
            if executor is None:
                error_msg = "Executor is not available"
                logger.error(f"Queue worker error: {error_msg}")
                future.set_exception(
                    RuntimeError(error_msg)
                )
                continue

            try:
                # Run blocking generation in thread pool executor
                loop = asyncio.get_running_loop()
                generate_fn = partial(
                    generator.generate_image,
                    prompt=request.prompt,
                    size=request.size,
                    n=request.n,
                )

                # Execute generation with timeout
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

                # Create successful response
                response = ImageGenerationResponse(
                    created=int(time.time()),
                    data=image_data_list,
                )

                # Set result on future
                future.set_result(response)
                logger.info("Request processed successfully")

            except asyncio.TimeoutError:
                error_msg = f"Generation timed out after {GENERATION_TIMEOUT} seconds"
                logger.error(f"Queue worker: {error_msg}")
                future.set_exception(
                    asyncio.TimeoutError(error_msg)
                )

            except RuntimeError as e:
                logger.error(f"Queue worker runtime error: {e}")
                future.set_exception(e)

            except Exception as e:
                logger.error(f"Queue worker unexpected error: {e}")
                future.set_exception(e)

        except Exception as e:
            # Catch any unexpected errors in the worker loop itself
            logger.error(f"Queue worker loop error: {e}")
            # If we have a queued_request, set exception on its future
            if queued_request is not None and queued_request.future is not None:
                try:
                    queued_request.future.set_exception(e)
                except Exception as future_error:
                    logger.error(f"Failed to set exception on future: {future_error}")

        finally:
            # Always mark task as done
            if queued_request is not None:
                request_queue.task_done()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Lifespan context manager for model loading and cleanup.

    Loads the Stable Diffusion model at startup and unloads it at shutdown.
    Also initializes and cleans up the thread pool executor and queue worker.
    """
    global generator, executor, request_queue, queue_worker_task

    logger.info("Starting up Stable Diffusion API server...")

    # Initialize request queue for GPU processing
    request_queue = asyncio.Queue(maxsize=10)
    logger.info("Request queue initialized with maxsize=10")

    # Initialize thread pool executor for async generation
    # Default max_workers=1 to prevent concurrent GPU access issues
    executor = ThreadPoolExecutor(max_workers=MAX_WORKERS, thread_name_prefix="sd_generator")
    logger.info(f"Thread pool executor initialized with {MAX_WORKERS} workers")

    # Start queue worker as background task
    queue_worker_task = asyncio.create_task(queue_worker())
    logger.info("Queue worker started as background task")

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

    # Cancel and cleanup queue worker task
    if queue_worker_task is not None:
        queue_worker_task.cancel()
        try:
            await queue_worker_task
        except asyncio.CancelledError:
            logger.info("Queue worker task cancelled successfully")

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
    Verifies that the request queue and queue worker are properly initialized.
    """
    model_loaded = generator is not None and generator.is_loaded
    queue_ready = (
        request_queue is not None
        and queue_worker_task is not None
        and not queue_worker_task.done()
    )
    ready = model_loaded and executor is not None and queue_ready
    return HealthResponse(
        status="healthy" if model_loaded else "degraded",
        model_loaded=model_loaded,
        ready=ready,
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

    # Validate requested model matches loaded model
    if request.model != generator.model_id:
        logger.warning(
            f"Model mismatch: requested '{request.model}', loaded '{generator.model_id}'"
        )
        raise HTTPException(
            status_code=400,
            detail={
                "error": f"Requested model '{request.model}' does not match "
                f"loaded model '{generator.model_id}'.",
                "code": "model_mismatch",
                "param": "model",
            },
        )

    # Check if request queue is available
    if request_queue is None:
        raise HTTPException(
            status_code=503,
            detail={
                "error": "Service is not ready. Please wait for startup to complete.",
                "code": "service_not_ready",
                "param": None,
            },
        )

    # Create a future to receive the result from the queue worker
    loop = asyncio.get_running_loop()
    result_future = loop.create_future()

    # Create queued request
    queued_request = QueuedRequest(
        request=request,
        future=result_future,
    )

    # Try to add request to queue (non-blocking)
    # Backpressure: return 429 if queue is full
    try:
        request_queue.put_nowait(queued_request)
        logger.info(f"Request queued (queue depth: {request_queue.qsize()})")
    except asyncio.QueueFull:
        raise HTTPException(
            status_code=429,
            detail={
                "error": "Request queue is full. Please try again later.",
                "code": "rate_limit_exceeded",
                "param": None,
            },
        )

    # Wait for the queue worker to process the request and set the result
    try:
        response = await result_future
        return response

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
