#!/bin/bash

echo "Installing required Python packages..."
pip install azure-storage-blob azure-search-documents openai --quiet

echo "Running chunking solution..."
python3 infra/create-chunking-solution.py