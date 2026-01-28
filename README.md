# Stable Diffusion 3.5 Large Turbo API

A Docker-containerized REST API for text-to-image generation using Stable Diffusion 3.5 Large Turbo. Provides an OpenAI-compatible `/v1/images/generations` endpoint for seamless integration with existing tools and workflows.

## Features

- **OpenAI-Compatible API**: Drop-in replacement for OpenAI's image generation API
- **GPU Accelerated**: Optimized for NVIDIA GPUs with CUDA 12.1
- **Configurable**: Model ID and server settings via environment variables
- **Docker Ready**: Production-ready containerization with health checks
- **Model Caching**: Volume mount support for persistent model storage

## Prerequisites

Before running this API, ensure you have:

1. **Docker** with NVIDIA Container Toolkit installed
   ```bash
   # Verify Docker installation
   docker --version

   # Verify NVIDIA Container Toolkit
   nvidia-smi
   docker run --rm --gpus all nvidia/cuda:12.1-base-ubuntu22.04 nvidia-smi
   ```

2. **NVIDIA GPU** with CUDA support (recommended: 16GB+ VRAM for SD 3.5 Large Turbo)

3. **Hugging Face Account** with access to the [Stable Diffusion 3.5 Large Turbo](https://huggingface.co/stabilityai/stable-diffusion-3.5-large-turbo) model
   - Create an account at https://huggingface.co
   - Accept the model license agreement
   - Generate an access token at https://huggingface.co/settings/tokens

## Quick Start

```bash
# 1. Build the Docker image
docker build -t sd-api .

# 2. Run with your Hugging Face token and API key
docker run --gpus all -p 8000:8000 \
  -e HUGGING_FACE_HUB_TOKEN=hf_your_token_here \
  -e API_KEY=your_api_key_here \
  -v ~/.cache/huggingface:/root/.cache/huggingface \
  sd-api

# 3. Test the API
curl -X POST http://localhost:8000/v1/images/generations \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"prompt": "A beautiful sunset over mountains", "n": 1, "size": "1024x1024"}'
```

## Build Instructions

### Standard Build

```bash
docker build -t sd-api:latest .
```

### Build with Custom Tag

```bash
docker build -t sd-api:v1.0.0 .
```

### Build with Build Arguments (if needed)

```bash
docker build --build-arg BUILDKIT_INLINE_CACHE=1 -t sd-api:latest .
```

## Run Instructions

### Basic Run (GPU Required)

```bash
docker run --gpus all -p 8000:8000 \
  -e HUGGING_FACE_HUB_TOKEN=your_token_here \
  -e API_KEY=your_api_key_here \
  sd-api
```

### Run with Model Caching (Recommended)

Cache downloaded models to avoid re-downloading on container restart:

```bash
docker run --gpus all -p 8000:8000 \
  -e HUGGING_FACE_HUB_TOKEN=your_token_here \
  -e API_KEY=your_api_key_here \
  -v ~/.cache/huggingface:/root/.cache/huggingface \
  sd-api
```

### Run with Custom Model

```bash
docker run --gpus all -p 8000:8000 \
  -e HUGGING_FACE_HUB_TOKEN=your_token_here \
  -e API_KEY=your_api_key_here \
  -e MODEL_ID=stabilityai/stable-diffusion-3.5-large \
  -v ~/.cache/huggingface:/root/.cache/huggingface \
  sd-api
```

### Run in Detached Mode

```bash
docker run -d --name sd-api --gpus all -p 8000:8000 \
  -e HUGGING_FACE_HUB_TOKEN=your_token_here \
  -e API_KEY=your_api_key_here \
  -v ~/.cache/huggingface:/root/.cache/huggingface \
  sd-api

# View logs
docker logs -f sd-api

# Stop container
docker stop sd-api
```

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `HUGGING_FACE_HUB_TOKEN` | **Yes** | - | Your Hugging Face access token for model download |
| `HF_TOKEN` | No | - | Alternative to `HUGGING_FACE_HUB_TOKEN` for Hugging Face authentication |
| `API_KEY` | No | - | API key for Bearer token authentication. If not set, authentication is disabled |
| `MODEL_ID` | No | `stabilityai/stable-diffusion-3.5-large-turbo` | Hugging Face model identifier |
| `HOST` | No | `0.0.0.0` | Server bind address |
| `PORT` | No | `8000` | Server port |
| `ENABLE_CACHE_DIT` | No | `false` | Enable DIT caching optimization for improved performance |

## Authentication

The API supports Bearer token authentication via the `Authorization` header. Authentication is enabled by setting the `API_KEY` environment variable.

### How It Works

- **When `API_KEY` is set:** All requests to the `/v1/images/generations` endpoint must include a valid `Authorization: Bearer <token>` header.
- **When `API_KEY` is not set:** Authentication is disabled and all requests are allowed (development mode).

### Example: Authenticated Request

```bash
curl -X POST http://localhost:8000/v1/images/generations \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"prompt": "A beautiful sunset over mountains"}'
```

### Authentication Errors

| HTTP Status | Scenario | Message |
|-------------|----------|---------|
| 401 | Missing header | `Authorization header is required` |
| 401 | Invalid format | `Invalid Authorization header format. Expected 'Bearer <token>'` |
| 401 | Wrong token | `Invalid API key` |

> **Note:** The `/health` and `/docs` endpoints do not require authentication.

## API Endpoints

### Health Check

**GET** `/health`

Check the health status of the API and model loading state.

```bash
curl http://localhost:8000/health
```

**Response:**
```json
{
  "status": "healthy",
  "model_loaded": true
}
```

| Status | Description |
|--------|-------------|
| `healthy` | Model is loaded and ready to serve requests |
| `degraded` | Service is running but model is not loaded |

### Generate Images

**POST** `/v1/images/generations`

Generate images from a text prompt using Stable Diffusion 3.5.

**Request Body:**

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `prompt` | string | Yes | - | Text description of the image (1-4096 characters) |
| `n` | integer | No | 1 | Number of images to generate (1-4) |
| `size` | string | No | `1024x1024` | Image dimensions (`512x512`, `768x768`, `1024x1024`) |
| `response_format` | string | No | `b64_json` | Response format (`b64_json` or `url`) |

**Example Request:**

```bash
curl -X POST http://localhost:8000/v1/images/generations \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "A beautiful sunset over mountains, digital art, high quality",
    "n": 1,
    "size": "1024x1024",
    "response_format": "b64_json"
  }'
```

**Example Response:**

```json
{
  "created": 1706450400,
  "data": [
    {
      "b64_json": "iVBORw0KGgoAAAANSUhEUgAABAAAAAQA..."
    }
  ]
}
```

**Save Generated Image:**

```bash
# Generate and save to file
curl -s -X POST http://localhost:8000/v1/images/generations \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"prompt": "A majestic mountain landscape"}' \
  | jq -r '.data[0].b64_json' | base64 -d > output.png
```

### API Documentation

**GET** `/docs`

Interactive Swagger UI documentation.

```
http://localhost:8000/docs
```

**GET** `/redoc`

ReDoc API documentation.

```
http://localhost:8000/redoc
```

## Error Handling

The API returns OpenAI-compatible error responses:

```json
{
  "error": "Error message describing what went wrong",
  "code": "error_code",
  "param": null
}
```

### Error Codes

| HTTP Status | Code | Description |
|-------------|------|-------------|
| 401 | `authentication_error` | Missing, invalid, or incorrect Bearer token |
| 400 | `validation_error` | Invalid request parameters |
| 500 | `gpu_out_of_memory` | GPU ran out of memory during generation |
| 500 | `generation_failed` | Image generation failed |
| 500 | `internal_error` | Unexpected server error |
| 503 | `model_not_loaded` | Model is not yet loaded (wait for startup) |

## Docker Compose Example

Create a `docker-compose.yml`:

```yaml
version: '3.8'

services:
  sd-api:
    build: .
    ports:
      - "8000:8000"
    environment:
      - HUGGING_FACE_HUB_TOKEN=${HUGGING_FACE_HUB_TOKEN}
      - API_KEY=${API_KEY}
      - MODEL_ID=stabilityai/stable-diffusion-3.5-large-turbo
    volumes:
      - huggingface-cache:/root/.cache/huggingface
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 300s

volumes:
  huggingface-cache:
```

Run with:

```bash
export HUGGING_FACE_HUB_TOKEN=your_token_here
export API_KEY=your_api_key_here
docker-compose up -d
```

## Python Client Example

```python
import base64
import requests

# Generate an image
response = requests.post(
    "http://localhost:8000/v1/images/generations",
    headers={"Authorization": "Bearer YOUR_API_KEY"},
    json={
        "prompt": "A cyberpunk city at night, neon lights, rain",
        "n": 1,
        "size": "1024x1024"
    }
)

# Save the image
data = response.json()
image_b64 = data["data"][0]["b64_json"]
image_bytes = base64.b64decode(image_b64)

with open("generated_image.png", "wb") as f:
    f.write(image_bytes)

print("Image saved to generated_image.png")
```

## OpenAI SDK Compatibility

This API is compatible with the OpenAI Python SDK:

```python
from openai import OpenAI

# Point to local SD API
client = OpenAI(
    base_url="http://localhost:8000/v1",
    api_key="your-api-key"  # Must match the API_KEY environment variable
)

response = client.images.generate(
    prompt="A serene Japanese garden with cherry blossoms",
    n=1,
    size="1024x1024"
)

# Access the base64 image data
image_b64 = response.data[0].b64_json
```

## Troubleshooting

### Model Download Fails

**Symptom:** Container fails to start with authentication errors.

**Solution:** Verify your `HUGGING_FACE_HUB_TOKEN` is correct and has access to the model:

```bash
# Test token access
curl -H "Authorization: Bearer YOUR_TOKEN" \
  https://huggingface.co/api/models/stabilityai/stable-diffusion-3.5-large-turbo
```

### Out of Memory (OOM) Errors

**Symptom:** Generation fails with CUDA out of memory errors.

**Solutions:**
- Reduce image size to `512x512` or `768x768`
- Generate fewer images at once (`n=1`)
- Use a GPU with more VRAM (16GB+ recommended)
- Close other GPU-intensive applications

### Container Starts but API Returns 503

**Symptom:** Health check shows `model_loaded: false`.

**Solution:** Wait for model download and loading to complete. First startup can take 5-10 minutes depending on internet speed. Monitor with:

```bash
docker logs -f sd-api
```

### GPU Not Detected

**Symptom:** Container fails to use GPU or falls back to CPU.

**Solutions:**
1. Verify NVIDIA Container Toolkit installation:
   ```bash
   docker run --rm --gpus all nvidia/cuda:12.1-base-ubuntu22.04 nvidia-smi
   ```

2. Ensure Docker daemon has GPU support:
   ```bash
   sudo systemctl restart docker
   ```

3. Check NVIDIA drivers:
   ```bash
   nvidia-smi
   ```

## Project Structure

```
.
├── Dockerfile              # Docker image definition
├── requirements.txt        # Python dependencies
├── README.md               # This documentation
└── app/
    ├── __init__.py         # Package initialization
    ├── main.py             # FastAPI application and endpoints
    ├── models.py           # Pydantic request/response models
    └── generator.py        # Model loading and image generation
```

## Performance Notes

- **First Request:** Initial request may be slow as the model loads into GPU memory
- **Subsequent Requests:** ~5-15 seconds per image depending on GPU and settings
- **Memory Usage:** SD 3.5 Large Turbo requires ~12-16GB VRAM at float16 precision
- **Concurrent Requests:** Requests are processed sequentially to prevent GPU memory issues

## License

This project provides an inference API for the Stable Diffusion 3.5 Large Turbo model. Usage of the model is subject to the [Stability AI License](https://huggingface.co/stabilityai/stable-diffusion-3.5-large-turbo).

## Contributing

Contributions are welcome! Please ensure any changes:
- Follow the existing code style
- Include appropriate error handling
- Update documentation as needed
