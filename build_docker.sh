#!/usr/bin/env bash
set -e

AZURE_STORAGE_URL=$1

if [ -z "$AZURE_STORAGE_URL" ]; then
    echo "Usage: $0 <AZURE_STORAGE_URL>"
    echo "Example: $0 'https://myaccount.blob.core.windows.net/mycontainer/content.zip?sp=r&st=...'"
    exit 1
fi

echo "Downloading content from Azure Storage..."
python scripts/sideload_content.py --url "$AZURE_STORAGE_URL" --target "content/"

echo "Building Docker image..."
docker build -t agentic_housing_drafting .

echo "Done! You can now run the image with:"
echo "docker run -p 80:80 agentic_housing_drafting"
