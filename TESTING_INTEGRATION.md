# Integration Testing for Request Queue System

This document describes how to run integration tests for the request queue system implementation (subtask-6-1, 6-2, and 6-3).

## Prerequisites

1. **Environment Setup**
   ```bash
   # Install dependencies
   pip install -r requirements.txt

   # Set required environment variables
   export HUGGING_FACE_HUB_TOKEN=your_token_here  # or HF_TOKEN
   export API_KEY=your_api_key_here  # Optional - disables auth if not set
   export GENERATION_TIMEOUT=120  # Optional - default is 120 seconds
   ```

2. **GPU Access**
   - The server requires GPU access to load the Stable Diffusion model
   - Ensure CUDA is properly configured

## Test 1: Sequential Request Processing (subtask-6-1)

### Objective
Verify that the queue system correctly handles 3 sequential image generation requests.

### Steps

1. **Start the server:**
   ```bash
   uvicorn app.main:app --host 0.0.0.0 --port 8000
   ```

2. **Wait for the model to load** (check logs for "Model loaded successfully")

3. **Run the test script:**
   ```bash
   ./test_sequential_requests.sh
   ```

   Or manually with curl:
   ```bash
   # Request 1
   curl -X POST http://localhost:8000/v1/images/generations \
     -H "Content-Type: application/json" \
     -d '{"prompt":"a simple red cube on white background","n":1,"size":"1024x1024"}'

   # Request 2
   curl -X POST http://localhost:8000/v1/images/generations \
     -H "Content-Type: application/json" \
     -d '{"prompt":"a simple red cube on white background","n":1,"size":"1024x1024"}'

   # Request 3
   curl -X POST http://localhost:8000/v1/images/generations \
     -H "Content-Type: application/json" \
     -d '{"prompt":"a simple red cube on white background","n":1,"size":"1024x1024"}'
   ```

### Expected Results

- All 3 requests should return **200 status**
- Each response should contain image data (b64_json or url)
- Server logs should show:
  - "Request queued (queue depth: X)"
  - "Processing request from queue (remaining in queue: X)"
  - "Request processed successfully"

### Success Criteria

✅ All 3 requests return 200 status
✅ All responses contain valid image data
✅ Logs show queue processing messages
✅ No errors or exceptions in logs

## Test 2: Queue Buffering (subtask-6-2)

### Objective
Verify that the queue can buffer 5 concurrent requests and process them sequentially.

### Steps

1. **Start the server with longer timeout:**
   ```bash
   export GENERATION_TIMEOUT=300
   uvicorn app.main:app --host 0.0.0.0 --port 8000
   ```

2. **Wait for the model to load** (check logs for "Model loaded successfully")

3. **Run the test script:**
   ```bash
   ./test_concurrent_5_requests.sh
   ```

   Or use the Python async version for more detailed output:
   ```bash
   python3 test_concurrent_5_requests.py
   ```

   Or manually with curl:
   ```bash
   for i in {1..5}; do
     curl -X POST http://localhost:8000/v1/images/generations \
       -H "Content-Type: application/json" \
       -d '{"prompt":"test concurrent request '$i'","n":1,"size":"1024x1024"}' &
   done
   wait
   ```

### Expected Results

- All 5 requests should return **200 status** (none rejected with 429)
- Requests are processed sequentially (one at a time)
- Server logs show queue depth increasing then decreasing
- No "queue is full" errors

### Success Criteria

✅ All 5 concurrent requests return 200 status
✅ No 429 errors
✅ Logs show sequential processing
✅ Queue depth varies from 0-5 in logs

## Test 3: Queue Full Rejection (subtask-6-3)

### Objective
Verify that the 11th concurrent request is rejected with 429 when queue is full.

### Steps

1. **Start the server:**
   ```bash
   export GENERATION_TIMEOUT=300
   uvicorn app.main:app --host 0.0.0.0 --port 8000
   ```

2. **Send 11 concurrent requests quickly:**
   ```bash
   for i in {1..11}; do
     curl -X POST http://localhost:8000/v1/images/generations \
       -H "Content-Type: application/json" \
       -d '{"prompt":"test overflow request '$i'","n":1,"size":"1024x1024"}' \
       -w "\nRequest $i - HTTP Status: %{http_code}\n" &
   done
   wait
   ```

### Expected Results

- Requests 1-10: Should be queued and eventually return **200 status**
- Request 11: Should immediately return **429 status**
- 429 response should contain error message with "queue" or "busy"
- Server logs should show "Queue full" message

### Success Criteria

✅ At least one request returns 429 status
✅ 429 error message contains relevant text about queue being full
✅ Server logs show queue full condition
✅ Most requests (up to 10) are successfully queued and processed

## Monitoring Server Logs

To verify queue processing behavior, monitor the server logs:

```bash
# Expected log patterns:
# - "Request queue initialized with maxsize=10"
# - "Queue worker started as background task"
# - "Request queued (queue depth: X)"
# - "Processing request from queue (remaining in queue: X)"
# - "Request processed successfully"
```

## Troubleshooting

### Server won't start
- Check environment variables are set
- Verify GPU is accessible
- Check model weights are downloadable from Hugging Face

### All requests timeout
- Increase GENERATION_TIMEOUT
- Check GPU memory availability
- Verify model is loaded (check /health endpoint)

### Requests fail with 503
- Wait for model to finish loading
- Check /health endpoint shows ready=true

### Can't reproduce queue full (429)
- Ensure requests are sent concurrently (use & in bash)
- Try shorter prompts for faster queueing
- Increase GENERATION_TIMEOUT to prevent timeouts during queuing
