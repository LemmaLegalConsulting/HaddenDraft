#!/usr/bin/env bash
# fetch_private_content.sh
# 
# This script fetches copyrighted/private content (e.g. treatises like the Green Book 
# and Ohio Eviction Law) from a private GitHub repository and ingests them into the 
# public project's content library.
#
# Usage:
#   ./scripts/fetch_private_content.sh <PRIVATE_REPO_URL>
#
# Example:
#   ./scripts/fetch_private_content.sh git@github.com:LemmaLegalConsulting/PrivateContent.git

set -e

PRIVATE_REPO=$1

if [ -z "$PRIVATE_REPO" ]; then
    echo "Usage: $0 <PRIVATE_REPO_URL>"
    echo "Example: $0 git@github.com:LemmaLegalConsulting/PrivateContent.git"
    exit 1
fi

echo "Fetching private content from $PRIVATE_REPO..."

# Create a temporary directory to clone the private repository
TEMP_DIR=$(mktemp -d)
trap 'rm -rf "$TEMP_DIR"' EXIT

git clone --depth 1 "$PRIVATE_REPO" "$TEMP_DIR"

# Ensure the source treatises directory exists
mkdir -p content/treatises/source/

# Copy the private treatises into the local source directory
# Assuming the private repo has a directory structure like: treatises/source/...
if [ -d "$TEMP_DIR/treatises/source" ]; then
    cp -R "$TEMP_DIR/treatises/source/"* content/treatises/source/
    echo "Successfully copied treatises to content/treatises/source/"
else
    echo "Warning: No treatises/source directory found in the private repository."
fi

# Run the ingestion script to chunk the legal sources (turns PDFs into markdown)
echo "Chunking legal sources..."
python3 scripts/chunk_legal_sources.py --all

echo "Ingestion complete. The markdown chunks are now available for deployment."
echo "Note: Both the source PDFs and the generated markdown chunks are ignored in .gitignore."
