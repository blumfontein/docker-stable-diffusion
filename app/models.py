"""Pydantic models for OpenAI-compatible image generation API.

This module defines request and response models that follow the OpenAI
/v1/images/generations API specification.
"""

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class ResponseFormat(str, Enum):
    """Supported response formats for generated images."""

    B64_JSON = "b64_json"
    URL = "url"


class ImageGenerationRequest(BaseModel):
    """Request model for image generation endpoint.

    Follows OpenAI's /v1/images/generations request format.
    """

    prompt: str = Field(
        ...,
        min_length=1,
        max_length=4096,
        description="The text description of the image to generate",
    )
    n: int = Field(
        default=1,
        ge=1,
        le=1,
        description="Number of images to generate (only 1 supported)",
    )
    size: str = Field(
        default="1024x1024",
        description="Image dimensions in WIDTHxHEIGHT format",
    )
    response_format: ResponseFormat = Field(
        default=ResponseFormat.B64_JSON,
        description="Format of the generated image response",
    )

    @field_validator("size")
    @classmethod
    def validate_size(cls, v: str) -> str:
        """Validate image size format."""
        valid_sizes = {"1024x1024", "512x512", "768x768"}
        if v not in valid_sizes:
            raise ValueError(
                f"Invalid size '{v}'. Must be one of: {', '.join(sorted(valid_sizes))}"
            )
        return v

    @field_validator("prompt")
    @classmethod
    def validate_prompt(cls, v: str) -> str:
        """Validate prompt is not empty or whitespace only."""
        if not v.strip():
            raise ValueError("Prompt cannot be empty or whitespace only")
        return v.strip()

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "prompt": "A beautiful sunset over mountains",
                    "n": 1,
                    "size": "1024x1024",
                    "response_format": "b64_json",
                }
            ]
        }
    )


class ImageData(BaseModel):
    """Individual image data in the response.

    Contains either base64-encoded image data or a URL.
    Exactly one of b64_json or url must be provided.
    """

    b64_json: Optional[str] = Field(
        default=None,
        description="Base64-encoded PNG image data",
    )
    url: Optional[str] = Field(
        default=None,
        description="URL to the generated image",
    )

    @model_validator(mode="after")
    def check_one_field_required(self) -> "ImageData":
        """Validate that exactly one of b64_json or url is provided."""
        if not self.b64_json and not self.url:
            raise ValueError("Either b64_json or url must be provided")
        if self.b64_json and self.url:
            raise ValueError("Only one of b64_json or url should be provided")
        return self


class ImageGenerationResponse(BaseModel):
    """Response model for image generation endpoint.

    Follows OpenAI's /v1/images/generations response format.
    """

    created: int = Field(
        ...,
        description="Unix timestamp of when the images were created",
    )
    data: List[ImageData] = Field(
        ...,
        description="List of generated image data",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "created": 1234567890,
                    "data": [
                        {
                            "b64_json": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
                        }
                    ],
                }
            ]
        }
    )


class ErrorResponse(BaseModel):
    """Error response model for API errors.

    Follows OpenAI's error response format.
    """

    error: str = Field(
        ...,
        description="Error message describing what went wrong",
    )
    code: str = Field(
        ...,
        description="Error code for programmatic handling",
    )
    param: Optional[str] = Field(
        default=None,
        description="The parameter that caused the error, if applicable",
    )


class HealthResponse(BaseModel):
    """Response model for health check endpoint."""

    status: str = Field(
        ...,
        description="Health status of the service",
    )
    model_loaded: bool = Field(
        ...,
        description="Whether the ML model is loaded and ready",
    )
    ready: bool = Field(
        ...,
        description="Whether the service is ready to accept requests",
    )
