#!/usr/bin/env bash
# fetch_private_content.sh
# 
# This script initializes and updates the private content submodule
# (which contains copyrighted treatises and organization-specific templates).

set -e

echo "Updating private content submodule..."
git submodule update --init --remote private-content

echo "Submodule updated."
