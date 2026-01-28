# Stable Diffusion 3.5 Large Turbo API Docker Image
# Base image with CUDA 12.6 runtime for GPU acceleration

FROM nvidia/cuda:12.6.0-runtime-ubuntu22.04

# Prevent interactive prompts during package installation
ENV DEBIAN_FRONTEND=noninteractive

# Set Python to run in unbuffered mode for better logging
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Install Python 3.10 and essential dependencies
# Note: git is required for installing vllm-omni from git source
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3.10 \
    python3.10-venv \
    python3-pip \
    gcc \
    g++ \
    git \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Set C compiler for Triton JIT compilation
ENV CC=gcc

# Set Python 3.10 as default
RUN update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.10 1 \
    && update-alternatives --install /usr/bin/python python /usr/bin/python3.10 1

# Set working directory
WORKDIR /app

# Copy requirements first for better layer caching
COPY requirements.txt .

# Upgrade pip and install Python dependencies
# Use PyTorch CUDA 12.6 wheels from the official PyTorch index
# Note: This installs vllm==0.12.0 and vllm-omni from git for optimized inference
RUN pip3 install --no-cache-dir --upgrade pip \
    && pip3 install --no-cache-dir --extra-index-url https://download.pytorch.org/whl/cu126 -r requirements.txt

# Copy application code
COPY app/ ./app/

# HuggingFace model cache directory for persistent storage
# Mount a volume to /models to cache models across container restarts
ENV HF_HOME=/models

# Set environment variables with defaults
# These can be overridden at runtime
ENV MODEL_ID=stabilityai/stable-diffusion-3.5-large-turbo
ENV HOST=0.0.0.0
ENV PORT=8000

# API Key for authentication (optional)
# If set, all requests must include Authorization: Bearer header with this value
# If not set, authentication is disabled
# Example: docker run -e API_KEY=your-secret-key ...
ENV API_KEY=""

# Hugging Face token for model access (alternative: HF_TOKEN)
ENV HUGGING_FACE_HUB_TOKEN=""

# Expose the API port
EXPOSE 8000

# Health check to verify the API is running
HEALTHCHECK --interval=30s --timeout=30s --start-period=300s --retries=3 \
    CMD python3 -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

# Run the FastAPI application with uvicorn
CMD ["python3", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
