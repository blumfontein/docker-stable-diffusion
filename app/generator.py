"""Image generation module using Stable Diffusion 3.5.

This module handles model loading and image generation using the diffusers library.
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

    This class manages the Stable Diffusion 3 pipeline, providing methods
    to load the model and generate images from text prompts.

    Attributes:
        model_id: Hugging Face model identifier for the SD model.
        device: PyTorch device to run inference on (cuda/cpu).
        pipe: The loaded StableDiffusion3Pipeline instance.
        is_loaded: Whether the model has been successfully loaded.
    """

    def __init__(self) -> None:
        """Initialize the ImageGenerator with configuration from environment."""
        self.model_id = os.getenv(
            "MODEL_ID", "stabilityai/stable-diffusion-3.5-large-turbo"
        )
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.pipe: Optional[object] = None
        self.is_loaded: bool = False

        logger.info(f"ImageGenerator initialized with model_id={self.model_id}")
        logger.info(f"Using device: {self.device}")

    def load_model(self) -> None:
        """Load the Stable Diffusion model from Hugging Face.

        Downloads and loads the model specified by MODEL_ID environment variable.
        Uses float16 precision for GPU memory efficiency.

        Raises:
            RuntimeError: If HUGGING_FACE_HUB_TOKEN is not set.
            Exception: If model loading fails for any other reason.
        """
        # Import here to avoid loading heavy dependencies until needed
        from diffusers import StableDiffusion3Pipeline

        token = os.getenv("HUGGING_FACE_HUB_TOKEN")
        if not token:
            raise RuntimeError(
                "HUGGING_FACE_HUB_TOKEN environment variable is required. "
                "Please set it to your Hugging Face access token."
            )

        logger.info(f"Loading model: {self.model_id}")
        logger.info("This may take several minutes on first run...")

        try:
            # Determine dtype based on device
            torch_dtype = torch.float16 if self.device == "cuda" else torch.float32

            self.pipe = StableDiffusion3Pipeline.from_pretrained(
                self.model_id,
                torch_dtype=torch_dtype,
                token=token,
            )
            self.pipe.to(self.device)

            # Enable memory optimizations for CUDA
            if self.device == "cuda":
                try:
                    self.pipe.enable_model_cpu_offload()
                    logger.info("Enabled model CPU offload for memory optimization")
                except Exception as e:
                    logger.warning(f"Could not enable CPU offload: {e}")

                # Enable VAE slicing for memory-efficient batch processing
                try:
                    self.pipe.enable_vae_slicing()
                    logger.info("Enabled VAE slicing for memory-efficient batch processing")
                except Exception as e:
                    logger.warning(f"Could not enable VAE slicing: {e}")

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
        if not self.is_loaded or self.pipe is None:
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
                for i in range(n):
                    # Generate the image
                    result = self.pipe(
                        prompt=prompt,
                        width=width,
                        height=height,
                        num_inference_steps=num_inference_steps,
                        guidance_scale=guidance_scale,
                    )

                    # Get the PIL image from the result
                    image = result.images[0]

                    # Convert to base64
                    b64_image = self._image_to_base64(image)
                    images.append(b64_image)

                    logger.info(f"Generated image {i + 1}/{n}")

            # Clean up GPU memory after generation
            self._cleanup_memory()

            return images

        except torch.cuda.OutOfMemoryError as e:
            logger.error(f"CUDA out of memory during generation: {e}")
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
        """Clean up GPU memory after generation."""
        if self.device == "cuda":
            torch.cuda.empty_cache()
        gc.collect()

    def unload_model(self) -> None:
        """Unload the model and free memory.

        Call this when shutting down the service to properly release resources.
        """
        if self.pipe is not None:
            del self.pipe
            self.pipe = None
            self.is_loaded = False
            self._cleanup_memory()
            logger.info("Model unloaded and memory cleaned up")
