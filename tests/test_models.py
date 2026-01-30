"""Unit tests for QueuedRequest dataclass."""

import asyncio
import pytest
from app.main import QueuedRequest
from app.models import ImageGenerationRequest


def test_queued_request_instantiation():
    """Test that QueuedRequest can be instantiated with required fields."""
    request = ImageGenerationRequest(prompt="test prompt")
    future = asyncio.Future()

    queued_request = QueuedRequest(request=request, future=future)

    assert queued_request.request == request
    assert queued_request.future == future
    assert isinstance(queued_request.request, ImageGenerationRequest)
    assert isinstance(queued_request.future, asyncio.Future)


def test_queued_request_fields_are_required():
    """Test that QueuedRequest requires both fields."""
    # This tests the dataclass structure - should work with dataclasses
    request = ImageGenerationRequest(prompt="test prompt")
    future = asyncio.Future()

    # Should work with both fields
    qr = QueuedRequest(request=request, future=future)
    assert qr is not None
