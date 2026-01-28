"""Image generation module using Stable Diffusion 3.5.

This module handles model loading and image generation using the vLLM-Omni framework.
It provides the ImageGenerator class for managing the Stable Diffusion pipeline.
"""

import base64
import gc
import io
import logging
import os
from typing import List, Optional, Tuple

import torch
from PIL import Image

logger = logging.getLogger(__name__)


class ImageGenerator:
    """Handles Stable Diffusion model loading and image generation.

    This class manages the Stable Diffusion 3 pipeline via vLLM-Omni, providing methods
    to load the model and generate images from text prompts.

    Attributes:
        model_id: Hugging Face model identifier for the SD model.
        device: PyTorch device to run inference on (cuda/cpu).
        omni: The loaded vLLM-Omni Omni instance.
        is_loaded: Whether the model has been successfully loaded.
    """

    def __init__(self) -> None:
        """Initialize the ImageGenerator with configuration from environment."""
        self.model_id = os.getenv(
            "MODEL_ID", "stabilityai/stable-diffusion-3.5-large-turbo"
        )
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.omni: Optional[object] = None
        self.is_loaded: bool = False

        logger.info(f"ImageGenerator initialized with model_id={self.model_id}")
        logger.info(f"Using device: {self.device}")

    def load_model(self) -> None:
        """Load the Stable Diffusion model via vLLM-Omni.

        Downloads and loads the model specified by MODEL_ID environment variable.
        Uses vLLM-Omni's Omni class for optimized inference.

        Raises:
            RuntimeError: If HUGGING_FACE_HUB_TOKEN is not set or CUDA not available.
            Exception: If model loading fails for any other reason.
        """
        # Import here to avoid loading heavy dependencies until needed
        from vllm_omni.entrypoints.omni import Omni

        token = os.getenv("HUGGING_FACE_HUB_TOKEN") or os.getenv("HF_TOKEN")
        if not token:
            raise RuntimeError(
                "HUGGING_FACE_HUB_TOKEN or HF_TOKEN environment variable is required. "
                "Please set it to your Hugging Face access token."
            )

        # vLLM requires CUDA
        if self.device != "cuda":
            raise RuntimeError(
                "vLLM-Omni requires CUDA. No CUDA device available."
            )

        logger.info(f"Loading model: {self.model_id}")
        logger.info("This may take several minutes on first run...")

        try:
            # Check if Cache-DiT should be enabled via environment variable
            enable_cache_dit = os.getenv("ENABLE_CACHE_DIT", "false").lower() == "true"

            if enable_cache_dit:
                # Initialize with Cache-DiT acceleration for 1.5-2.2x speedup
                logger.info("Initializing Omni with Cache-DiT acceleration...")
                self.omni = Omni(
                    model=self.model_id,
                    cache_backend="cache_dit",
                    cache_config={
                        "max_warmup_steps": 4,  # Optimized for turbo models
                        "Fn_compute_blocks": 1,
                        "residual_diff_threshold": 0.24,
                    },
                )
                logger.info("Cache-DiT acceleration enabled")
            else:
                # Basic initialization without Cache-DiT
                logger.info("Initializing Omni...")
                self.omni = Omni(model=self.model_id)

            self.is_loaded = True
            logger.info(f"Model loaded successfully on {self.device}")

        except Exception as e:
            logger.error(f"Failed to load model: {e}")
            self.is_loaded = False
            raise

    def _parse_size(self, size: str) -> Tuple[int, int]:
        """Parse size string into width and height integers.

        Args:
            size: Size string in format "WIDTHxHEIGHT" (e.g., "1024x1024").

        Returns:
            Tuple of (width, height) as integers.
        """
        try:
            width, height = size.lower().split("x")
            return int(width), int(height)
        except (ValueError, AttributeError):
            # Default to 1024x1024 if parsing fails
            return 1024, 1024

    def generate_image(
        self,
        prompt: str,
        size: str = "1024x1024",
        n: int = 1,
        num_inference_steps: int = 4,
        guidance_scale: float = 0.0,
    ) -> List[str]:
        """Generate images from a text prompt.

        Args:
            prompt: Text description of the image to generate.
            size: Image dimensions in "WIDTHxHEIGHT" format.
            n: Number of images to generate (1-4).
            num_inference_steps: Number of denoising steps (default 4 for turbo).
            guidance_scale: Guidance scale for generation (default 0.0 for turbo).

        Returns:
            List of base64-encoded PNG image strings.

        Raises:
            RuntimeError: If model is not loaded or generation fails.
        """
        if not self.is_loaded or self.omni is None:
            raise RuntimeError(
                "Model is not loaded. Call load_model() before generating images."
            )

        width, height = self._parse_size(size)

        logger.info(
            f"Generating {n} image(s): prompt='{prompt[:50]}...', "
            f"size={width}x{height}"
        )

        try:
            images: List[str] = []

            # Use inference mode for memory optimization and faster inference
            with torch.inference_mode():
                # Use vLLM-Omni's generate() method with num_outputs_per_prompt
                outputs = self.omni.generate(
                    prompt=prompt,
                    width=width,
                    height=height,
                    num_inference_steps=num_inference_steps,
                    guidance_scale=guidance_scale,
                    num_outputs_per_prompt=n,
                )

                # Extract images from vLLM-Omni output structure
                # Output format: outputs[0].request_output[0].images -> List[PIL.Image]
                generated_images = outputs[0].request_output[0].images

                for i, image in enumerate(generated_images):
                    # Convert to base64
                    b64_image = self._image_to_base64(image)
                    images.append(b64_image)
                    logger.info(f"Generated image {i + 1}/{n}")

            # Clean up GPU memory after generation
            self._cleanup_memory()

            return images

        except torch.cuda.OutOfMemoryError as e:
            logger.error(f"CUDA out of memory during generation: {e}")
            # Use aggressive cleanup for OOM recovery - empty_cache is warranted here
            if self.device == "cuda":
                torch.cuda.empty_cache()
            self._cleanup_memory()
            raise RuntimeError(
                "GPU out of memory. Try reducing image size or number of images."
            )
        except Exception as e:
            logger.error(f"Image generation failed: {e}")
            self._cleanup_memory()
            raise RuntimeError(f"Image generation failed: {str(e)}")

    def _image_to_base64(self, image: Image.Image) -> str:
        """Convert a PIL Image to base64-encoded PNG string.

        Args:
            image: PIL Image to convert.

        Returns:
            Base64-encoded PNG image string.
        """
        buffer = io.BytesIO()
        # Use compress_level=1 for faster encoding (default is 6)
        image.save(buffer, format="PNG", compress_level=1)
        buffer.seek(0)
        return base64.b64encode(buffer.read()).decode("utf-8")

    def _cleanup_memory(self) -> None:
        """Clean up GPU memory after generation.

        Note: This only runs gc.collect() for routine cleanup.
        torch.cuda.empty_cache() is intentionally NOT called here as it can
        hurt performance when called frequently. empty_cache is only used
        in OOM recovery and model unloading scenarios.
        """
        gc.collect()

    def unload_model(self) -> None:
        """Unload the model and free memory.

        Call this when shutting down the service to properly release resources.
        """
        if self.omni is not None:
            del self.omni
            self.omni = None
            self.is_loaded = False
            # Use empty_cache when fully unloading model to reclaim GPU memory
            if self.device == "cuda":
                torch.cuda.empty_cache()
            self._cleanup_memory()
            logger.info("Model unloaded and memory cleaned up")

    def warmup(self) -> None:
        """Perform a warmup inference to initialize CUDA kernels.

        This runs a small dummy inference to warm up the model and compile
        any lazy-loaded CUDA kernels. Call this after load_model() to ensure
        the first real inference is fast.

        Raises:
            RuntimeError: If model is not loaded.
        """
        if not self.is_loaded or self.omni is None:
            raise RuntimeError(
                "Model is not loaded. Call load_model() before warmup."
            )

        logger.info("Running warmup inference...")

        try:
            # Use a small image size for faster warmup
            with torch.inference_mode():
                # Use vLLM-Omni's generate() method for warmup
                _ = self.omni.generate(
                    prompt="warmup",
                    width=512,
                    height=512,
                    num_inference_steps=1,
                    guidance_scale=0.0,
                    num_outputs_per_prompt=1,
                )
            logger.info("Warmup completed successfully")
        except Exception as e:
            logger.warning(f"Warmup inference failed: {e}")
            # Don't raise - warmup failure shouldn't prevent service from starting
