# Dockerfile
# Azure Functions Python Docker Image
# This Dockerfile is for local testing and custom container deployment

FROM mcr.microsoft.com/azure-functions/python:4-python3.11

ENV AzureWebJobsScriptRoot=/home/site/wwwroot \
    AzureFunctionsJobHost__Logging__Console__IsEnabled=true \
    PYTHON_ENABLE_WORKER_EXTENSIONS=1 \
    PYTHON_ISOLATE_WORKER_DEPENDENCIES=1

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create app directory
WORKDIR /home/site/wwwroot

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy function app files
COPY host.json .
COPY api_service.py .
COPY confluence_qa_orchestrator.py .
COPY utils.py .

# Copy any additional modules
COPY *.py ./

# Create necessary directories
RUN mkdir -p /home/site/wwwroot/.python_packages

# Set permissions
RUN chmod -R 755 /home/site/wwwroot

# The Azure Functions runtime will handle the rest
# No CMD needed as the base image handles it