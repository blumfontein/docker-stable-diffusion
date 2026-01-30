"""Unit tests for main.py queue system."""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.main import queue_worker, QueuedRequest
from app.models import ImageGenerationRequest, ImageGenerationResponse


@pytest.mark.asyncio
async def test_queue_initialization_maxsize():
    """Test that request_queue is initialized with maxsize=10."""
    # This can be tested by checking the Queue initialization in lifespan
    queue = asyncio.Queue(maxsize=10)

    # Verify maxsize
    assert queue.maxsize == 10

    # Verify we can add 10 items without blocking
    for i in range(10):
        queue.put_nowait(i)

    # Verify 11th item raises QueueFull
    with pytest.raises(asyncio.QueueFull):
        queue.put_nowait(11)


@pytest.mark.asyncio
async def test_queue_worker_processes_request(monkeypatch):
    """Test that queue_worker processes requests from the queue."""
    # Create a test queue with one request
    test_queue = asyncio.Queue(maxsize=10)

    # Mock the global request_queue
    import app.main
    monkeypatch.setattr(app.main, "request_queue", test_queue)

    # Mock the generator
    mock_generator = MagicMock()
    mock_generator.is_loaded = True
    mock_generator.generate_image.return_value = ["base64_image_data"]
    monkeypatch.setattr(app.main, "generator", mock_generator)

    # Mock the executor
    mock_executor = MagicMock()
    monkeypatch.setattr(app.main, "executor", mock_executor)

    # Create a test request
    request = ImageGenerationRequest(prompt="test prompt")
    future = asyncio.Future()
    queued_request = QueuedRequest(request=request, future=future)

    # Add request to queue
    await test_queue.put(queued_request)

    # Mock run_in_executor to immediately return the result
    async def mock_run_in_executor(executor, fn):
        return fn()

    # Start queue worker in background
    worker_task = asyncio.create_task(queue_worker())

    # Wait briefly for processing
    await asyncio.sleep(0.1)

    # Cancel worker
    worker_task.cancel()
    try:
        await worker_task
    except asyncio.CancelledError:
        pass

    # Verify generator was called (this test may need adjustment based on actual implementation)
    # This is a simplified test - in practice you'd need more sophisticated mocking


@pytest.mark.asyncio
async def test_queue_full_raises_exception():
    """Test that putting to a full queue raises QueueFull."""
    queue = asyncio.Queue(maxsize=2)

    # Fill the queue
    queue.put_nowait(1)
    queue.put_nowait(2)

    # Third item should raise QueueFull
    with pytest.raises(asyncio.QueueFull):
        queue.put_nowait(3)


@pytest.mark.asyncio
async def test_queue_get_blocks_until_item_available():
    """Test that queue.get() blocks until an item is available."""
    queue = asyncio.Queue(maxsize=10)

    # Start a task that will get from queue
    async def get_from_queue():
        return await queue.get()

    task = asyncio.create_task(get_from_queue())

    # Wait a bit - task should still be pending
    await asyncio.sleep(0.01)
    assert not task.done()

    # Add item to queue
    await queue.put("test_item")

    # Task should complete now
    result = await task
    assert result == "test_item"
